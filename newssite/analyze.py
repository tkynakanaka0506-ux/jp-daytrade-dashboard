#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ニュース収集 → 重要度判定 → 影響銘柄付与 → news.json のデータ構造を組み立てる。"""
import json
from datetime import datetime
from pathlib import Path

from . import backtest as backtest_mod
from . import catalyst_export
from . import impact as impact_mod
from . import llm as llm_mod
from . import rss as rss_mod
from . import stocks as stocks_mod
from .config import FEEDS, GOV_FEEDS, JST, MARKET_TICKERS, MAX_AGE_HOURS, MAX_NEWS_ITEMS, PER_FEED_LIMIT

DIRECTION_LABEL = impact_mod.DIRECTION_LABEL


def log(msg):
    print(f"[analyze] {msg}", flush=True)


def _fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _dig(obj, path):
    cur = obj
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def market_snapshot(data_json_path):
    """既存の data.json(Javaが取得している指数・為替)があればヘッダー用に読み込む。"""
    path = Path(data_json_path)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log(f"data.json を読めませんでした({e})。市況ヘッダーは省略します。")
        return []

    out = []
    for key, label in MARKET_TICKERS:
        node = _dig(data, key)
        if not isinstance(node, dict):
            continue
        value = (node.get("value") or "").strip()
        if not value or value in ("―", "-"):
            continue
        out.append({
            "label": label,
            "value": value,
            "change_pct": node.get("change_pct"),
            "asof": node.get("asof", ""),
        })
    return out


NOVELTY_LABEL = {"high": "新規", "medium": "続報", "low": "再報道"}


def _news_novelty(item, prior_norms):
    """[PRESENTATION LAYER] 「初出/続報/再報道」の3段階。

    政策として重要でも、既に何度も報じられているニュースは新しい投資材料
    とは限らない、という考え方をスコアと別軸で表現する。theme/direction/
    direct-indirect(FACTUAL LAYER)には一切使わない・影響しない。

    判定材料は2つ:
      - related(同日内に他媒体が同じ話題を報じた数。rss.collect が既に集計済み)
      - 過去日の記録(backtest_events.jsonl)に似た見出しが既にあるか
        (=違う日にも同じ話題が出ている「続報」らしさ)

    prior_norms は事前に rss._normalize() 済みの文字列を渡すこと
    (_same_topic は正規化済み同士の比較を前提にしているため)。
    """
    norm = rss_mod._normalize(item["title"])
    seen_before = any(rss_mod._same_topic(norm, prior) for prior in prior_norms)
    related_count = len(item.get("related", []))

    if seen_before:
        return "low", "similar_seen_before"
    if related_count >= 2:
        return "medium", f"{related_count + 1}媒体が同時報道"
    return "high", "初出・類似の過去記録なし"


def build_news(feeds=None, rules=None, master=None, use_llm=True, limit=MAX_NEWS_ITEMS):
    """ニュースを集めて、1件ずつに重要度・カテゴリ・影響銘柄を付けたリストを返す。"""
    rules = rules or impact_mod.load()
    master = master or stocks_mod.load()
    raw_items = rss_mod.collect(
        feeds or FEEDS, direct_feeds=GOV_FEEDS, per_feed_limit=PER_FEED_LIMIT, max_age_hours=MAX_AGE_HOURS
    )
    log(f"重複を束ねた結果 {len(raw_items)} 件の話題を取得しました。")

    today = datetime.now(JST).strftime("%Y-%m-%d")
    prior_titles = backtest_mod.load_prior_titles(today)
    prior_norms = [rss_mod._normalize(t) for t in prior_titles]

    news = []
    for item in raw_items:
        title = item["title"]
        if impact_mod.is_noise(title, rules):
            continue
        themes = impact_mod.match_themes(title, rules)
        stars, reason = impact_mod.score_importance(item, themes, rules)
        impacts = impact_mod.affected_stocks(item, themes, rules, master, max_items=8)
        category = impact_mod.pick_category(item, themes, rules)
        maturity_score, maturity_label = impact_mod.score_policy_maturity(title, rules)
        novelty, novelty_reason = _news_novelty(item, prior_norms)
        # [PRESENTATION LAYER] 表示用の統合スコアを付与するだけで、direction/theme
        # など impacts の中身(FACTUAL LAYER)は書き換えない。
        for imp in impacts:
            imp["policy_impact_score"] = impact_mod.compute_policy_impact_score(imp, maturity_score)
        news.append({
            "id": item["id"],
            "title": title,
            "url": item["url"],
            "source": item["source"],
            "published_at": _fmt_dt(item.get("published")),
            "published_ts": item["published"].timestamp() if item.get("published") else 0,
            "category": category,
            "category_label": rules.category_label.get(category, "市況"),
            "category_emoji": rules.category_emoji.get(category, "📰"),
            "importance": stars,
            "importance_reason": reason,
            "future_signal": impact_mod.is_future_signal(title, rules),
            "policy_maturity": maturity_score,
            "policy_maturity_label": maturity_label,
            "news_novelty": novelty,
            "news_novelty_label": NOVELTY_LABEL[novelty],
            "themes": [t["label"] for t in themes],
            "summary": "",
            "impact_comment": "",
            "impacts": impacts,
            "related": item.get("related", [])[:4],
        })

    # 重要度 → 新しさ の順に並べ、上位だけをページに載せる
    news.sort(key=lambda n: (-n["importance"], -n["published_ts"]))
    news = news[:limit]

    if use_llm and llm_mod.available():
        _apply_llm(news, master)

    return news


def _apply_llm(news, master, target=14):
    """上位ニュースにだけ要約・コメント・追加銘柄を付ける(無料枠を節約するため)。

    candidate_stocks も全銘柄ではなく、今回のニュースのテーマに関係する銘柄
    (+主力銘柄は保険として常に残す)だけに絞り、プロンプトのトークン量を減らす。
    """
    targets = news[:target]
    if not targets:
        return
    used_themes = set()
    for n in targets:
        used_themes.update(n.get("themes", []))
    if used_themes:
        pool = [s for s in master.stocks if used_themes & set(s.get("themes", []))]
    else:
        pool = list(master.stocks)
    seen = {s["code"] for s in pool}
    for s in master.stocks:
        if "主力" in s.get("themes", []) and s["code"] not in seen:
            pool.append(s)
            seen.add(s["code"])
    candidates = [
        {"code": s["code"], "name": s["name"], "sector": s.get("sector", ""), "themes": s.get("themes", [])}
        for s in pool
    ]
    result = llm_mod.enrich(targets, candidates)
    if not result:
        return
    by_id = {n["id"]: n for n in targets}
    applied = 0
    for entry in result.get("items", []) or []:
        news_item = by_id.get(entry.get("id"))
        if not news_item:
            continue
        summary = (entry.get("summary") or "").strip()
        comment = (entry.get("impact_comment") or "").strip()
        if summary:
            news_item["summary"] = summary
        if comment:
            news_item["impact_comment"] = comment
        importance = entry.get("importance")
        if isinstance(importance, int) and 1 <= importance <= 5:
            # ルール判定とLLM判定の平均(四捨五入)にして、片方の極端な判定に寄せない
            news_item["importance"] = int(round((news_item["importance"] + importance) / 2))
        have = {i["code"] for i in news_item["impacts"]}
        for extra in (entry.get("extra_stocks") or [])[:3]:
            stock = master.by_code.get((extra.get("code") or "").strip())
            if not stock or stock["code"] in have:
                continue
            direction = extra.get("direction") if extra.get("direction") in DIRECTION_LABEL else "watch"
            news_item["impacts"].append({
                "code": stock["code"],
                "name": stock["name"],
                "sector": stock.get("sector", ""),
                "direction": direction,
                "direction_label": DIRECTION_LABEL[direction],
                "strength": "中",
                "reason": (extra.get("reason") or "").strip() or "ニュース内容との関連がAI判定で指摘された銘柄",
                "theme": "AI判定",
                "origin": "llm",
            })
            have.add(stock["code"])
        applied += 1
    log(f"{applied} 件のニュースにAI補強を反映しました。")
    news.sort(key=lambda n: (-n["importance"], -n["published_ts"]))


def stock_ranking(news, limit=20):
    """ニュース横断で「今どの銘柄に材料が集まっているか」を集計する。"""
    agg = {}
    for n in news:
        weight = n["importance"]
        for imp in n["impacts"]:
            row = agg.setdefault(imp["code"], {
                "code": imp["code"],
                "name": imp["name"],
                "sector": imp.get("sector", ""),
                "positive": 0,
                "negative": 0,
                "watch": 0,
                "score": 0,
                "news": [],
            })
            row[imp["direction"]] = row.get(imp["direction"], 0) + 1
            sign = {"positive": 1, "negative": -1, "watch": 0}[imp["direction"]]
            row["score"] += sign * weight
            if len(row["news"]) < 3:
                row["news"].append({
                    "title": n["title"],
                    "url": n["url"],
                    "direction": imp["direction"],
                    "reason": imp["reason"],
                    "importance": n["importance"],
                })
    rows = list(agg.values())
    for row in rows:
        row["mentions"] = row["positive"] + row["negative"] + row["watch"]
    rows.sort(key=lambda r: (-r["mentions"], -abs(r["score"])))
    return rows[:limit]


def build(data_json_path="data.json", use_llm=True):
    """news.json に書き出すデータ全体を作る。"""
    rules = impact_mod.load()
    master = stocks_mod.load()
    now = datetime.now(JST)
    news = build_news(rules=rules, master=master, use_llm=use_llm)
    ranking = stock_ranking(news)
    # [バックテスト基盤] 本番ビルドのたびに今回判定したイベントをログへ追記する。
    # 株価データはまだ接続していないため、現時点ではニュース×銘柄×スコアの
    # 履歴を貯めるだけ(dev.py backtest で BACKTEST_STATUS を確認できる)。
    try:
        backtest_mod.record_events(news, generated_at=now)
    except Exception as e:  # バックテスト記録の失敗でサイト生成自体を止めない
        log(f"バックテストイベントの記録に失敗しました({e})。サイト生成は続行します。")

    # [Catalyst Intelligence 出力] 他プロジェクト(投資判断エンジン側)が読み込む
    # 「今アクティブな政策材料」スナップショット。統合演算はしない(catalyst_export
    # のdocstring参照)。書き出しの失敗でサイト生成自体は止めない。
    try:
        n = catalyst_export.export_signals(news)
        log(f"政策材料シグナルを{n}件書き出しました({catalyst_export.EXPORT_PATH})。")
    except Exception as e:
        log(f"政策材料シグナルの書き出しに失敗しました({e})。サイト生成は続行します。")

    status = "updated" if news else "unavailable"
    status_message = (
        f"{len(news)} 件のニュースを取得しました。"
        if news
        else "ニュースを取得できませんでした(RSS取得失敗の可能性があります)。"
    )

    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "generated_iso": now.isoformat(timespec="seconds"),
        "status": status,
        "status_message": status_message,
        "llm_used": bool(use_llm and llm_mod.available()),
        "categories": rules.categories,
        "market": market_snapshot(data_json_path),
        "news": news,
        "stock_ranking": ranking,
        "counts": {
            "news": len(news),
            "high_importance": sum(1 for n in news if n["importance"] >= 4),
            "stocks": len(ranking),
        },
    }
