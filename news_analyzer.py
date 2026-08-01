#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini API(無料枠)を使って、data.json のうち「話題性・重要度の判断」が必要な
以下のフィールドだけを補完するスクリプト。他の決定論的なフィールド(市場指数・
TDnet開示・テクニカル指標)は Main.java が担当し、このスクリプトはそのあとに実行する。

  - overnight_news / afterclose_news (地政学・市場材料ニュース)
  - us_good_news (米国株の好材料ニュース。見出しテキストから読み取れる範囲で、
    「好決算なのに売られる(材料出尽くし)」を示す記述が無いかの簡易矛盾分析も行う)
  - movers_morning / movers_afterclose (値動き・出来高で話題の銘柄)

設計方針:
  - ニュースの"取得"自体は Google News RSS(無料・APIキー不要)で行う。
  - "どれが重要か・どの分野/銘柄に関連するか"という主観的判断だけを
    Gemini API(無料枠、1日1000リクエストまで無料)に1回〜数回のリクエストで依頼する。
  - GEMINI_API_KEY が未設定、またはネットワーク/API呼び出しが失敗した場合は、
    既存の data.json の値をそのまま保持し、正常終了する(exit code 0)。
    このスクリプトの失敗でパイプライン全体(Java取得・HTML生成・push)を
    止めないことを最優先する。

使い方: python3 news_analyzer.py <morning|evening> <data.jsonのパス>
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (compatible; jp-daytrade-dashboard-bot/1.0)"
GEMINI_MODEL = "gemini-2.5-flash-lite"


def log(msg):
    print(f"[news_analyzer] {msg}", file=sys.stderr)


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
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        payload = json.loads(res.read().decode("utf-8"))
    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


# ---------------- スキーマ定義(Gemini responseSchema) ----------------

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
        "money_flow_type": {"type": "STRING", "enum": ["current", "expected", ""]},
    },
    "required": ["title", "url", "source", "time"],
}

NEWS_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"items": {"type": "ARRAY", "items": NEWS_ITEM_SCHEMA}},
    "required": ["items"],
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

MOVERS_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"items": {"type": "ARRAY", "items": MOVERS_ITEM_SCHEMA}},
    "required": ["items"],
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
        # ---- 「好材料の織り込み済み(材料出尽くし)」矛盾分析(任意項目) ----
        # 見出しテキストのみから読み取れる範囲での推定であり、実際のチャートを
        # 参照した判定ではない。根拠が乏しい場合は両方省略してよい(無理にこじつけない)。
        "baked_in_verdict": {
            "type": "STRING",
            "enum": ["本物の初動", "過熱・警戒", "材料出尽くし", "判定不能"],
        },
        "baked_in_reason": {"type": "STRING"},
    },
    "required": ["ticker", "company", "category", "headline", "url"],
}

US_NEWS_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"items": {"type": "ARRAY", "items": US_NEWS_ITEM_SCHEMA}},
    "required": ["items"],
}


# ---------------- プロンプト構築 ----------------

NEWS_RULES = """あなたは日本株デイトレード情報ダッシュボードのニュース選定担当です。
以下のGoogle Newsの候補見出し一覧(JSON)から、投資判断の参考情報として価値の高いものを
2〜4件選び、指定のJSON形式で出力してください。

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

MOVERS_RULES = """あなたは日本株デイトレード情報ダッシュボードの「値動き・出来高で話題の銘柄」選定担当です。
以下のGoogle Newsの候補見出し一覧(JSON)から、本日(または直近)値動き・出来高で
話題になった日本株の個別銘柄を最大5件選び、指定のJSON形式で出力してください。

- codeは見出し中に4桁の証券コードが明記されている場合のみ埋める(不明なら空文字)。
- priceやchange_pctは見出しに明記されている場合のみ埋める(不明なら空文字/nullでよい。数値を創作しない)。
- reasonには見出しの内容から「なぜ話題になったか」を一文で(例:「決算好調で急騰」「大型受注観測で商い増加」)。
- 断定的な将来予想("上がります"等)は書かない。客観的な事実描写にする。
- 該当する銘柄が見つからない場合は空配列でよい(無理に埋めない)。

候補見出し一覧:
"""

US_NEWS_RULES = """あなたは日本株デイトレード情報ダッシュボードの「米国株の好材料ニュース」選定担当です。
以下のGoogle News(英語)の候補見出し一覧(JSON)から、直近に報じられた米国株の
明確な好材料ニュースを3〜6件選び、指定のJSON形式で出力してください。

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


def build_prompt(rules, candidates):
    return rules + json.dumps(candidates, ensure_ascii=False, indent=2)


# ---------------- メイン処理 ----------------

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    data_path = sys.argv[2] if len(sys.argv) > 2 else "data.json"

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        log("GEMINI_API_KEY未設定のため、ニュース系フィールドの更新をスキップします(既存値を保持)。")
        return

    with open(data_path, encoding="utf-8") as f:
        root = json.load(f)

    news_field = "afterclose_news" if mode == "evening" else "overnight_news"
    movers_field = "movers_afterclose" if mode == "evening" else "movers_morning"

    # ---- 1) 地政学・市場材料ニュース ----
    try:
        queries = [
            "地政学リスク 市場 影響",
            "中東情勢 原油",
            "米中関係 半導体",
            "日銀 政策 為替",
            "関税 政策 市場",
        ]
        candidates = []
        for q in queries:
            try:
                candidates.extend(fetch_rss(q, limit=6))
            except Exception as e:
                log(f"RSS取得失敗(query={q!r}): {e}")
        if candidates:
            result = call_gemini(api_key, build_prompt(NEWS_RULES, candidates), NEWS_RESPONSE_SCHEMA)
            items = [it for it in result.get("items", []) if it.get("title") and it.get("url")]
            if items:
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
                log(f"{news_field} を{len(items)}件更新しました。")
        else:
            log("ニュース候補が0件のため、newsフィールドはスキップします。")
    except Exception as e:
        log(f"ニュース分析ステップが失敗しました(既存値を保持): {e}")

    # ---- 2) 値動き・出来高で話題の銘柄 ----
    try:
        mover_queries = ["本日 急騰 銘柄", "本日 急落 銘柄", "本日 出来高 ランキング 株"]
        mover_candidates = []
        for q in mover_queries:
            try:
                mover_candidates.extend(fetch_rss(q, limit=6))
            except Exception as e:
                log(f"RSS取得失敗(query={q!r}): {e}")
        if mover_candidates:
            result = call_gemini(api_key, build_prompt(MOVERS_RULES, mover_candidates), MOVERS_RESPONSE_SCHEMA)
            items = [it for it in result.get("items", []) if it.get("name") and it.get("reason")]
            if items:
                root[movers_field] = items
                log(f"{movers_field} を{len(items)}件更新しました。")
    except Exception as e:
        log(f"値動き話題株ステップが失敗しました(既存値を保持): {e}")

    # ---- 3) 米国株の好材料ニュース ----
    try:
        us_queries = [
            "US stocks earnings beat today",
            "stock analyst upgrade price target today",
            "US stock guidance raise",
        ]
        us_candidates = []
        for q in us_queries:
            try:
                us_candidates.extend(fetch_rss(q, hl="en-US", gl="US", ceid="US:en", limit=6))
            except Exception as e:
                log(f"RSS取得失敗(query={q!r}): {e}")
        if us_candidates:
            result = call_gemini(api_key, build_prompt(US_NEWS_RULES, us_candidates), US_NEWS_RESPONSE_SCHEMA)
            items = [it for it in result.get("items", []) if it.get("headline") and it.get("category")]
            if items:
                for it in items:
                    # 「判定不能」または理由が無いものは、不確かな警告を出さないよう
                    # フィールドごと落とす(空文字のbaked_in_verdictも同様に扱う)。
                    if it.get("baked_in_verdict") in (None, "", "判定不能") or not it.get("baked_in_reason"):
                        it.pop("baked_in_verdict", None)
                        it.pop("baked_in_reason", None)
                root["us_good_news"] = items
                log(f"us_good_news を{len(items)}件更新しました。")
    except Exception as e:
        log(f"米国株好材料ステップが失敗しました(既存値を保持): {e}")

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)
    log("data.json を書き戻しました。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # このスクリプトの失敗でパイプライン全体を止めない
        log(f"予期しないエラー(既存data.jsonは変更せず終了します): {e}")
        sys.exit(0)
