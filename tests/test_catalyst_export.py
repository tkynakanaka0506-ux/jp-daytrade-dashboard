#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""catalyst_export.py の単体テスト。

他プロジェクト(投資判断エンジン側)へのAPI契約なので、スキーマの
フィールド名・型が意図せず変わっていないかを固定するのが目的。
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newssite import catalyst_export  # noqa: E402

REQUIRED_FIELDS = {
    "event_id", "code", "name", "published_at", "theme", "primary_theme",
    "direction", "tier", "policy_maturity", "time_horizon",
    "policy_impact_score", "matched_keyword", "reason", "source", "url",
    "news_novelty", "policy_event_id", "policy_event_is_update", "source_tier",
    "policy_to_earnings_stage", "ai_capex_impact_score", "intelligence_layer",
}


def _news_item():
    return {
        "id": "news-1",
        "url": "https://example.com/a",
        "source": "テスト通信",
        "published_at": "2026-09-13 10:00",
        "themes": ["半導体産業政策・国内投資支援"],
        "policy_maturity": 60,
        "news_novelty": "high",
        "impacts": [
            {
                "code": "8035", "name": "東京エレクトロン", "theme": "半導体産業政策・国内投資支援",
                "direction": "positive", "beneficiary_tier": "direct", "revenue_horizon": "3-6m",
                "policy_impact_score": 88, "matched_keyword": "半導体工場", "reason": "テスト理由",
                "origin": "rule",
            },
            {
                "code": "7203", "name": "トヨタ自動車", "theme": "",
                "direction": "positive", "origin": "direct",
            },
        ],
    }


class CatalystExportTest(unittest.TestCase):
    def test_build_signals_only_includes_rule_origin(self):
        records = catalyst_export.build_signals([_news_item()])
        self.assertEqual(len(records), 1, "originがdirectのimpactは除外されるべき")
        self.assertEqual(records[0]["code"], "8035")

    def test_build_signals_schema_fields(self):
        records = catalyst_export.build_signals([_news_item()])
        self.assertEqual(set(records[0].keys()), REQUIRED_FIELDS)

    def test_build_signals_values_pass_through_unmodified(self):
        records = catalyst_export.build_signals([_news_item()])
        r = records[0]
        self.assertEqual(r["policy_impact_score"], 88, "スコアを書き換えてはいけない(統合演算はしない)")
        self.assertEqual(r["direction"], "positive")
        self.assertEqual(r["tier"], "direct")
        self.assertEqual(r["primary_theme"], "半導体産業政策・国内投資支援")

    def test_build_event_signals_falls_back_to_news_id_without_lifecycle(self):
        events = catalyst_export.build_event_signals([_news_item()])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], "news-1", "policy_event_id未設定なら従来通りニュースIDを使う")
        self.assertFalse(events[0]["policy_event_is_update"])

    def test_build_event_signals_uses_policy_event_id_when_present(self):
        item = _news_item()
        item["policy_event_id"] = "semiconductor_support-20260901-01"
        item["policy_event_is_update"] = True
        item["policy_event_first_seen"] = "2026-09-01"
        events = catalyst_export.build_event_signals([item])
        self.assertEqual(events[0]["event_id"], "semiconductor_support-20260901-01",
                         "policy_event_idがあれば続報系列の識別にそちらを使う")
        self.assertTrue(events[0]["policy_event_is_update"])
        self.assertEqual(events[0]["policy_event_first_seen"], "2026-09-01")

    def test_build_signals_passes_through_policy_event_id(self):
        item = _news_item()
        item["policy_event_id"] = "yen_weak-20260901-01"
        item["policy_event_is_update"] = True
        records = catalyst_export.build_signals([item])
        self.assertEqual(records[0]["policy_event_id"], "yen_weak-20260901-01")
        self.assertTrue(records[0]["policy_event_is_update"])

    def test_build_signals_and_events_pass_through_source_tier(self):
        item = _news_item()
        item["source_tier"] = "commentary"
        records = catalyst_export.build_signals([item])
        self.assertEqual(records[0]["source_tier"], "commentary")
        events = catalyst_export.build_event_signals([item])
        self.assertEqual(events[0]["source_tier"], "commentary")

    def test_build_signals_and_events_pass_through_policy_to_earnings_stage(self):
        item = _news_item()
        item["impacts"][0]["policy_to_earnings_stage"] = "設備投資"
        records = catalyst_export.build_signals([item])
        self.assertEqual(records[0]["policy_to_earnings_stage"], "設備投資")
        events = catalyst_export.build_event_signals([item])
        self.assertEqual(events[0]["policy_to_earnings_stage"], "設備投資")
        self.assertEqual(events[0]["stocks"][0]["policy_to_earnings_stage"], "設備投資")

    def test_export_signals_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "signals.json"
            n = catalyst_export.export_signals([_news_item()], out_path=out_path)
            self.assertEqual(n, 1)
            self.assertTrue(out_path.exists())
            import json
            with open(out_path, encoding="utf-8") as f:
                payload = json.load(f)
            self.assertEqual(payload["schema_version"], catalyst_export.SCHEMA_VERSION)
            self.assertEqual(payload["signal_count"], 1)
            self.assertEqual(len(payload["signals"]), 1)


if __name__ == "__main__":
    unittest.main()
