#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini API / Groq API(いずれも無料枠)を使って、data.json のうち「話題性・重要度の判断」が
必要な以下のフィールドだけを補完するスクリプト。他の決定論的なフィールド(市場指数・
TDnet開示・テクニカル指標)は Main.java が担当し、このスクリプトはそのあとに実行する。

  - overnight_news / afterclose_news (地政学・市場材料ニュース)
  - us_good_news (米国株の好材料ニュース。見出しテキストから読み取れる範囲で、
    「好決算なのに売られる(材料出尽くし)」を示す記述が無いかの簡易矛盾分析も行う)
  - movers_morning / movers_afterclose (値動き・出来高で話題の銘柄)
  - technical[].baked_in_warning / baked_in_reason (織り込み済みリスク判定)
  - technical[].theme / theme_trend_note (投資テーマ自動タグ付け)

設計方針(役割分担・並行実行):
  - ニュースの"取得"自体は Google News RSS(無料・APIキー不要)で行う。
  - 5つのタスクを2グループに分け、Gemini(グループA)とGroq(グループB)それぞれに
    1回ずつのリクエストで依頼する(以前は5タスクを1回のGeminiリクエストに統合していたが、
    Gemini無料枠のレート制限(429)が2026年8月以降ほぼ常時発生するようになり、統合しても
    改善しなかったため、プロバイダごと分散させて片方が落ちても残りは更新されるようにした)。
      グループA(Gemini): news_items, us_news_items
      グループB(Groq):   movers_items, tech_risk_items, theme_items
  - さらに、割り当てられたプロバイダの呼び出しが失敗した場合、もう片方のAPIキーが
    設定されていればそちらでフォールバック再試行する(クロスプロバイダ・フォールバック)。
    両方失敗した場合は対象配列を空にし、取得不可状態を記録する。
  - GEMINI_API_KEY・GROQ_API_KEYのどちらも未設定の場合も、ニュース系フィールドを
    空にして取得不可状態を保存し、正常終了する(exit code 0)。このスクリプトの失敗で
    パイプライン全体(Java取得・HTML生成・push)を止めないことを最優先する。

使い方: python3 news_analyzer.py <morning|evening> <data.jsonのパス>
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import ssl
try:
    import certifi
    _CERTIFI_AVAILABLE = True
except Exception:
    certifi = None
    _CERTIFI_AVAILABLE = False

def _get_ssl_context():
    if _CERTIFI_AVAILABLE:
        return ssl.create_default_context(cafile=certifi.where())
    # certifi が無ければ検証無効化してでも動かす(ユーザは pip install certifi を推奨)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (compatible; jp-daytrade-dashboard-bot/1.0)"
GEMINI_MODEL = "gemini-2.5-flash-lite"
GROQ_MODEL = "llama-3.3-70b-versatile"

# 無料枠のレート制限(429 Too Many Requests)対策:
# 呼び出し間隔を最低○秒空け、429時はバックオフしてリトライする。
GEMINI_MIN_INTERVAL_SEC = 5
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_BASE_SEC = 8

GROQ_MIN_INTERVAL_SEC = 2
GROQ_MAX_RETRIES = 3
GROQ_RETRY_BASE_SEC = 5

_last_call_ts = {"gemini": 0.0, "groq": 0.0}
JST = timezone(timedelta(hours=9))


def log(msg):
    print(f"[news_analyzer] {msg}", file=sys.stderr)


def _checked_at():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M")


def set_data_status(root, field, state, message):
    """当回の取得状態を保存する。失敗時も理由を残し、前回値を有効扱いしない。"""
    statuses = root.setdefault("data_status", {})
    statuses[field] = {
        "state": state,
        "checked_at": _checked_at(),
        "message": message,
    }


def mark_updated(root, field):
    """今回の実行で取得・更新したデータだけに更新時刻を残す。"""
    timestamps = root.setdefault("data_updated_at", {})
    updated_at = _checked_at()
    timestamps[field] = updated_at
    set_data_status(root, field, "updated", "今回の実行で取得・更新しました。")


def mark_empty(root, field, message):
    """取得には成功したが該当がなかった状態を記録する。"""
    mark_updated(root, field)
    set_data_status(root, field, "empty", message)


def mark_unavailable(root, field, message):
    """取得できなかったデータを空のまま取得不可として記録する。"""
    set_data_status(root, field, "unavailable", message)


def fetch_rss(query, hl="ja", gl="JP", ceid="JP:ja", limit=10):
    """Google News RSS(無料・キー不要)からニュース候補を取得する。"""
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(query)
        + f"&hl={hl}&gl={gl}&ceid={ceid}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = _get_ssl_context()
    with urllib.request.urlopen(req, timeout=20, context=ctx) as res:
        data = res.read()
    root = ET.fromstring(data)
    items = []
    for item in root.findall("./channel/item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else ""
        if title:
            items.append({"title": title, "url": link, "source": source, "time": pub})
    return items


def _wait_for_interval(provider, min_interval):
    elapsed = time.time() - _last_call_ts[provider]
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)


def call_gemini(api_key, prompt, schema):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        f"?key={urllib.parse.quote(api_key)}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.2,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        method="POST",
    )
    last_err = None
    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        _wait_for_interval("gemini", GEMINI_MIN_INTERVAL_SEC)
        try:
            ctx = _get_ssl_context()
            with urllib.request.urlopen(req, timeout=90, context=ctx) as res:
                payload = json.loads(res.read().decode("utf-8"))
            _last_call_ts["gemini"] = time.time()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except urllib.error.HTTPError as e:
            _last_call_ts["gemini"] = time.time()
            last_err = e
            if e.code == 429 and attempt < GEMINI_MAX_RETRIES:
                wait = GEMINI_RETRY_BASE_SEC * attempt
                log(f"[Gemini] HTTP 429(レート制限)のため{wait}秒待機してリトライします({attempt}/{GEMINI_MAX_RETRIES})")
                time.sleep(wait)
                continue
            raise
    raise last_err


def call_groq(api_key, prompt, schema):
    """Groq(OpenAI互換API)を使い、JSONオブジェクトを1回のchat completionsで取得する。
    Groqの構造化出力(response_format=json_object)には「JSON」という語をプロンプトに
    含める必要があるため、指示文にも明記している。スキーマはプロンプト内の説明で
    表現し、パース側は既存コードと同様に.get()で欠損キーに寛容に対応する。"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    schema_hint = (
        "\n\n出力は必ず次のJSONスキーマ(キー名)に従うJSONオブジェクトのみとし、"
        "説明文やコードブロック記法(```)は一切付けないこと:\n"
        + json.dumps(schema, ensure_ascii=False)
    )
    body = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt + schema_hint},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
          "User-Agent": UA,
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    last_err = None
    for attempt in range(1, GROQ_MAX_RETRIES + 1):
        _wait_for_interval("groq", GROQ_MIN_INTERVAL_SEC)
        try:
            ctx = _get_ssl_context()
            with urllib.request.urlopen(req, timeout=90, context=ctx) as res:
                payload = json.loads(res.read().decode("utf-8"))
            _last_call_ts["groq"] = time.time()
            text = payload["choices"][0]["message"]["content"]
            return json.loads(text)
        except urllib.error.HTTPError as e:
            _last_call_ts["groq"] = time.time()
            last_err = e
            if e.code == 429 and attempt < GROQ_MAX_RETRIES:
                wait = GROQ_RETRY_BASE_SEC * attempt
                log(f"[Groq] HTTP 429(レート制限)のため{wait}秒待機してリトライします({attempt}/{GROQ_MAX_RETRIES})")
                time.sleep(wait)
                continue
            raise
    raise last_err


def call_llm(provider, gemini_key, groq_key, prompt, schema):
    if provider == "gemini":
        return call_gemini(gemini_key, prompt, schema)
    return call_groq(groq_key, prompt, schema)


def call_with_fallback(group_name, primary_provider, gemini_key, groq_key, prompt, schema):
    """割り当てられたプロバイダで呼び出し、失敗時はもう片方で再試行する。
    両方失敗または未設定ならNoneを返し、呼び出し側が当回の空配列と取得不可状態を保存する。"""
    providers_tried = []
    order = [primary_provider] + [p for p in ("gemini", "groq") if p != primary_provider]
    for provider in order:
        key = gemini_key if provider == "gemini" else groq_key
        if not key:
            continue
        providers_tried.append(provider)
        try:
            result = call_llm(provider, gemini_key, groq_key, prompt, schema)
            if provider != primary_provider:
                log(f"[{group_name}] {primary_provider}が失敗したため{provider}にフォールバックして成功しました。")
            return result
        except Exception as e:
            log(f"[{group_name}] {provider}呼び出しが失敗しました: {e}")
    if not providers_tried:
        log(f"[{group_name}] 利用可能なAPIキーが無いため取得不可として処理します。")
    else:
        log(f"[{group_name}] 全プロバイダ({', '.join(providers_tried)})が失敗しました。前回値は利用しません。")
    return None


# ---------------- スキーマ定義 ----------------

NEWS_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "url": {"type": "STRING"},
        "source": {"type": "STRING"},
        "time": {"type": "STRING"},
        "investment_sector": {"type": "STRING"},
        "investment_companies": {"type": "ARRAY", "items": {"type": "STRING"}},
        "money_flow": {"type": "STRING"},
        "money_flow_type": {"type": "STRING", "enum": ["current", "expected"]},
    },
    "required": ["title", "url", "source", "time"],
}

MOVERS_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "code": {"type": "STRING"},
        "name": {"type": "STRING"},
        "price": {"type": "STRING"},
        "change_pct": {"type": "NUMBER"},
        "volume_note": {"type": "STRING"},
        "reason": {"type": "STRING"},
    },
    "required": ["name", "reason"],
}

US_NEWS_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ticker": {"type": "STRING"},
        "company": {"type": "STRING"},
        "category": {
            "type": "STRING",
            "enum": ["earnings_beat", "guidance_raise", "upgrade", "buyback", "dividend_hike"],
        },
        "headline": {"type": "STRING"},
        "url": {"type": "STRING"},
        "time": {"type": "STRING"},
        "baked_in_verdict": {
            "type": "STRING",
            "enum": ["本物の初動", "過熱・警戒", "材料出尽くし", "判定不能"],
        },
        "baked_in_reason": {"type": "STRING"},
    },
    "required": ["ticker", "company", "category", "headline", "url"],
}

TECH_RISK_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "code": {"type": "STRING"},
        "warning": {"type": "BOOLEAN"},
        "reason": {"type": "STRING"},
    },
    "required": ["code", "warning"],
}

THEME_TAG_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "code": {"type": "STRING"},
        "theme": {"type": "STRING"},
        "theme_trend_note": {"type": "STRING"},
    },
    "required": ["code", "theme"],
}


def _heuristic_us_good_from_rss(candidates):
    """Simple deterministic extractor for US good-news categories from RSS titles.
    This is a fallback when the LLM-based analysis is unavailable or returns empty.
    It returns a list of objects with at least `headline` and `category` filled.
    """
    out = []
    if not candidates:
        return out
    for it in candidates:
        title = (it.get("title") or "").strip()
        url = it.get("url") or ""
        time_ = it.get("time") or ""
        t = title.lower()
        cat = None
        # earnings beat
        if re.search(r"\bbeat(s|ing)?\b|beats (estimates|expectations|consensus)|beat (estimates|consensus)", t):
            cat = "earnings_beat"
        # guidance raise / outlook up
        elif re.search(r"raise(s|d)? (guidance|outlook)|updat(e|ed) guidance|boost(s|ed) (guidance|outlook)|guidance (raise|up)", t):
            cat = "guidance_raise"
        # upgrade / price target up
        elif re.search(r"upgrad(e|ed|es)|raise(d)? (price )?target|initiated coverage|rating (upgrade|raised)", t):
            cat = "upgrade"
        # buyback
        elif re.search(r"buyback|share repurchase|repurchase|announc(es|ed) repurchase", t):
            cat = "buyback"
        # dividend hike
        elif re.search(r"dividend (hike|increase|raise|boost)|raises dividend|increase in dividend", t):
            cat = "dividend_hike"

        if cat:
            out.append({
                "ticker": "",
                "company": "",
                "category": cat,
                "headline": title,
                "url": url,
                "time": time_,
            })
    return out


def _compute_pre_earnings_indicator(root, technical, news_candidates, growth_candidates):
    """Compute deterministic leading (pre-earnings) indicators per technical item.
    Returns a list of {code, name, score, signals, detail_urls} sorted by score desc.
    Uses RSS news hit counts, recent growth_candidates, short-term returns and sector signals.
    """
    indicators = []
    if not technical:
        return indicators

    # keyword lists (Japanese and English) indicating forward-looking positive signals
    positive_kw = [
        "受注", "増産", "受注好調", "受注拡大", "出荷", "販売好調", "増収見込み", "ガイダンス上方",
        "guidance", "beat", "order", "demand", "boost", "raise", "outlook up", "ship",
    ]

    growth_by_name = {g.get("company"): g for g in (growth_candidates or []) if g.get("company")}

    # prepare lowercased titles for quick search
    titles = [(it.get("title") or "", it.get("url")) for it in (news_candidates or [])]
    titles_lc = [(t.lower(), u) for (t, u) in titles]

    for t in technical:
        code = t.get("code") or f"NAME:{t.get('name','') }"
        name = (t.get("name") or "").strip()
        score = 0.0
        signals = []
        urls = []

        # 1) growth_candidates direct match
        g = growth_by_name.get(name)
        if g:
            score += 20.0
            signals.append("TDnet: 当日開示(増配/上方修正など)")
            if g.get("url"):
                urls.append(g.get("url"))

        # 2) news mentions with positive keywords
        mention_hits = 0
        for tlc, u in titles_lc:
            if not name:
                continue
            if name.lower() in tlc:
                for kw in positive_kw:
                    if kw in tlc:
                        mention_hits += 1
                        if u:
                            urls.append(u)
                        break
        if mention_hits:
            add = min(mention_hits * 6.0, 30.0)
            score += add
            signals.append(f"ニュース指標: 関連見出し {mention_hits}件")

        # 3) short-term momentum (ret_5d_pct)
        ret5 = t.get("ret_5d_pct")
        if isinstance(ret5, (int, float)):
            if ret5 >= 5.0:
                score += 10.0
                signals.append(f"直近5日上昇 {ret5:.1f}%")
            elif ret5 <= -5.0:
                score -= 8.0
                signals.append(f"直近5日下落 {ret5:.1f}%(減点)")

        # 4) sector contrarian
        if t.get("sector_contrarian"):
            score += 8.0
            signals.append("セクター逆行高")

        # 5) squeeze / credit ratio & RSI
        credit_ratio = t.get("credit_ratio")
        rsi = t.get("rsi")
        if isinstance(credit_ratio, (int, float)) and credit_ratio < 1.0:
            bonus = max(0.0, (1.0 - credit_ratio)) * 6.0
            score += bonus
            signals.append(f"信用倍率低め(踏み上げ余地) {credit_ratio}")
        if isinstance(rsi, (int, float)) and rsi <= 35:
            score += 6.0
            signals.append(f"RSI売られ過ぎ {rsi}")

        # 6) high price penalty (reduce notifications for very hot/value stocks)
        high_dist = t.get("high_52w_dist_pct")
        if isinstance(high_dist, (int, float)) and high_dist <= 3.0:
            score -= 10.0
            signals.append("52週高値に接近(過熱・減点)")

        # floor/ceiling and normalization
        score = max(-20.0, min(50.0, score))
        # scale to 0-100
        norm = int((score + 20.0) / 70.0 * 100.0)
        indicators.append({
            "code": code,
            "name": name,
            "score": norm,
            "raw_score": round(score, 2),
            "signals": signals,
            "urls": urls,
        })

    indicators.sort(key=lambda x: x.get("score", 0), reverse=True)
    return indicators


def _assess_industry_spillover(gemini_key, groq_key, technical, news_candidates):
    """Ask the LLM to infer whether recent peer/company headlines imply positive spillover
    to a watched ticker. Returns a map (code_or_name -> {influence, reason, confidence})."""
    if not gemini_key and not groq_key:
        return {}
    # Group by sector and prepare prompts per sector to limit LLM calls
    sector_map = {}
    for t in technical:
        sector = (t.get("sector") or "").strip()
        if not sector:
            continue
        sector_map.setdefault(sector, []).append(t)

    # prepare news by company mention
    titles = [(it.get("title") or "", it.get("url") or "") for it in (news_candidates or [])]

    schema = {
        "type": "OBJECT",
        "properties": {
            "assessments": {"type": "ARRAY", "items": {"type": "OBJECT"}},
        },
        "required": ["assessments"],
    }

    result_map = {}
    for sector, items in sector_map.items():
        # collect peer headlines mentioning sector companies
        sector_news = []
        for title, url in titles:
            lc = title.lower()
            for t in items:
                name = (t.get("name") or "").lower()
                if name and name in lc:
                    sector_news.append({"company": t.get("name"), "title": title, "url": url})
                    break
        if not sector_news:
            continue
        # build prompt
        prompt = (
            f"あなたは日本株の業界影響分析の補助者です。業種: {sector}\n"
            "以下は同業他社の最近の見出し一覧です。これらの見出しがウォッチリストの他の銘柄に対して"
            "ポジティブな波及効果(業績上振れの予兆)を示すかどうかを、銘柄ごとに評価してください。"
            "出力は JSON 配列 'assessments' として、各要素は {\"code\"(任意), \"name\", \"influence\":\"positive|neutral|negative\",\"reason\":\"...\",\"confidence\":0-100} の形にしてください。\n"
            "同じ業種に属するウォッチリスト銘柄: "
        )
        prompt += ", ".join([t.get("name","") for t in items]) + "\n\n"
        prompt += "最近の見出し一覧:\n"
        for n in sector_news:
            prompt += f"- {n['company']}: {n['title']} ({n['url']})\n"

        try:
            resp = call_with_fallback(f"業種波及({sector})", "gemini", gemini_key, groq_key, prompt, schema)
            if not resp:
                continue
            assessments = resp.get("assessments") or []
            for a in assessments:
                key = a.get("code") or a.get("name")
                if not key:
                    continue
                result_map[key] = {
                    "influence": a.get("influence"),
                    "reason": a.get("reason"),
                    "confidence": a.get("confidence"),
                }
        except Exception as e:
            log(f"業種波及のLLM評価が失敗しました({sector}): {e}")
            continue
    return result_map


def _compute_prediction_scenarios(indicators, technical, root, news_candidates):
    """Add prediction labels and risk triggers based on five modules:
    1) supply-demand squeeze
    2) VWAP/volume accumulation (approx)
    3) management confidence (ir_tone)
    4) sector rotation
    5) combine into scenario labels and prediction_score
    Modifies indicators in-place and returns them.
    """
    tech_map = {t.get('code') or t.get('name'): t for t in (technical or [])}
    titles = [(it.get('title') or '').lower() for it in (news_candidates or [])]

    for ind in indicators:
        code = ind.get('code')
        name = ind.get('name')
        key = code if code in tech_map else name
        t = tech_map.get(key, {})
        # initialize fields
        ind.setdefault('prediction_labels', [])
        ind.setdefault('prediction_notes', [])
        ind.setdefault('risk_triggers', [])
        pred_score = 0.0

        # 1) supply-demand squeeze heuristic
        credit_ratio = t.get('credit_ratio')
        ma5_dev = t.get('ma5_dev')
        ma5_above = False
        try:
            if isinstance(ma5_dev, str) and ma5_dev.endswith('%'):
                ma5_val = float(ma5_dev.replace('%','').replace('+',''))
                ma5_above = ma5_val > 0
            elif isinstance(ma5_dev, (int,float)):
                ma5_above = ma5_dev > 0
        except Exception:
            ma5_above = False

        news_hit = False
        lname = (name or '').lower()
        for tl in titles:
            if lname and lname in tl:
                news_hit = True
                break

        squeeze_flag = False
        if isinstance(credit_ratio, (int, float)) and credit_ratio < 1.0:
            # mark sell-side pressure (canonical flag)
            ind.setdefault('prediction_notes', []).append(f'信用倍率低め({credit_ratio})')
            ind.setdefault('reason_flags', []).append('売り残過多')
            # extra boost when price is above MA5 and news exists
            if ma5_above and news_hit:
                squeeze_flag = True
                ind.setdefault('prediction_labels', []).append('踏み上げ期待')
                ind.setdefault('prediction_notes', []).append('売り残増・5日線上・材料予兆(🚀)')
                pred_score += 28.0
            else:
                # partial signal when only sell-side increase is observed
                pred_score += 6.0

        # 2) VWAP / volume accumulation
        vol = t.get('volume')
        avg5 = t.get('avg_volume_5d')
        price = None
        live = t.get('live_quote') or {}
        price = live.get('price') or t.get('price')
        # prefer explicit VWAP if available
        vwap = None
        try:
            vwap = float(live.get('vwap')) if live.get('vwap') is not None else None
        except Exception:
            vwap = None
        if isinstance(vol, (int,float)) and isinstance(avg5, (int,float)) and vol > avg5 and ((vwap is not None and isinstance(price,(int,float)) and price > vwap) or ma5_above):
            vwap_like = True
            if 'クジラ追随' not in ind['prediction_labels']:
                ind.setdefault('prediction_labels', []).append('クジラ追随')
            ind.setdefault('prediction_notes', []).append('出来高増・VWAP上(大口買い疑い)')
            pred_score += 15.0

        # detect gradual volume increase without news
        if isinstance(vol, (int,float)) and isinstance(avg5, (int,float)) and vol > avg5 * 1.5 and not news_hit:
            ind.setdefault('prediction_notes', []).append('出来高じわ増(先回り買い疑い)')
            pred_score += 10.0

        # 3) management confidence via existing ir_tone if present
        ir = ind.get('ir_tone') or {}
        if ir:
            tone = ir.get('tone')
            if tone == 'positive':
                ind.setdefault('prediction_labels', []).append('隠れ好業績予想')
                ind.setdefault('prediction_notes', []).append('IRトーン強気')
                ind.setdefault('reason_flags', []).append('経営者強気')
                pred_score += 20.0
            elif tone == 'negative':
                ind['prediction_notes'].append('IRトーン弱気(減点)')
                pred_score -= 15.0

        # 4) sector rotation: sector rising but stock lagging
        sector_avg = t.get('sector_avg_change_pct')
        ret5 = t.get('ret_5d_pct')
        if isinstance(sector_avg, (int,float)) and sector_avg > 1.0 and (not isinstance(ret5,(int,float)) or ret5 < 1.0):
            ind.setdefault('prediction_labels', []).append('出遅れ優良株')
            ind.setdefault('prediction_notes', []).append('セクター好調だが個別は未上昇')
            ind.setdefault('reason_flags', []).append('同業好調')
            pred_score += 10.0

        # 5) FX tailwind (existing fx_map integrated earlier may add fx_bonus into raw_score)
        # combine pred_score with existing raw_score
        raw = ind.get('raw_score', 0)
        combined = raw + pred_score
        # map to 0-100
        combined_norm = int(max(0, min(100, (combined + 40.0) / 90.0 * 100.0)))
        ind['prediction_score'] = round(combined, 2)
        ind['prediction_confidence'] = combined_norm

        # risk triggers and automated stop-loss calculation
        if isinstance(price, (int,float)):
            # stop-loss: either recent low (day_low) if available, else 90% of price, and VWAP-like (ma5) as secondary
            day_low = None
            if isinstance(live.get('day_low'), (int,float)):
                day_low = live.get('day_low')
            if day_low:
                sl_price = int(day_low)
                sl_note = '直近安値を割ったら撤退'
            else:
                sl_price = int(price * 0.90)
                sl_note = '現在値の10%下(目安)を撤退ライン'
            ind['risk_triggers'].append({'type':'stop_loss_price','value':sl_price,'note':sl_note})
            # relative pct
            try:
                pct = round((price - sl_price) / price * 100.0, 1)
                ind['risk_triggers'][-1]['pct'] = pct
            except Exception:
                pass
        if not ma5_above:
            ind.setdefault('risk_triggers', []).append({'type':'ma5_breach','note':'5日線割れでシナリオ崩れ'})
        # VWAP breach as stop signal
        if vwap is not None:
            try:
                ind.setdefault('risk_triggers', []).append({'type':'vwap_breach','value':int(vwap),'note':'VWAP下抜けでシナリオ崩れ'})
                if isinstance(price,(int,float)):
                    ind['risk_triggers'][-1]['pct'] = round((price - vwap) / price * 100.0, 1)
            except Exception:
                pass

        # final label consolidation for high-score picks
        # if prediction_confidence (soon) or combined_norm >=70, ensure one of primary labels exists
        # we'll assign 'クジラ追随' when vwap_like True, else '踏み上げ期待' when squeeze_flag True
        # (labels may already exist from above rules)
        if combined_norm >= 70:
            if vwap_like and 'クジラ追随' not in ind['prediction_labels']:
                ind.setdefault('prediction_labels', []).append('クジラ追随')
            if squeeze_flag and '踏み上げ期待' not in ind['prediction_labels']:
                ind.setdefault('prediction_labels', []).append('踏み上げ期待')

    return indicators


def _update_credit_history(root, technical):
    """Store and compare credit_ratio history to detect sudden increases in sell-side.
    Assumes credit_ratio = buy_balance / sell_balance (JPX convention). A sharp drop
    in credit_ratio implies sell balance increased (踏み上げ期待)。
    Stores history under root['credit_history'] as {code: {'last': val, 'ts': 'YYYY-MM-DD HH:MM'}}
    Returns a dict of flags per code: {code: {'delta': float, 'sell_rise': bool, 'notes':[...]}}
    """
    hist = root.setdefault("credit_history", {})
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    flags = {}
    for t in technical:
        code = t.get("code")
        if not code:
            continue
        cur = t.get("credit_ratio")
        prev = None
        entry = hist.get(code)
        if entry and isinstance(entry.get("last"), (int, float)):
            prev = float(entry.get("last"))
        if isinstance(cur, (int, float)):
            hist[code] = {"last": cur, "ts": now}
        # compute change if prev exists
        delta = None
        sell_rise = False
        notes = []
        if prev is not None and isinstance(cur, (int, float)) and prev > 0:
            delta = (cur - prev) / prev
            # if ratio dropped by >=20% -> implies sell-side increased
            if delta <= -0.2:
                sell_rise = True
                notes.append(f"信用倍率が{prev:.2f}→{cur:.2f}に低下(売り残増加の可能性)")
        flags[code] = {"delta": None if delta is None else round(delta, 3), "sell_rise": sell_rise, "notes": notes}
    # persist hist back
    root["credit_history"] = hist
    return flags


def _assess_ir_tone(gemini_key, groq_key, tdnet_items):
    """Use LLM to assess tone of recent TDnet/IR text titles. Returns map by company/code.
    If API keys absent, returns empty dict.
    """
    if not gemini_key and not groq_key:
        return {}
    schema = {
        "type": "OBJECT",
        "properties": {
            "assessments": {"type": "ARRAY", "items": {"type": "OBJECT"}},
        },
        "required": ["assessments"],
    }
    # batch by company: collect recent titles per company
    by_comp = {}
    for it in tdnet_items or []:
        comp = it.get("company") or it.get("code") or it.get("title")
        if not comp:
            continue
        by_comp.setdefault(comp, []).append({"title": it.get("title",""), "url": it.get("url",""), "asof": it.get("time","")})

    out = {}
    for comp, items in by_comp.items():
        prompt = (
            f"以下はある企業の直近TDnet/IR見出しの一覧です。経営者のトーン、文面の自信度、"
            "およびこれらが業績見通しに対してポジティブ/ニュートラル/ネガティブのどれを示唆するかを短く評価してください。"
            "出力はJSONで、'assessments'配列に{name, tone: 'positive|neutral|negative', confidence:0-100, reason: '...'}を入れてください。\n\n"
        )
        prompt += "\n".join([f"- {i['title']} ({i['asof']}) {i['url']}" for i in items[:6]])
        try:
            resp = call_with_fallback(f"IRトーン評価({comp})", "gemini", gemini_key, groq_key, prompt, schema)
            if not resp:
                continue
            assessments = resp.get("assessments") or []
            if assessments:
                a = assessments[0]
                out_key = a.get("name") or comp
                out[out_key] = {"tone": a.get("tone"), "confidence": a.get("confidence"), "reason": a.get("reason")}
        except Exception as e:
            log(f"IRトーン評価失敗({comp}): {e}")
            continue
    return out


def _assess_fx_impact(root, technical):
    """Estimate USD/JPY and export sensitivity. Returns per-code fx_bonus and notes.
    Uses root['fx']['value'] if present. Matches sectors likely to benefit from weaker yen.
    """
    fx_val = None
    fx = root.get("fx") or {}
    val = fx.get("value")
    if isinstance(val, str):
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)", val.replace(",", ""))
        if m:
            try:
                fx_val = float(m.group(1))
            except Exception:
                fx_val = None
    results = {}
    if fx_val is None:
        return results
    # sectors considered exporters
    exporter_keywords = ["輸出", "電気機器", "機械", "輸送用機器", "化学", "精密", "半導体", "素材"]
    # heuristic: if USDJPY is strong (high) and sector matches, give bonus
    for t in technical:
        code = t.get("code")
        if not code:
            continue
        sector = (t.get("sector") or "")
        bonus = 0.0
        notes = []
        for kw in exporter_keywords:
            if kw in sector:
                # stronger yen (higher number) benefits exporters when stock not yet priced in
                if fx_val >= 150:
                    bonus = 12.0
                    notes.append(f"為替({fx_val})で輸出メリット想定")
                break
        results[code] = {"fx_bonus": bonus, "notes": notes}
    return results

# グループA(Gemini担当): 地政学ニュース + 米国株好材料ニュース
GROUP_A_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "news_items": {"type": "ARRAY", "items": NEWS_ITEM_SCHEMA},
        "us_news_items": {"type": "ARRAY", "items": US_NEWS_ITEM_SCHEMA},
    },
    "required": ["news_items", "us_news_items"],
}

# グループB(Groq担当): 値動き話題株 + 織り込み済みリスク + テーマタグ
GROUP_B_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "movers_items": {"type": "ARRAY", "items": MOVERS_ITEM_SCHEMA},
        "tech_risk_items": {"type": "ARRAY", "items": TECH_RISK_ITEM_SCHEMA},
        "theme_items": {"type": "ARRAY", "items": THEME_TAG_ITEM_SCHEMA},
    },
    "required": ["movers_items", "tech_risk_items", "theme_items"],
}


# ---------------- プロンプト構築 ----------------

GROUP_A_INSTRUCTIONS = """あなたは日本株デイトレード情報ダッシュボードの分析担当です。
以下に独立した2つのタスク(タスク1・タスク3)を示します。すべてのタスクを行い、
1つのJSONオブジェクトとして出力してください。出力オブジェクトは必ず次の
2つのキーをすべて持つこと: news_items, us_news_items

- 各キーには、それぞれ対応するタスクの結果(配列)を入れること。
- あるタスクの候補データが「(候補なし)」と書かれている場合、または該当する
  結果が無い場合は、そのキーを空配列 [] にすること(無理に何かを埋めない)。
- 各タスクはそれぞれ独立しており、他のタスクの結果と混同しないこと。

"""

GROUP_B_INSTRUCTIONS = """あなたは日本株デイトレード情報ダッシュボードの分析担当です。
以下に独立した3つのタスク(タスク2・タスク4・タスク5)を示します。すべてのタスクを行い、
1つのJSONオブジェクトとして出力してください。出力オブジェクトは必ず次の
3つのキーをすべて持つこと: movers_items, tech_risk_items, theme_items

- 各キーには、それぞれ対応するタスクの結果(配列)を入れること。
- あるタスクの候補データが「(候補なし)」と書かれている場合、または該当する
  結果が無い場合は、そのキーを空配列 [] にすること(無理に何かを埋めない)。
- 各タスクはそれぞれ独立しており、他のタスクの結果と混同しないこと。

"""

NEWS_RULES = """===== タスク1: news_items =====
以下のGoogle Newsの候補見出し一覧(JSON)から、投資判断の参考情報として価値の高いものを
2〜4件選び、news_items に格納してください。

選定基準:
- 単なる株価コメントや市況の雑感ではなく、地政学リスク・戦争/紛争・制裁・貿易政策・
  中央銀行動向・要人発言など、実際に起きている出来事を報じたニュースを優先する。
- 明らかに重複・類似する内容は1件にまとめる。

各項目には以下も付け加えること(判断が難しい場合は省略してよい。無理にこじつけない):
- investment_sector: その出来事が影響しうる業種・分野を一言で(例:「半導体・AI関連」「エネルギー・資源」「海運」)。
- investment_companies: その分野で特に注目すべき具体的な投資対象企業を2〜3社(会社名、わかれば「会社名(証券コード4桁)」の形式)。
- money_flow: その出来事を受けてどの分野・銘柄群に資金が向かっている/向かうと考えられるかを一文で。
  表現は必ず「〜の傾向がみられる」「〜の可能性がある」「〜に資金が向かうと考えられる」のように、
  「上がります/必ず上昇する」といった断定・確約表現を絶対に使わないこと。
- money_flow_type: money_flowを付けた場合、既に株価反応が出ている実況なら"current"、
  まだ反映されていない見込みなら"expected"。money_flowを付けない場合は空文字でよい。

出力するtitle/url/source/timeは、必ず候補一覧に実際に存在する値をそのまま使うこと(創作しない)。

候補見出し一覧:
"""

MOVERS_RULES = """===== タスク2: movers_items =====
以下のGoogle Newsの候補見出し一覧(JSON)から、本日(または直近)値動き・出来高で
話題になった日本株の個別銘柄を最大5件選び、movers_items に格納してください。

- codeは見出し中に4桁の証券コードが明記されている場合のみ埋める(不明なら空文字)。
- priceやchange_pctは見出しに明記されている場合のみ埋める(不明なら空文字/nullでよい。数値を創作しない)。
- reasonには見出しの内容から「なぜ話題になったか」を一文で(例:「決算好調で急騰」「大型受注観測で商い増加」)。
- 断定的な将来予想("上がります"等)は書かない。客観的な事実描写にする。
- 該当する銘柄が見つからない場合は空配列でよい(無理に埋めない)。

候補見出し一覧:
"""

US_NEWS_RULES = """===== タスク3: us_news_items =====
以下のGoogle News(英語)の候補見出し一覧(JSON)から、直近に報じられた米国株の
明確な好材料ニュースを3〜6件選び、us_news_items に格納してください。

対象とするのは以下の5カテゴリのいずれかに該当するものだけ(それ以外は対象外):
- earnings_beat(市場予想を上回る決算)
- guidance_raise(業績見通し/ガイダンスの上方修正)
- upgrade(証券会社・アナリストによる評価/目標株価の上方修正)
- buyback(大規模な自社株買い発表)
- dividend_hike(増配発表)

headlineには「何が具体的に発表されたか」を一文で(数値が見出しに含まれる場合は含める)。
tickerが見出しから特定できない場合は空文字でよい(推測で作らない)。
該当するニュースが見つからない場合は空配列でよい。

さらに、あなたはプロの機関投資家として「好決算なのに売られる(材料出尽くし)」を
見抜く矛盾分析も行ってください。各項目について:

① 期待値の検証: この見出し(および候補一覧内の関連する他の見出し)の記述だけから、
   市場予想に対する「驚き(サプライズ)」の有無を読み取れるか。
② チャートとの矛盾: 見出し中に「株価は下落」「利益確定売り」「既に上昇していた」
   「発表にもかかわらず売られた」といった、好材料と逆行する株価反応を示す記述が
   あるかを確認する。
③ 結論のラベル化(baked_in_verdict): 見出しの記述だけから判断できる範囲で、以下の
   4段階のいずれかを選ぶこと。チャートを実際に見ているわけではないため、
   見出しに根拠となる記述が無い場合は必ず「判定不能」を選び、無理に断定しないこと。
   - 「本物の初動」: 好材料が強力で、株価反応もそれに素直に連動している記述がある。
   - 「過熱・警戒」: 好材料は良いが、見出し中に「既に上昇していた」「割高感」等、
     織り込み済みを示唆する記述がある。
   - 「材料出尽くし」: 好材料にもかかわらず「株価は下落」「材料出尽くし」等、
     好材料と逆行する株価反応が見出しに明記されている。
   - 「判定不能」: 見出しだけでは判断材料が不足している(このケースが最も多いはずです)。
   baked_in_verdictを「判定不能」以外にする場合は、baked_in_reasonに見出し中の
   具体的な根拠(引用に近い形)を一文で書くこと。「判定不能」の場合はbaked_in_reasonごと
   省略してよい。

候補見出し一覧:
"""

TECH_RISK_RULES = """===== タスク4: tech_risk_items =====
以下は監視銘柄ごとのテクニカル指標(直近5日騰落率・52週高値からの位置など)と、
直近に確認できた好材料(あれば recent_catalyst に記載)をまとめたJSONです。

提供された『直近5日騰落率』と『高値圏までの距離』を確認してください。もし材料が良いにもかかわらず、
既に株価が直近で大幅上昇していたり、52週高値のすぐそばにある場合は、好材料発表が
『絶好の売り場(材料出尽くし)』になるリスクを評価し、tech_risk_items に警告を出してください。

出力ルール:
- warningは、材料出尽くしのリスクが具体的な数値根拠(直近5日騰落率が大きくプラス、または
  高値圏までの距離が数%以内)から明確に読み取れる場合のみtrueにする。判断材料が乏しい/
  通常の値動きの範囲なら必ずfalseにする(無理にこじつけない)。
- reasonには根拠にした具体的な数値(例:「直近5日で+8.2%上昇、52週高値まで1.1%」)を含めて
  一文で書く。warningがfalseの場合は省略してよい。
- 断定的な将来予想("必ず下がる"等)は書かない。あくまでリスク評価であることが分かる表現にする。
- 該当銘柄が無ければ空配列でよい。

対象銘柄一覧:
"""

THEME_RULES = """===== タスク5: theme_items =====
以下は監視銘柄ごとの証券コード・銘柄名・業種・直近の好材料見出し(あれば recent_catalyst)を
まとめたJSON配列です。各銘柄について、該当する投資テーマが明確に読み取れる場合のみ、
theme_items にタグ付けしてください。

出力ルール:
- themeには「半導体」「AI」「データセンター」「防衛」「円安メリット」「インバウンド」
  「電力・再エネ」「資源・エネルギー」のように、テーマ名を一言(10字前後)で書く。
  複数該当する場合は最も強く関連する1つだけを選ぶ。
- 業種名やrecent_catalystの内容から明確にテーマが読み取れない銘柄は、無理にこじつけず
  出力配列に含めないこと(該当銘柄が1つも無ければ空配列でよい)。
- theme_trend_noteには、そのテーマが「今まさに市場で注目されているか」を一文で書く。
  判断材料は、候補一覧内で同じテーマに該当する銘柄が複数あるか(複数あれば市場全体の
  物色テーマとして注目度が高いと考えられる)、recent_catalystの内容が最近の具体的な
  出来事を示しているかなど。根拠が乏しい場合はtheme_trend_noteを省略してよい。
- 断定的な将来予想("上がります"等)は書かない。あくまで現状の傾向描写にする。
- codeは候補一覧に実際に存在する値をそのまま使うこと(創作しない)。

対象銘柄一覧:
"""


def build_task_block(rules, candidates):
    if not candidates:
        return rules + "(候補なし。このタスクは空配列を返すこと)\n\n"
    return rules + json.dumps(candidates, ensure_ascii=False, indent=2) + "\n\n"


# ---------------- メイン処理 ----------------

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    data_path = sys.argv[2] if len(sys.argv) > 2 else "data.json"

    with open(data_path, encoding="utf-8") as f:
        root = json.load(f)

    news_field = "afterclose_news" if mode == "evening" else "overnight_news"
    movers_field = "movers_afterclose" if mode == "evening" else "movers_morning"
    inactive_news_field = "overnight_news" if mode == "evening" else "afterclose_news"
    inactive_movers_field = "movers_morning" if mode == "evening" else "movers_afterclose"

    # 今回の実行対象外の時間帯データも、前回値は使わず「今回未取得」と明記する。
    # Java側で空配列化した状態を保ち、画面上の「更新処理中」表示を残さない。
    set_data_status(root, inactive_news_field, "not_requested", "今回の実行モードでは更新対象外です。")
    set_data_status(root, inactive_movers_field, "not_requested", "今回の実行モードでは更新対象外です。")

    # news_analyzer.pyを単独で実行した場合も含め、前回の分析結果を絶対に流用しない。
    # Java側の生データ(technical)は保持するが、LLM由来の補足フィールドは先に消去する。
    root[news_field] = []
    root[movers_field] = []
    root["us_good_news"] = []
    for technical_item in root.get("technical", []) or []:
        for key in ("baked_in_warning", "baked_in_reason", "theme", "theme_trend_note"):
            technical_item.pop(key, None)

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not gemini_key and not groq_key:
        message = "GEMINI_API_KEY・GROQ_API_KEYともに未設定のため取得できませんでした。"
        mark_unavailable(root, news_field, message)
        mark_unavailable(root, movers_field, message)
        mark_unavailable(root, "us_good_news", message)
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(root, f, ensure_ascii=False, indent=2)
        log(message + " 前回値は消去しました。")
        return

    # ---- 候補データの収集(RSS取得・ローカルデータ整形のみ。API呼び出しはまだ行わない) ----

    news_candidates = []
    try:
        queries = [
            "地政学リスク 市場 影響",
            "中東情勢 原油",
            "米中関係 半導体",
            "日銀 政策 為替",
            "関税 政策 市場",
        ]
        for q in queries:
            try:
                news_candidates.extend(fetch_rss(q, limit=6))
            except Exception as e:
                log(f"RSS取得失敗(query={q!r}): {e}")
    except Exception as e:
        log(f"ニュース候補の収集に失敗しました: {e}")

    mover_candidates = []
    try:
        mover_queries = ["本日 急騰 銘柄", "本日 急落 銘柄", "本日 出来高 ランキング 株"]
        for q in mover_queries:
            try:
                mover_candidates.extend(fetch_rss(q, limit=6))
            except Exception as e:
                log(f"RSS取得失敗(query={q!r}): {e}")
    except Exception as e:
        log(f"値動き話題株候補の収集に失敗しました: {e}")

    us_candidates = []
    try:
        us_queries = [
            "US stocks earnings beat today",
            "stock analyst upgrade price target today",
            "US stock guidance raise",
        ]
        for q in us_queries:
            try:
                us_candidates.extend(fetch_rss(q, hl="en-US", gl="US", ceid="US:en", limit=6))
            except Exception as e:
                log(f"RSS取得失敗(query={q!r}): {e}")
    except Exception as e:
        log(f"米国株好材料候補の収集に失敗しました: {e}")

    technical = root.get("technical", [])
    growth = root.get("growth_candidates", [])
    growth_by_name = {g.get("company"): g for g in growth if g.get("company")}

    tech_candidates = []
    for t in technical:
        ret5d = t.get("ret_5d_pct")
        dist = t.get("high_52w_dist_pct")
        if ret5d is None or dist is None:
            continue
        entry = {
            "code": t.get("code", ""),
            "name": t.get("name", ""),
            "signal": t.get("signal", ""),
            "ret_5d_pct": ret5d,
            "high_52w_dist_pct": dist,
        }
        g = growth_by_name.get(t.get("name"))
        if g:
            entry["recent_catalyst"] = g.get("title", "")
        tech_candidates.append(entry)

    theme_candidates = []
    for t in technical:
        entry = {
            "code": t.get("code", ""),
            "name": t.get("name", ""),
            "sector": t.get("sector", ""),
        }
        g = growth_by_name.get(t.get("name"))
        if g:
            entry["recent_catalyst"] = g.get("title", "")
        theme_candidates.append(entry)

    # ---- グループA(Gemini担当・失敗時はGroqへフォールバック): news_items, us_news_items ----
    group_a_prompt = (
        GROUP_A_INSTRUCTIONS
        + build_task_block(NEWS_RULES, news_candidates)
        + build_task_block(US_NEWS_RULES, us_candidates)
    )
    result_a = call_with_fallback("グループA(ニュース系)", "gemini", gemini_key, groq_key, group_a_prompt, GROUP_A_SCHEMA)

    # ---- グループB(Groq担当・失敗時はGeminiへフォールバック): movers_items, tech_risk_items, theme_items ----
    group_b_prompt = (
        GROUP_B_INSTRUCTIONS
        + build_task_block(MOVERS_RULES, mover_candidates)
        + build_task_block(TECH_RISK_RULES, tech_candidates)
        + build_task_block(THEME_RULES, theme_candidates)
    )
    result_b = call_with_fallback("グループB(値動き・テーマ系)", "groq", gemini_key, groq_key, group_b_prompt, GROUP_B_SCHEMA)

    # ---- 1) 地政学・市場材料ニュース / 3) 米国株好材料ニュース ----
    if result_a is None:
        mark_unavailable(root, news_field, "ニュース分析APIで取得できませんでした。")
        mark_unavailable(root, "us_good_news", "ニュース分析APIで取得できませんでした。")
    else:
        try:
            items = [it for it in result_a.get("news_items", []) if it.get("title") and it.get("url")]
            for it in items:
                if not it.get("money_flow_type"):
                    it.pop("money_flow_type", None)
                if not it.get("investment_sector"):
                    it.pop("investment_sector", None)
                if not it.get("investment_companies"):
                    it.pop("investment_companies", None)
                if not it.get("money_flow"):
                    it.pop("money_flow", None)
            root[news_field] = items
            if items:
                mark_updated(root, news_field)
                log(f"{news_field} を{len(items)}件更新しました。")
            else:
                mark_empty(root, news_field, "取得済み・該当する主要ニュースはありません。")
        except Exception as e:
            root[news_field] = []
            mark_unavailable(root, news_field, "ニュース分析結果を反映できませんでした。")
            log(f"ニュース分析結果の反映に失敗しました: {e}")

        try:
            items = [it for it in result_a.get("us_news_items", []) if it.get("headline") and it.get("category")]
            # ノイズを削ぎ落とす: baked_in_verdict が判定不能の場合は理由が無ければ外す
            for it in items:
                if it.get("baked_in_verdict") in (None, "", "判定不能") or not it.get("baked_in_reason"):
                    it.pop("baked_in_verdict", None)
                    it.pop("baked_in_reason", None)
            # LLM が空だった場合、RSS の見出しを単純ルールで解析して代替出力する
            if not items:
                try:
                    fallback = _heuristic_us_good_from_rss(us_candidates)
                    if fallback:
                        items = fallback
                        log(f"us_good_news: LLM出力が空のためRSSヒューリスティックで{len(items)}件を代替取得しました。")
                except Exception as e:
                    log(f"us_good_news heuristic fallback failed: {e}")

            root["us_good_news"] = items
            if items:
                mark_updated(root, "us_good_news")
                log(f"us_good_news を{len(items)}件更新しました。")
            else:
                mark_empty(root, "us_good_news", "取得済み・該当する米国株好材料はありません。")
        except Exception as e:
            root["us_good_news"] = []
            mark_unavailable(root, "us_good_news", "米国株好材料の分析結果を反映できませんでした。")
            log(f"米国株好材料結果の反映に失敗しました: {e}")

    # ---- 2) 値動き・出来高で話題の銘柄 ----
    if result_b is None:
        mark_unavailable(root, movers_field, "話題株分析APIで取得できませんでした。")
    else:
        try:
            items = [it for it in result_b.get("movers_items", []) if it.get("name") and it.get("reason")]
            root[movers_field] = items
            if items:
                mark_updated(root, movers_field)
                log(f"{movers_field} を{len(items)}件更新しました。")
            else:
                mark_empty(root, movers_field, "取得済み・該当する話題株はありません。")
        except Exception as e:
            root[movers_field] = []
            mark_unavailable(root, movers_field, "話題株分析結果を反映できませんでした。")
            log(f"値動き話題株結果の反映に失敗しました: {e}")

    if result_b is not None:

        # ---- 4) 織り込み済みリスク判定 ----
        try:
            warn_map = {
                it["code"]: it.get("reason", "")
                for it in result_b.get("tech_risk_items", [])
                if it.get("code") and it.get("warning")
            }
            if warn_map:
                for t in technical:
                    code = t.get("code")
                    if code in warn_map:
                        t["baked_in_warning"] = True
                        t["baked_in_reason"] = warn_map[code]
                root["technical"] = technical
                mark_updated(root, "technical")
                log(f"baked-in warning(材料出尽くし警戒)を{len(warn_map)}件付与しました。")
        except Exception as e:
            log(f"織り込み済みリスク判定結果の反映に失敗しました。今回の補足結果は空のままです: {e}")

        # ---- 5) 「テーマ性」の自動タグ付け ----
        try:
            theme_map = {
                it["code"]: it
                for it in result_b.get("theme_items", [])
                if it.get("code") and it.get("theme")
            }
            if theme_map:
                for t in technical:
                    code = t.get("code")
                    if code in theme_map:
                        t["theme"] = theme_map[code]["theme"]
                        note = theme_map[code].get("theme_trend_note")
                        if note:
                            t["theme_trend_note"] = note
                root["technical"] = technical
                mark_updated(root, "technical")
                log(f"投資テーマタグを{len(theme_map)}件付与しました。")
        except Exception as e:
            log(f"投資テーマタグ付け結果の反映に失敗しました。今回の補足結果は空のままです: {e}")

    # ---- 6) 先行指標(決算前シグナル)の算出(決定論的) + 需給/IR/為替の突合 ----
    try:
        # credit history / sell-side increase detection
        credit_flags = _update_credit_history(root, technical)
        # TDnet items for IR tone analysis
        tdnet_items = (root.get("tdnet_morning", []) or []) + (root.get("tdnet_afterclose", []) or [])
        ir_map = _assess_ir_tone(gemini_key, groq_key, tdnet_items)
        fx_map = _assess_fx_impact(root, technical)

        indicators = _compute_pre_earnings_indicator(root, technical, news_candidates, growth)
        # integrate credit/IR/FX into indicators
        for ind in indicators:
            code = ind.get("code")
            name = ind.get("name")
            # credit flags
            if code and code in credit_flags:
                cf = credit_flags[code]
                ind.setdefault("credit_flags", cf)
                if cf.get("sell_rise"):
                    ind["raw_score"] = round(ind.get("raw_score", 0) + 12.0, 2)
                    ind.setdefault("signals", []).insert(0, "売り残増加(踏み上げ期待)")
            # IR tone
            ir_key = None
            if code and code in ir_map:
                ir_key = code
            elif name and name in ir_map:
                ir_key = name
            if ir_key:
                ir = ir_map[ir_key]
                ind.setdefault("ir_tone", ir)
                if ir.get("tone") == "positive":
                    ind["raw_score"] = round(ind.get("raw_score", 0) + 15.0, 2)
                    ind.setdefault("signals", []).append("IR文書のトーン: 強気")
                elif ir.get("tone") == "negative":
                    ind["raw_score"] = round(ind.get("raw_score", 0) - 12.0, 2)
                    ind.setdefault("signals", []).append("IR文書のトーン: 弱気(減点)")
            # FX impact
            if code and code in fx_map and fx_map[code].get("fx_bonus"):
                ind["raw_score"] = round(ind.get("raw_score", 0) + fx_map[code].get("fx_bonus", 0), 2)
                ind.setdefault("signals", []).append("為替追い風")
        # renormalize into 0-100
        for ind in indicators:
            raw = ind.get("raw_score", 0)
            norm = int(max(0, min(100, (raw + 20.0) / 70.0 * 100.0)))
            ind["score"] = norm

        root["pre_earnings_indicator"] = indicators
        if indicators:
            mark_updated(root, "pre_earnings_indicator")
            log(f"pre_earnings_indicator を{len(indicators)}件生成しました。")
        else:
            mark_empty(root, "pre_earnings_indicator", "先行指標の該当銘柄はありませんでした。")
    except Exception as e:
        root["pre_earnings_indicator"] = []
        mark_unavailable(root, "pre_earnings_indicator", "先行指標の算出に失敗しました。")
        log(f"先行指標の算出に失敗しました: {e}")
    # LLM による同業他社波及評価(任意・APIキーがある場合のみ)
    try:
        industry_map = _assess_industry_spillover(gemini_key, groq_key, technical, news_candidates)
        if industry_map:
            # attach results to indicators
            for ind in root.get("pre_earnings_indicator", []):
                key = ind.get("code") or ind.get("name")
                if key in industry_map:
                    ind.setdefault("industry_influence", {}).update(industry_map[key])
            mark_updated(root, "pre_earnings_indicator")
            log(f"pre_earnings_indicator に業種波及評価を付与しました({len(industry_map)}件)。")
    except Exception as e:
        log(f"業種波及評価の付与に失敗しました: {e}")

    # ---- 7) 予測シナリオ(クジラ/踏み上げ/隠れ好業績など)の算出 ----
    try:
        preds = _compute_prediction_scenarios(root.get("pre_earnings_indicator", []), technical, root, news_candidates)
        if preds:
            # merge back
            root["pre_earnings_indicator"] = preds
            mark_updated(root, "pre_earnings_indicator")
            log(f"pre_earnings_indicator に予測シナリオを付与しました({len(preds)}件)。")
    except Exception as e:
        log(f"予測シナリオの算出に失敗しました: {e}")

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)
    log("data.json を書き戻しました。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # パイプラインを停止させない。個別の取得失敗はmain内で空配列と取得不可状態として保存する。
        log(f"予期しないエラー: {e}")
        sys.exit(0)
