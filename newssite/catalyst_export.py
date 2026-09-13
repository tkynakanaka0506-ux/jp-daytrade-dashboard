#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python(Catalyst Intelligence) → 他プロジェクト(Investment Decision Engine) への
データ受け渡し。

【役割分担の原則(2プロジェクト間のAPI境界)】
  この Python プロジェクト = 「何が起きたか」を判定する(FACTUAL LAYER)。
  受け手側(例: 別リポジトリの株価スコアリングシステム) = 「それを踏まえて
  今買う価値があるか」を判断する(そちら独自の UNPRICED/EXPECTATION/
  SURPRISE/TIMING/BUY SCORE 等)。

  ここで書き出す policy_impact_score は「政策材料そのものの強さ」の1シグナル
  でしかない。受け手側の指標(特に UNPRICED=価格の織り込み度)と概念が重複
  しないよう、この関数は一切の統合演算(加算・合成スコア化)を行わない。
  単に「今どの銘柄に、どんな政策材料が、どれくらいの強さである」という
  事実(と、そのスコア)を渡すだけ。

  受け手側で「Policy Impact × Unpriced」のような掛け合わせ判断をする場合、
  それは受け手側の責務であり、このモジュールが決めることではない。
"""
import json
from datetime import datetime
from pathlib import Path

from .config import JST

# 現時点では同じリポジトリ内に書き出すだけ(他プロジェクトへの自動配置はしない)。
# 受け手側でこのファイルを読みに来るかコピーするかは、統合の次段階で決める。
EXPORT_PATH = Path(__file__).resolve().parent / "data" / "policy_catalyst_signals.json"
SCHEMA_VERSION = 1


def build_signals(news_items):
    """news_items(analyze.build_news の出力)から、受け渡し用レコードの配列を作る。

    1レコード = 1(ニュース, 銘柄)。origin="rule"(キーワードルール判定)のみ対象
    (当事者直接言及やLLM補強は、テーマ→銘柄ルールの検証対象外という
    backtest.record_events と同じ理由で除外する)。
    """
    records = []
    for item in news_items:
        # primary_theme: そのニュースが最初にヒットしたテーマ(themes[0])。
        # 複数テーマに一致した場合、各銘柄が実際に紐づいた理由は imp["theme"]
        # (FACTUAL LAYER側で既に確定済み)であり、primary_theme はあくまで
        # 「このニュース全体としての主題」という参考情報。
        themes = item.get("themes") or []
        primary_theme = themes[0] if themes else ""

        for imp in item.get("impacts", []):
            if imp.get("origin") != "rule":
                continue
            records.append({
                "event_id": f"{item['id']}|{imp['code']}",
                "code": imp["code"],
                "name": imp["name"],
                "published_at": item.get("published_at", ""),
                "theme": imp.get("theme", ""),
                "theme_id": imp.get("theme_id"),
                "primary_theme": primary_theme,
                "direction": imp.get("direction", "watch"),
                "tier": imp.get("beneficiary_tier"),
                "policy_maturity": item.get("policy_maturity"),
                "time_horizon": imp.get("revenue_horizon"),
                "policy_impact_score": imp.get("policy_impact_score"),
                "ai_capex_impact_score": imp.get("ai_capex_impact_score"),
                "intelligence_layer": imp.get("intelligence_layer"),
                "policy_to_earnings_stage": imp.get("policy_to_earnings_stage"),
                "matched_keyword": imp.get("matched_keyword"),
                "reason": imp.get("reason", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "news_novelty": item.get("news_novelty"),
                "policy_event_id": item.get("policy_event_id"),
                "policy_event_is_update": item.get("policy_event_is_update", False),
                "source_tier": item.get("source_tier"),
            })
    return records


def build_event_signals(news_items):
    """イベント単位(1ニュース=1レコード)で、紐づく銘柄を stocks 配列にネストした形。

    build_signals() が (ニュース, 銘柄) の1行=1レコードなのに対し、こちらは
    「このニュースが、どの銘柄群に対応するか」を1回のルックアップで
    引けるようにした表現(Phase2で追加。既存の signals は変更しない)。

    注意: 1つのニュースが複数テーマに一致し、銘柄ごとにtheme/direction/
    policy_impact_score が異なることが実際にある(例:「先端半導体への
    政府支援拡大、経済安全保障の観点から…」が防衛テーマと半導体政策
    テーマの両方に一致し、銘柄ごとに理由が違ったケース)。そのため
    トップレベルのtheme/direction/policy_impact_scoreは「代表値
    (最初にヒットしたrule由来impactの値)」であり、銘柄ごとの正確な値は
    必ず stocks[].theme / stocks[].policy_impact_score を見ること
    (トップレベルの値だけを見ると情報が失われる)。
    """
    events = []
    for item in news_items:
        themes = item.get("themes") or []
        primary_theme = themes[0] if themes else ""
        rule_impacts = [imp for imp in item.get("impacts", []) if imp.get("origin") == "rule"]
        if not rule_impacts:
            continue
        top = rule_impacts[0]
        stocks = [
            {
                "code": imp["code"],
                "impact": imp.get("direction", "watch"),
                "tier": imp.get("beneficiary_tier"),
                "theme": imp.get("theme", ""),
                "theme_id": imp.get("theme_id"),
                "policy_impact_score": imp.get("policy_impact_score"),
                "ai_capex_impact_score": imp.get("ai_capex_impact_score"),
                "intelligence_layer": imp.get("intelligence_layer"),
                "policy_to_earnings_stage": imp.get("policy_to_earnings_stage"),
            }
            for imp in rule_impacts
        ]
        events.append({
            # policy_event_id があればそれを使う(=同一政策の続報系列を1つの
            # イベントとして受け手側に見せる)。無ければ従来通りニュースID
            # にフォールバックする(policy_lifecycle未実行の単体テスト等)。
            "event_id": item.get("policy_event_id") or item["id"],
            "policy_event_is_update": item.get("policy_event_is_update", False),
            "policy_event_first_seen": item.get("policy_event_first_seen"),
            "theme": top.get("theme", ""),
            "theme_id": top.get("theme_id"),
            "primary_theme": primary_theme,
            "direction": top.get("direction", "watch"),
            "tier": top.get("beneficiary_tier"),
            "policy_maturity": item.get("policy_maturity"),
            "time_horizon": top.get("revenue_horizon"),
            "policy_impact_score": top.get("policy_impact_score"),
            "ai_capex_impact_score": top.get("ai_capex_impact_score"),
            "intelligence_layer": top.get("intelligence_layer"),
            "policy_to_earnings_stage": top.get("policy_to_earnings_stage"),
            "source_tier": item.get("source_tier"),
            "matched_keyword": top.get("matched_keyword"),
            "reason": top.get("reason", ""),
            "source": item.get("source", ""),
            "url": item.get("url", ""),
            "published_at": item.get("published_at", ""),
            "news_novelty": item.get("news_novelty"),
            "stocks": stocks,
        })
    return events


def export_signals(news_items, out_path=None):
    """今回のビルドで判定した政策材料シグナルをJSONスナップショットとして書き出す。

    追記式(backtest_events.jsonl)ではなく、毎回上書きのスナップショット
    (=「今アクティブな政策材料は何か」)にしてある。過去の履歴が必要なら
    backtest.load_events() 側を使う。

    signals: 1行=1(ニュース,銘柄)のフラットな配列(Phase1、既存のまま)。
    events : 1行=1ニュースで、対応銘柄を stocks 配列にまとめた表現(Phase2で追加)。
    """
    records = build_signals(news_items)
    events = build_event_signals(news_items)
    path = out_path or EXPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "signal_count": len(records),
        "signals": records,
        "event_count": len(events),
        "events": events,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    return len(records)
