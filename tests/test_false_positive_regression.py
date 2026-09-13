#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑥ false_positive_log.json の回帰テスト。

tests/golden_headlines.json が「期待する正しい挙動」を幅広く固定するのに
対し、こちらは「過去に実際キーワードルールを誤爆させた見出しと、その原因・
修正内容」を1件1レコードで構造化して残す(ゴールデンデータセットの
「悪い例版」)。今後rules.jsonのキーワードを変更するたびに、過去の誤爆が
再発していないかをここで機械的に確認できる。

各レコードのフィールド:
  headline      : 実際に誤爆した(または誤爆しかけた)見出し
  wrong_theme   : 誤って一致してしまったテーマid(一致すべきでない。nullなら
                  「そもそも何のテーマにも一致すべきでない」ケース)
  correct_theme : 本来一致すべきテーマid(nullなら「無一致が正解」)
  cause         : なぜ誤爆したか
  fix           : 何を直したか(rules.json側の変更内容)
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newssite import impact as impact_mod  # noqa: E402

LOG_PATH = Path(__file__).resolve().parent / "false_positive_log.json"

REQUIRED_FIELDS = {"headline", "wrong_theme", "correct_theme", "cause", "fix"}


class FalsePositiveLogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = impact_mod.load()
        with open(LOG_PATH, encoding="utf-8") as f:
            cls.cases = json.load(f)

    def test_log_entries_have_required_fields(self):
        for case in self.cases:
            missing = REQUIRED_FIELDS - set(case.keys())
            self.assertFalse(missing, f"false_positive_log.jsonのレコードにフィールド不足: {missing} ({case.get('headline')})")

    def test_wrong_theme_does_not_reproduce(self):
        failures = []
        for case in self.cases:
            if case["wrong_theme"] is None:
                continue
            theme_ids = [t["id"] for t in impact_mod.match_themes(case["headline"], self.rules)]
            if case["wrong_theme"] in theme_ids:
                failures.append(
                    f"[再発] {case['headline']}\n"
                    f"  誤爆テーマ「{case['wrong_theme']}」が再び一致した(実際: {theme_ids})\n"
                    f"  原因: {case['cause']}\n  過去の修正: {case['fix']}"
                )
        self.assertEqual([], failures, "\n\n" + "\n\n".join(failures))

    def test_correct_theme_still_matches(self):
        """誤爆防止のためのexclude強化で、正当なケースまで消していないかの確認。"""
        failures = []
        for case in self.cases:
            if case["correct_theme"] is None:
                continue
            theme_ids = [t["id"] for t in impact_mod.match_themes(case["headline"], self.rules)]
            if case["correct_theme"] not in theme_ids:
                failures.append(
                    f"[過剰除外] {case['headline']}\n"
                    f"  本来一致すべきテーマ「{case['correct_theme']}」が一致しなくなった(実際: {theme_ids})"
                )
        self.assertEqual([], failures, "\n\n" + "\n\n".join(failures))


if __name__ == "__main__":
    unittest.main()
