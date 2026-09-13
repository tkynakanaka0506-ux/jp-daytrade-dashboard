#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""policy_lifecycle.py の単体テスト。

ここが壊れると、①(織り込み済み検知)以降の全機能が「同じ政策を何度も
別イベントとして数える」「別の政策を1つに誤って束ねる」という土台の
バグを引きずることになるため、特に念入りに固定する。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newssite import policy_lifecycle  # noqa: E402


def _resolve(registry, theme_id="semiconductor_support", keyword="半導体 支援策",
             maturity=None, title="", day="2026-09-01"):
    return policy_lifecycle.resolve_policy_event_id(
        registry, theme_id=theme_id, matched_keyword=keyword,
        maturity_score=maturity, title=title, day=day,
    )


class PolicyLifecycleTest(unittest.TestCase):
    def test_same_policy_updates_within_window_share_one_id(self):
        """9/1発表→9/3補助金対象→9/8正式決定 は同じpolicy_event_idの更新系列。"""
        registry = {}
        id1, is_update1, _ = _resolve(registry, maturity=20, title="政府が半導体支援策を発表", day="2026-09-01")
        id2, is_update2, _ = _resolve(registry, maturity=35, title="補助金対象企業を発表", day="2026-09-03")
        id3, is_update3, _ = _resolve(registry, maturity=75, title="支援策を正式決定", day="2026-09-08")

        self.assertFalse(is_update1, "最初の1件は新規イベントであるべき")
        self.assertTrue(is_update2)
        self.assertTrue(is_update3)
        self.assertEqual(id1, id2)
        self.assertEqual(id2, id3)

    def test_different_theme_never_merges(self):
        """テーマが違えば同日・同キーワード相当でも別イベント。"""
        registry = {}
        id1, _, _ = _resolve(registry, theme_id="semiconductor_support", day="2026-09-01")
        id2, _, _ = _resolve(registry, theme_id="defense_budget", day="2026-09-01")
        self.assertNotEqual(id1, id2)

    def test_distant_policy_in_same_theme_does_not_merge(self):
        """9/1 半導体支援策 と 10/5 別の半導体支援策(34日後、window=30日超)は別物。"""
        registry = {}
        id1, _, _ = _resolve(registry, maturity=20, title="半導体支援策を発表", day="2026-09-01")
        id2, is_update2, _ = _resolve(registry, maturity=20, title="別の半導体支援策を発表", day="2026-10-05")

        self.assertNotEqual(id1, id2, "LIFECYCLE_WINDOW_DAYSを超えた古い系列に誤って束ねてはいけない")
        self.assertFalse(is_update2)

    def test_maturity_regression_starts_a_new_lifecycle(self):
        """一度「法案成立」まで進んだ後、同じテーマ・窓内で「検討」に戻ったら
        それは続報ではなく新しい政策の一巡目とみなす。"""
        registry = {}
        id1, _, _ = _resolve(registry, maturity=75, title="法案成立", day="2026-09-01")
        id2, is_update2, _ = _resolve(registry, maturity=20, title="別件の検討開始", day="2026-09-10")

        self.assertNotEqual(id1, id2)
        self.assertFalse(is_update2)

    def test_missing_maturity_does_not_block_continuation(self):
        """成熟度キーワードに一致しない続報(Noneのまま)は、判定材料が無いだけ
        なので継続を妨げない。"""
        registry = {}
        id1, _, _ = _resolve(registry, maturity=20, title="半導体支援策を検討", day="2026-09-01")
        id2, is_update2, _ = _resolve(registry, maturity=None, title="半導体支援策の関連報道", day="2026-09-02")
        self.assertEqual(id1, id2)
        self.assertTrue(is_update2)

    def test_same_day_repeat_still_counts_as_update(self):
        registry = {}
        id1, _, _ = _resolve(registry, maturity=20, day="2026-09-01")
        id2, is_update2, _ = _resolve(registry, maturity=20, day="2026-09-01")
        self.assertEqual(id1, id2)
        self.assertTrue(is_update2)

    def test_registry_round_trips_through_disk(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "registry.json"
            registry = policy_lifecycle._load_registry(path)
            id1, _, _ = _resolve(registry, maturity=20, day="2026-09-01")
            policy_lifecycle._save_registry(registry, path)

            reloaded = policy_lifecycle._load_registry(path)
            id2, is_update2, _ = _resolve(reloaded, maturity=35, day="2026-09-03")
            self.assertEqual(id1, id2, "プロセスをまたいでも同じ系列として継続認識できる")
            self.assertTrue(is_update2)

    def test_load_registry_missing_or_corrupt_file_does_not_crash(self):
        missing = policy_lifecycle._load_registry(Path("/nonexistent/registry.json"))
        self.assertEqual(missing, {"active": {}, "_seq": {}})

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "broken.json"
            path.write_text("{not valid json", encoding="utf-8")
            broken = policy_lifecycle._load_registry(path)
            self.assertEqual(broken, {"active": {}, "_seq": {}})


if __name__ == "__main__":
    unittest.main()
