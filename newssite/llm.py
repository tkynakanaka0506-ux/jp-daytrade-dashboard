#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gemini / Groq(いずれも無料枠)による任意の補強処理。

このモジュールは「あると良い」だけの存在で、APIキーが無い・失敗した場合でも
サイトは data/rules.json のルール判定だけで成立する。呼び出し側は戻り値 None を
「補強なし」として扱うこと。
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import UA
from .rss import ssl_context

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

MAX_RETRIES = 3
RETRY_BASE_SEC = 6


def log(msg):
    print(f"[llm] {msg}", flush=True)


def available():
    return bool(os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GROQ_API_KEY", "").strip())


def _post(url, body, headers, timeout=90):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as res:
        return json.loads(res.read().decode("utf-8"))


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
    payload = _post(url, body, {"User-Agent": UA, "Content-Type": "application/json"})
    return json.loads(payload["candidates"][0]["content"]["parts"][0]["text"])


def call_groq(api_key, prompt, schema):
    hint = (
        "\n\n出力は必ず次のJSONスキーマ(キー名)に従うJSONオブジェクトのみとし、"
        "説明文やコードブロック記法(```)は付けないこと:\n"
        + json.dumps(schema, ensure_ascii=False)
    )
    body = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt + hint}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    payload = _post(
        "https://api.groq.com/openai/v1/chat/completions",
        body,
        {"User-Agent": UA, "Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    return json.loads(payload["choices"][0]["message"]["content"])


def call(prompt, schema):
    """Gemini → Groq の順に試し、どちらも駄目なら None を返す。"""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    providers = []
    if gemini_key:
        providers.append(("gemini", lambda: call_gemini(gemini_key, prompt, schema)))
    if groq_key:
        providers.append(("groq", lambda: call_groq(groq_key, prompt, schema)))
    if not providers:
        log("APIキーが未設定のため、ルール判定のみで生成します。")
        return None

    for name, fn in providers:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = fn()
                log(f"{name} で補強に成功しました。")
                return result
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < MAX_RETRIES:
                    wait = RETRY_BASE_SEC * attempt
                    log(f"{name}: HTTP 429 のため {wait} 秒待って再試行します({attempt}/{MAX_RETRIES})")
                    time.sleep(wait)
                    continue
                log(f"{name} 呼び出し失敗: HTTP {e.code}")
                break
            except Exception as e:
                log(f"{name} 呼び出し失敗: {e}")
                break
    log("すべてのプロバイダで失敗しました。ルール判定のみで生成します。")
    return None


ENRICH_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "summary": {"type": "STRING"},
                    "impact_comment": {"type": "STRING"},
                    "importance": {"type": "INTEGER"},
                    "extra_stocks": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "code": {"type": "STRING"},
                                "direction": {"type": "STRING", "enum": ["positive", "negative", "watch"]},
                                "reason": {"type": "STRING"},
                            },
                            "required": ["code", "direction", "reason"],
                        },
                    },
                },
                "required": ["id"],
            },
        }
    },
    "required": ["items"],
}

PROMPT_HEADER = """あなたは日本株の市場ニュース編集者です。以下のニュース見出し一覧(JSON)について、
投資家が「何が起きたか」と「どの銘柄に影響しうるか」を素早くつかめる補足情報を作成してください。

各ニュースについて出力する項目:
- id: 入力のidをそのまま返す(必須)。
- summary: 見出しから読み取れる事実を1文(60字程度)で要約する。見出しに書かれていない
  事実を創作しないこと。読み取れない場合は空文字にする。
- impact_comment: そのニュースが日本株のどの分野の需給・業績見通しに効きうるかを1〜2文で。
  「上がります」「必ず下落する」のような断定・確約表現は絶対に使わず、
  「〜の可能性がある」「〜が意識されやすい」といった表現にすること。
- importance: 日本株市場全体へのインパクトを1〜5の整数で(5が最重要)。
- extra_stocks: 候補銘柄リスト(candidate_stocks)の中から、そのニュースで特に意識されやすい
  銘柄を最大3件選ぶ。codeは必ず候補リストに存在する4桁コードを使い、存在しないコードを
  作らないこと。reasonは「なぜその銘柄に効くか」を40字程度で書く。該当が無ければ空配列。

注意: あなたは投資助言をしてはならない。事実と一般的な連想の説明にとどめること。

ニュース一覧:
"""


def enrich(news_items, candidate_stocks):
    """news_items に summary / impact_comment / extra_stocks を足すための呼び出し。

    失敗しても例外を投げず None を返す。
    """
    if not news_items:
        return None
    payload = {
        "news": [
            {
                "id": n["id"],
                "title": n["title"],
                "source": n.get("source", ""),
                "category": n.get("category", ""),
                "themes": n.get("themes", []),
                "rule_stocks": [i["code"] for i in n.get("impacts", [])],
            }
            for n in news_items
        ],
        "candidate_stocks": candidate_stocks,
    }
    prompt = PROMPT_HEADER + json.dumps(payload, ensure_ascii=False, indent=1)
    return call(prompt, ENRICH_SCHEMA)
