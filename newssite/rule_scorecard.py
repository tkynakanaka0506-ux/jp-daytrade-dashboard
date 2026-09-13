#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ルールエンジンの判定品質を数値で見るためのスコアカード。

tests/golden_headlines.json を実行し、テーマ判定・方向判定・primary_theme・
理由文の根拠一致を集計する。rules.json をいじった後に

  python3 dev.py score

を実行すれば、「変更したけど本当に精度が上がったのか」を数字で確認できる。
pass/fail の回帰テスト(tests/test_golden_dataset.py)とは別物で、こちらは
落ちても止めない「品質メーター」として使う。
"""
import json
import re
from pathlib import Path

from . import impact as impact_mod
from . import stocks as stocks_mod

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "tests" / "golden_headlines.json"

REASON_KEYWORD_RE = re.compile(r"^「(.+?)」に反応")


def _load_cases():
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return json.load(f)


def run(verbose=True):
    rules = impact_mod.load()
    master = stocks_mod.load()
    cases = _load_cases()

    total = len(cases)
    theme_checks = theme_correct = 0
    misattributions = 0
    direction_checks = direction_correct = 0
    primary_checks = primary_correct = 0
    reason_checks = reason_grounded = 0

    category_fail_counts = {}
    detail_lines = []

    for case in cases:
        title = case["headline"]
        category = case.get("category")
        themes = impact_mod.match_themes(title, rules)
        theme_ids = {t["id"] for t in themes}
        impacts = impact_mod.affected_stocks({"title": title}, themes, rules, master, max_items=8)
        by_code = {i["code"]: i for i in impacts}
        case_failed = False

        if "expected_theme_ids" in case:
            theme_checks += 1
            expected = set(case["expected_theme_ids"])
            if theme_ids == expected:
                theme_correct += 1
            else:
                case_failed = True
                extra = theme_ids - expected
                missing = expected - theme_ids
                if extra:
                    misattributions += 1
                detail_lines.append(
                    f"  [テーマ不一致] {title}\n"
                    f"    期待={sorted(expected)} 実際={sorted(theme_ids)}"
                    f"{' (余分:' + str(sorted(extra)) + ')' if extra else ''}"
                    f"{' (不足:' + str(sorted(missing)) + ')' if missing else ''}"
                )

        for code, expected_dir in case.get("expect_direction", {}).items():
            direction_checks += 1
            actual = by_code.get(code)
            if actual is not None and actual["direction"] == expected_dir:
                direction_correct += 1
            else:
                case_failed = True
                detail_lines.append(
                    f"  [方向不一致] {title}\n"
                    f"    銘柄{code}: 期待={expected_dir} 実際={actual['direction'] if actual else '該当なし'}"
                )

        if "expect_direction_theme_wide" in case:
            direction_checks += 1
            expected_dir = case["expect_direction_theme_wide"]
            rule_impacts = [i for i in impacts if i["origin"] == "rule"]
            if rule_impacts and all(i["direction"] == expected_dir for i in rule_impacts):
                direction_correct += 1
            else:
                case_failed = True
                detail_lines.append(
                    f"  [方向不一致(全体)] {title}\n"
                    f"    期待={expected_dir} 実際={[(i['code'], i['direction']) for i in rule_impacts]}"
                )

        for code in case.get("expected_stocks_present", []):
            if code not in by_code:
                case_failed = True
                detail_lines.append(
                    f"  [表示枠漏れ] {title}\n"
                    f"    銘柄{code}が表示されていない(実際: {[i['code'] for i in impacts]})"
                )

        for earlier, later in case.get("expect_before", []):
            primary_checks += 1
            codes_order = [i["code"] for i in impacts]
            if earlier in codes_order and later in codes_order and (
                codes_order.index(earlier) < codes_order.index(later)
            ):
                primary_correct += 1
            else:
                case_failed = True
                detail_lines.append(
                    f"  [primary_theme不一致] {title}\n"
                    f"    期待順序: {earlier} が {later} より前 / 実際順序: {codes_order}"
                )

        # 理由文の根拠一致(サニティチェック): 「〈キーワード〉に反応」と書かれている
        # 以上、そのキーワードは本当に見出しに含まれているか
        for i in impacts:
            m = REASON_KEYWORD_RE.match(i["reason"])
            if not m:
                continue
            reason_checks += 1
            keyword = m.group(1)
            if all(part in title for part in keyword.split(" ") if part):
                reason_grounded += 1
            else:
                case_failed = True
                detail_lines.append(
                    f"  [理由文不一致] {title}\n"
                    f"    銘柄{i['code']}: 理由文が「{keyword}」を主張しているが見出しに見当たらない"
                )

        if case_failed and category:
            category_fail_counts[category] = category_fail_counts.get(category, 0) + 1

    def pct(correct, checks):
        return f"{correct}/{checks} ({100 * correct / checks:.0f}%)" if checks else "対象なし"

    lines = []
    lines.append("=== ルールエンジン品質スコアカード ===")
    lines.append(f"総ケース数: {total}")
    lines.append(f"テーマ判定正解率: {pct(theme_correct, theme_checks)}")
    lines.append(f"誤帰属率: {misattributions}/{theme_checks} ({100 * misattributions / theme_checks:.0f}%)" if theme_checks else "誤帰属率: 対象なし")
    lines.append(f"方向判定正解率: {pct(direction_correct, direction_checks)}")
    lines.append(f"primary_theme正解率: {pct(primary_correct, primary_checks)}")
    lines.append(f"理由文の根拠一致率: {pct(reason_grounded, reason_checks)}")
    if category_fail_counts:
        lines.append("")
        lines.append("失敗の内訳(カテゴリ別):")
        for cat, n in sorted(category_fail_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: {n}件")
    if detail_lines and verbose:
        lines.append("")
        lines.append("--- 詳細 ---")
        lines.extend(detail_lines)

    report = "\n".join(lines)
    if verbose:
        print(report)
    return report


if __name__ == "__main__":
    run()
