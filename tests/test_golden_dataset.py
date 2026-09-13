#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""実際のニュース検証で見つけたバグの再発防止用ゴールデンデータセット。

tests/golden_headlines.json の各見出しをパイプラインに通し、期待した
テーマ・方向・銘柄になっているかを確認する。rules.json をいじるたびに
「前に直したWPS問題が再発していないか」を自動で検出するのが目的。
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newssite import impact as impact_mod, stocks as stocks_mod  # noqa: E402

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_headlines.json"


class GoldenDatasetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = impact_mod.load()
        cls.master = stocks_mod.load()
        with open(GOLDEN_PATH, encoding="utf-8") as f:
            cls.cases = json.load(f)

    def test_golden_headlines(self):
        failures = []
        for case in self.cases:
            title = case["headline"]
            themes = impact_mod.match_themes(title, self.rules)
            theme_ids = [t["id"] for t in themes]
            impacts = impact_mod.affected_stocks(
                {"title": title}, themes, self.rules, self.master, max_items=8
            )
            by_code = {i["code"]: i for i in impacts}

            if "expected_theme_ids" in case:
                if set(case["expected_theme_ids"]) != set(theme_ids):
                    failures.append(
                        f"[{case['note']}]\n  見出し: {title}\n"
                        f"  期待テーマ: {case['expected_theme_ids']} / 実際: {theme_ids}"
                    )

            for code, expected_dir in case.get("expect_direction", {}).items():
                actual = by_code.get(code)
                if actual is None:
                    failures.append(
                        f"[{case['note']}]\n  見出し: {title}\n"
                        f"  銘柄{code}が影響銘柄に含まれていない(期待方向:{expected_dir})"
                    )
                elif actual["direction"] != expected_dir:
                    failures.append(
                        f"[{case['note']}]\n  見出し: {title}\n"
                        f"  銘柄{code}の方向: 期待={expected_dir} / 実際={actual['direction']}"
                    )

            if "expect_direction_theme_wide" in case:
                expected = case["expect_direction_theme_wide"]
                wrong = [
                    (i["code"], i["name"], i["direction"])
                    for i in impacts
                    if i["origin"] == "rule" and i["direction"] != expected
                ]
                if wrong:
                    failures.append(
                        f"[{case['note']}]\n  見出し: {title}\n"
                        f"  全銘柄が{expected}になるはずが、一致しないもの: {wrong}"
                    )

            for code in case.get("expected_stocks_present", []):
                if code not in by_code:
                    failures.append(
                        f"[{case['note']}]\n  見出し: {title}\n"
                        f"  銘柄{code}が表示枠に含まれていない"
                        f"(実際の銘柄: {[i['code'] for i in impacts]})"
                    )

        self.assertEqual([], failures, "\n\n" + "\n\n".join(failures))


if __name__ == "__main__":
    unittest.main()
