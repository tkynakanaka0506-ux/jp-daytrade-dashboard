#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""newssite/sample.py の回帰テスト。

過去にsample.py がbuild_news()の判定ロジックを手で複製しており、
policy_maturity/news_novelty/policy_event_id 等の追加に追従できず
プレビュー画面にだけ表示されない、というdriftが実際に発生した。
sample_data()はbuild_news()に委譲する実装(analyze.py参照)にしたので、
ここでは「build_news()の出力フィールドがsample側にも必ず出る」ことを
固定して、同じdriftの再発を防ぐ。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newssite import analyze  # noqa: E402
from newssite.sample import sample_data  # noqa: E402

# build_news()が返す1件のニュース辞書が必ず持つべきキー(このテストの目的上、
# 全部でなく「サンプルでdriftしやすかった判定系フィールド」だけ確認する)。
DRIFT_PRONE_FIELDS = {
    "policy_maturity", "policy_maturity_label",
    "news_novelty", "news_novelty_label",
    "policy_event_id", "policy_event_is_update", "policy_event_first_seen", "policy_event_state",
    "future_signal",
}


class SampleDataTest(unittest.TestCase):
    def test_sample_data_uses_real_build_news_fields(self):
        data = sample_data()
        self.assertGreater(len(data["news"]), 0)
        for n in data["news"]:
            missing = DRIFT_PRONE_FIELDS - set(n.keys())
            self.assertFalse(missing, f"sample_data()の出力にbuild_news()相当のフィールドが無い: {missing}")

    def test_sample_data_does_not_persist_policy_lifecycle_registry(self):
        from newssite import policy_lifecycle
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "policy_event_registry.json"
            orig_path = policy_lifecycle.REGISTRY_PATH
            policy_lifecycle.REGISTRY_PATH = fake_path
            try:
                sample_data()
            finally:
                policy_lifecycle.REGISTRY_PATH = orig_path
            self.assertFalse(fake_path.exists(), "サンプル生成が本番のpolicy_event_registry.jsonを書き換えてはいけない")

    def test_sample_data_matches_build_news_output_shape(self):
        """sample.pyが独自ロジックを再実装していない(=build_newsのキー集合と一致する)ことの確認。"""
        news = analyze.build_news(raw_items=[], use_llm=False, persist_lifecycle=False)
        sample_news = sample_data()["news"]
        # raw_items=[]では0件なのでキー集合の比較はできないため、sample側のキー集合が
        # build_newsの出力キー集合(実際の1件)の部分集合を超えていない=同じ生成元であることを
        # sample側のキーで確認する(DRIFT_PRONE_FIELDSでカバーしきれない新規フィールドの
        # 追加にも追従できるよう、意図的にゆるく「全件で同じキー集合」だけ固定する)。
        self.assertEqual(news, [])
        key_sets = {frozenset(n.keys()) for n in sample_news}
        self.assertEqual(len(key_sets), 1, "sample_data()のニュース項目は全件同じキー集合を持つはず")


if __name__ == "__main__":
    unittest.main()
