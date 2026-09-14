#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ニュース収集 → 重要度判定 → 影響銘柄付与 → news.json のデータ構造を組み立てる。"""
import json
from datetime import datetime
from pathlib import Path

from . import impact as impact_mod
from . import llm as llm_mod
from . import rss as rss_mod
from . import stocks as stocks_mod
from .config import FEEDS, JST, MARKET_TICKERS, MAX_AGE_HOURS, MAX_NEWS_ITEMS, PER_FEED_LIMIT

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


def build_news(feeds=None, rules=None, master=None, use_llm=True, limit=MAX_NEWS_ITEMS):
    """ニュースを集めて、1件ずつに重要度・カテゴリ・影響銘柄を付けたリストを返す。"""
    rules = rules or impact_mod.load()
    master = master or stocks_mod.load()
    raw_items = rss_mod.collect(feeds or FEEDS, per_feed_limit=PER_FEED_LIMIT, max_age_hours=MAX_AGE_HOURS)
    log(f"重複を束ねた結果 {len(raw_items)} 件の話題を取得しました。")

    news = []
    for item in raw_items:
        title = item["title"]
        if impact_mod.is_noise(title, rules):
            continue
        themes = impact_mod.match_themes(title, rules)
        stars, reason = impact_mod.score_importance(item, themes, rules)
        impacts = impact_mod.affected_stocks(item, themes, rules, master, max_items=8)
        category = impact_mod.pick_category(item, themes, rules)
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
    """上位ニュースにだけ要約・コメント・追加銘柄を付ける(無料枠を節約するため)。"""
    targets = news[:target]
    candidates = [
        {"code": s["code"], "name": s["name"], "sector": s.get("sector", ""), "themes": s.get("themes", [])}
        for s in master.stocks
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
