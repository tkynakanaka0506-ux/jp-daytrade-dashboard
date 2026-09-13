#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Policy Impact Score バックテスト基盤。

今回のセッションの結論は「スコアが無効」ではなく「今のデータでは未検証」。
これを継続的に検証可能にするため、本番ビルド(analyze.build)のたびに
「その時点でのニュース×銘柄×スコア」をイベントログへ追記していく。
株価データは現時点では接続していない(152銘柄分の日次終値フィードは
別プロジェクト範囲、と判断して意図的に後回しにしている)。

ログが十分に溜まった時点で、別途 価格テーブル(date, code, close) を
用意すれば、このイベントログと突き合わせて T+1/T+5/T+20 のバックテストが
そのまま実行できる設計にしてある。

[PRESENTATION LAYER] ここで記録する内容はあくまで検証用の記録であり、
theme/direction/direct-indirect の判定(FACTUAL LAYER)には一切使わない。
"""
import json
from datetime import datetime
from pathlib import Path

from .config import JST

EVENTS_LOG_PATH = Path(__file__).resolve().parent / "data" / "backtest_events.jsonl"
MIN_N_FOR_VERDICT = 10


def record_events(news_items, generated_at=None):
    """今回のビルドで判定したニュース×銘柄イベントをログに追記する。

    同じニュースID×銘柄コードの組は既にログにあれば追記しない
    (毎回のビルドで同じ直近ニュースが何度も再取得されるため、
    バックテストv2で踏んだ「同一イベントの日またぎ重複」を最初から防ぐ)。

    origin="rule"(キーワードルールによる判定)のみを記録する。
    "direct"(見出しに名指しされた当事者)と"llm"(AI補強による追加銘柄)は、
    このバックテストが検証したいのは「テーマ→銘柄ルールの精度」であり、
    どちらもルールエンジンの判定結果ではないため対象外にしている。
    """
    day = (generated_at or datetime.now(JST)).strftime("%Y-%m-%d")
    existing_keys = _load_existing_keys()

    new_rows = []
    for item in news_items:
        for imp in item.get("impacts", []):
            if imp.get("origin") != "rule":
                continue  # 当事者(direct)は「ニュースの銘柄紐付けルール」の検証対象外
            key = f"{item['id']}|{imp['code']}"
            if key in existing_keys:
                continue
            new_rows.append({
                "event_key": key,
                "day": day,
                "news_id": item["id"],
                "title": item["title"],
                "code": imp["code"],
                "name": imp["name"],
                "theme": imp.get("theme", ""),
                "direction": imp.get("direction", "watch"),
                "policy_impact_score": imp.get("policy_impact_score"),
                "beneficiary_tier": imp.get("beneficiary_tier"),
                "revenue_horizon": imp.get("revenue_horizon"),
            })

    if not new_rows:
        return 0

    EVENTS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_LOG_PATH, "a", encoding="utf-8") as f:
        for row in new_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(new_rows)


def _load_existing_keys():
    if not EVENTS_LOG_PATH.exists():
        return set()
    keys = set()
    with open(EVENTS_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                keys.add(json.loads(line)["event_key"])
            except (json.JSONDecodeError, KeyError):
                continue
    return keys


def load_prior_titles(before_day):
    """before_day より前の日に記録されたニュース見出しの一覧を返す。

    News Novelty(新規性)判定に使う: 過去に似た見出しが記録されていれば
    「続報・再報道」の可能性が高いと判断する材料にする。
    """
    if not EVENTS_LOG_PATH.exists():
        return []
    titles = []
    with open(EVENTS_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("day", "") < before_day:
                titles.append(row.get("title", ""))
    return titles


def load_events():
    if not EVENTS_LOG_PATH.exists():
        return []
    events = []
    with open(EVENTS_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def compute_status(price_lookup=None):
    """BACKTEST_STATUS を診断情報つきで返す。

    price_lookup: (day, code) -> close を返せる callable。未指定なら
    「価格データ未接続」として INSUFFICIENT_DATA を返す
    (今は意図的に未接続。152銘柄分の日次終値フィードは別プロジェクト)。
    """
    events = load_events()
    unique_days = len(set(e["day"] for e in events))
    unique_codes = len(set(e["code"] for e in events))

    if price_lookup is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": "価格データ未接続(152銘柄分の日次終値フィードが無いため)",
            "unique_events": len(events),
            "unique_days": unique_days,
            "unique_codes": unique_codes,
            "price_coverage": 0,
            "valid_forward_returns": {"t5": 0, "t20": 0},
            "score_band_n": {},
        }

    # 価格データが将来接続された場合の集計ロジック(現状は price_lookup=None のため未使用)
    band_defs = [(80, 101, "80-100"), (70, 80, "70-79"), (60, 70, "60-69"), (50, 60, "50-59"), (0, 50, "<50")]

    def band_of(score):
        if score is None:
            return None
        for lo, hi, label in band_defs:
            if lo <= score < hi:
                return label
        return None

    band_n = {label: 0 for _, _, label in band_defs}
    valid_t5 = valid_t20 = 0
    priced_codes = set()
    for e in events:
        label = band_of(e.get("policy_impact_score"))
        if label:
            band_n[label] += 1
        if price_lookup(e["day"], e["code"]) is not None:
            priced_codes.add(e["code"])

    insufficient_bands = [label for label, n in band_n.items() if n < MIN_N_FOR_VERDICT]
    status = "INSUFFICIENT_DATA" if len(insufficient_bands) == len(band_n) else "PARTIAL"

    return {
        "status": status,
        "reason": f"N不足の帯: {insufficient_bands}" if insufficient_bands else "全帯でN充足",
        "unique_events": len(events),
        "unique_days": unique_days,
        "unique_codes": unique_codes,
        "price_coverage": len(priced_codes),
        "valid_forward_returns": {"t5": valid_t5, "t20": valid_t20},
        "score_band_n": band_n,
    }


def print_status():
    status = compute_status()
    print("=== BACKTEST_STATUS ===")
    print(f"status: {status['status']}")
    print(f"reason: {status['reason']}")
    print(f"蓄積イベント数: {status['unique_events']} (日数: {status['unique_days']}, 銘柄数: {status['unique_codes']})")
    print(f"価格データ接続: {'あり' if status['price_coverage'] else 'なし'}")
    if status["unique_events"] > 0:
        print(f"\n次にやること: 152銘柄分の日次終値が接続でき次第、"
              f"compute_status(price_lookup=...) にルックアップ関数を渡せばそのまま集計される。")
