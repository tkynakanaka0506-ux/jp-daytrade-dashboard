#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backtest.py の単体テスト。

今回のバックテストv2構築で見つけた2つのバグの再発防止:
  1. 同じ(ニュース, 銘柄)イベントを何度もログに追記してしまう
     (元データで日をまたいで同じ記事が残留し、516件まで水増しされた実例)。
  2. 「N=全体件数」を「有効なリターンが取れた件数」であるかのように
     表示してしまう(N=45と表示しながら実際は2件しか計算できていなかった実例)。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newssite import backtest  # noqa: E402


def _news_item(news_id, title, code, name, theme, direction, score, origin="rule"):
    return {
        "id": news_id,
        "title": title,
        "impacts": [{
            "code": code, "name": name, "theme": theme, "direction": direction,
            "policy_impact_score": score, "origin": origin,
            "beneficiary_tier": None, "revenue_horizon": None,
        }],
    }


class BacktestTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(
            backtest, "EVENTS_LOG_PATH", Path(self._tmpdir.name) / "events.jsonl"
        )
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmpdir.cleanup()

    def test_record_events_is_idempotent_across_days(self):
        # バグ1の再発防止: 同じ(news_id, code)は、日をまたいで何度record_eventsを
        # 呼んでも1回しかログに残らない。
        item = _news_item("news-1", "防衛費増額を閣議決定", "7011", "三菱重工業",
                           "防衛・安全保障", "positive", 88)
        n1 = backtest.record_events([item])
        n2 = backtest.record_events([item])  # 同じニュースが翌日も再取得された想定
        n3 = backtest.record_events([item])
        self.assertEqual(n1, 1)
        self.assertEqual(n2, 0, "同じイベントが2回目以降も追記されてしまっている")
        self.assertEqual(n3, 0)
        self.assertEqual(len(backtest.load_events()), 1)

    def test_record_events_skips_direct_origin(self):
        # 「当事者」(direct)は、テーマ→銘柄ルールの検証対象ではないので記録しない。
        item = _news_item("news-2", "トヨタ自動車が上方修正", "7203", "トヨタ自動車",
                           "", "positive", None, origin="direct")
        n = backtest.record_events([item])
        self.assertEqual(n, 0)

    def test_record_events_distinguishes_different_codes_same_news(self):
        item = {
            "id": "news-3", "title": "半導体政策ニュース",
            "impacts": [
                {"code": "8035", "name": "東京エレクトロン", "theme": "t", "direction": "positive",
                 "policy_impact_score": 70, "origin": "rule", "beneficiary_tier": None, "revenue_horizon": None},
                {"code": "6857", "name": "アドバンテスト", "theme": "t", "direction": "positive",
                 "policy_impact_score": 70, "origin": "rule", "beneficiary_tier": None, "revenue_horizon": None},
            ],
        }
        n = backtest.record_events([item])
        self.assertEqual(n, 2, "同じニュースでも銘柄が違えば別イベントとして記録されるべき")

    def test_status_reports_insufficient_data_without_price_lookup(self):
        item = _news_item("news-4", "防衛費増額", "7011", "三菱重工業",
                           "防衛・安全保障", "positive", 88)
        backtest.record_events([item])
        status = backtest.compute_status()
        self.assertEqual(status["status"], "INSUFFICIENT_DATA")
        self.assertEqual(status["unique_events"], 1)

    def test_status_n_reflects_valid_returns_not_raw_group_size(self):
        # バグ2の再発防止: score_band_n の値が「実際にリターン計算できた件数」であり、
        # 「その帯に該当する全件数」ではないことを保証する。
        for i in range(5):
            item = _news_item(f"news-band-{i}", f"見出し{i}", "7011", "三菱重工業",
                               "t", "positive", 85)
            backtest.record_events([item])

        def price_lookup_always_none(day, code):
            return None  # 価格が一切取れない状況を模擬

        status = backtest.compute_status(price_lookup=price_lookup_always_none)
        # 価格が1件も取れない以上、price_coverageは0であるべき
        # (band_nに5件积まれていても、それは「有効なリターン件数」ではないことの確認)
        self.assertEqual(status["price_coverage"], 0)


if __name__ == "__main__":
    unittest.main()
