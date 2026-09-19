#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI Capex Intelligence(ユーザー提案2026-09-13)の回帰テスト。

「政府・政策が市場を動かす力」(policy_impact_score)と「巨大テックの
設備投資が需要を動かす力」(ai_capex_impact_score)は別物、という方針を
機械的に固定する。実例として、Metaの2026年Q2決算(売上+28%・Capex
310.8億ドル・FCF7.84億ドルまで低下・2026年Capex見通し130〜145億ドル)と、
2026年8月の未成年SNS依存訴訟(最大180億ドル・10年分割・利用時間制限)を
題材にしている。
"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newssite import analyze, impact as impact_mod  # noqa: E402
from newssite.config import JST  # noqa: E402


def _raw_item(id_, title, source="日本経済新聞", source_tier="secondary"):
    return {
        "id": id_, "title": title, "url": f"https://example.com/{id_}",
        "source": source, "source_tier": source_tier, "published": datetime.now(JST),
        "related": [], "feed_category": "tech", "feed_weight": 2, "feed_categories": ["tech"],
    }


class AiCapexThemeMatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = impact_mod.load()

    def _themes(self, title):
        return [t["id"] for t in impact_mod.match_themes(title, self.rules)]

    def test_capex_expansion_headline_matches_ai_capex_cycle(self):
        self.assertIn("ai_capex_cycle", self._themes(
            "メタ、データセンター投資を増額へ 2026年Capex見通しは130〜145億ドル"
        ))

    def test_capex_deceleration_headline_matches_ai_capex_cycle(self):
        self.assertIn("ai_capex_cycle", self._themes(
            "Microsoft、AI設備投資を減額 データセンター投資を延期"
        ))

    def test_capex_deceleration_headline_does_not_also_match_semi_demand(self):
        """semi_demandの『データセンター』が減速系見出しまで誤って拾わないこと
        (④の重複防止と同じ思想: 増額と減額を同じ方向として混同しない)。"""
        themes = self._themes("Microsoft、AI設備投資を減額 データセンター投資を延期")
        self.assertNotIn("semi_demand", themes)

    def test_capex_expansion_headline_may_also_match_semi_demand(self):
        """増額方向は既存semi_demandとも方向が矛盾しないため多重ヒットして良い
        (ALLOWED_KEYWORD_OVERLAPSで確認済み)。"""
        themes = self._themes("メタ、データセンター投資を増額へ")
        self.assertIn("semi_demand", themes)
        self.assertIn("ai_capex_cycle", themes)

    def test_meta_fcf_headline_matches_ai_demand_risk_not_ai_capex_cycle(self):
        """FCF急減はai_capex_cycle(明確な増減シグナル)ではなくai_demand_risk
        (資金負担リスク、単独では需要減速と断定しない弱いシグナル)に分類する。"""
        themes = self._themes("Meta、2026年Q2のFCFが急減 資金調達コストも増加")
        self.assertIn("ai_demand_risk", themes)
        self.assertNotIn("ai_capex_cycle", themes)

    def test_meta_lawsuit_headline_matches_platform_regulation_risk(self):
        themes = self._themes(
            "Metaが未成年SNS依存訴訟で最大180億ドルの支払いに合意、利用時間制限も受諾"
        )
        self.assertIn("platform_regulation_risk", themes)

    def test_california_sns_law_matches_platform_regulation_risk(self):
        themes = self._themes("カリフォルニア州、16歳未満への無限スクロール規制法が成立")
        self.assertIn("platform_regulation_risk", themes)

    def test_platform_regulation_risk_has_no_stock_impacts(self):
        """JP株への受益チェーンが無いテーマなので、impactsは意図的に空にしてある
        (無理に受益銘柄をでっち上げない)。"""
        theme = next(t for t in self.rules.themes if t["id"] == "platform_regulation_risk")
        self.assertEqual(theme.get("impacts", []), [])


class AiCapexScoreSplitTest(unittest.TestCase):
    """policy_impact_scoreとai_capex_impact_scoreが別フィールドとして分離され、
    互いを侵食しないことの確認(ユーザー方針: 2本をMJSまで分離したまま渡す)。"""

    def test_corporate_capex_theme_populates_ai_capex_score_not_policy_score(self):
        news = analyze.build_news(
            raw_items=[_raw_item("c1", "メタ、データセンター投資を増額へ")],
            use_llm=False, persist_lifecycle=False,
        )
        capex_impacts = [i for i in news[0]["impacts"] if i.get("intelligence_layer") == "corporate_capex"]
        self.assertTrue(capex_impacts, "corporate_capexレイヤーの影響銘柄が無い")
        for imp in capex_impacts:
            self.assertIsNone(imp["policy_impact_score"], "corporate_capex由来でpolicy_impact_scoreが埋まっている")
            self.assertIsNotNone(imp["ai_capex_impact_score"])

    def test_government_policy_theme_still_populates_policy_score_not_ai_capex_score(self):
        """既存の政府政策テーマ(防衛費等)は従来通りpolicy_impact_scoreに入り、
        ai_capex_impact_scoreは埋まらない(非侵食の確認)。"""
        news = analyze.build_news(
            raw_items=[_raw_item("g1", "防衛費増額を閣議決定、来年度予算は過去最高に")],
            use_llm=False, persist_lifecycle=False,
        )
        policy_impacts = [i for i in news[0]["impacts"] if i.get("theme_id") == "defense_budget"]
        self.assertTrue(policy_impacts)
        for imp in policy_impacts:
            self.assertIsNotNone(imp["policy_impact_score"])
            self.assertIsNone(imp["ai_capex_impact_score"])
            self.assertEqual(imp["intelligence_layer"], "government_policy")

    def test_ai_demand_risk_direction_is_watch_not_falsely_positive(self):
        """『増加』は資金負担の悪化文脈であり、グローバルなpositive_words『上昇』
        との衝突を避けるためkeywordに意図的に『増加』を使っている
        (『上昇』だとheadline_sentimentが誤ってpositiveに解決してしまう)。"""
        news = analyze.build_news(
            raw_items=[_raw_item("r1", "Meta、2026年Q2のFCFが急減 資金調達コストも増加")],
            use_llm=False, persist_lifecycle=False,
        )
        risk_impacts = [i for i in news[0]["impacts"] if i.get("theme_id") == "ai_demand_risk"]
        self.assertTrue(risk_impacts)
        for imp in risk_impacts:
            self.assertEqual(imp["direction"], "watch", "FCF急減を安易にpositive/negativeと断定してはいけない")


if __name__ == "__main__":
    unittest.main()
