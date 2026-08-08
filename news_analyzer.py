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
    with urllib.request.urlopen(req, timeout=20) as res:
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
            with urllib.request.urlopen(req, timeout=90) as res:
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
            with urllib.request.urlopen(req, timeout=90) as res:
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
            for it in items:
                if it.get("baked_in_verdict") in (None, "", "判定不能") or not it.get("baked_in_reason"):
                    it.pop("baked_in_verdict", None)
                    it.pop("baked_in_reason", None)
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
