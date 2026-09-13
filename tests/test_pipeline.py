#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ニュースサイト生成の主要ロジックのテスト。

  python3 -m unittest discover -s tests -v

ネットワークには接続せず、RSS取得部分はローカルのXML文字列に差し替えて検証する。
"""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newssite import analyze, impact as impact_mod, render, rss, stocks as stocks_mod  # noqa: E402

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
{items}
</channel></rss>"""

ITEM_TEMPLATE = """<item>
  <title>{title} - {source}</title>
  <link>{link}</link>
  <pubDate>{pub}</pubDate>
  <source url="https://example.com">{source}</source>
</item>"""


def make_rss(entries):
    items = "\n".join(
        ITEM_TEMPLATE.format(title=t, source=s, link=l, pub="Sat, 13 Sep 2026 00:00:00 GMT")
        for t, s, l in entries
    )
    return RSS_TEMPLATE.format(items=items).encode("utf-8")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


class RssTest(unittest.TestCase):
    def test_fetch_parses_and_strips_source_suffix(self):
        payload = make_rss([("日銀が追加利上げを決定", "日本経済新聞", "https://example.com/a")])
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
            items = rss.fetch("dummy", "policy", 2)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "日銀が追加利上げを決定")
        self.assertEqual(items[0]["source"], "日本経済新聞")
        self.assertEqual(items[0]["feed_category"], "policy")
        self.assertIsNotNone(items[0]["published"])

    def test_fetch_returns_empty_on_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("boom")):
            self.assertEqual(rss.fetch("dummy"), [])

    def test_collect_merges_duplicate_topics(self):
        payload = make_rss([
            ("日銀が追加利上げを決定 政策金利0.75%へ", "A社", "https://example.com/1"),
            ("日銀が追加利上げを決定 市場は上昇", "B社", "https://example.com/2"),
            ("訪日客が過去最高を更新", "C社", "https://example.com/3"),
        ])
        with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: FakeResponse(payload)):
            items = rss.collect([("q1", "policy", 2)])
        self.assertEqual(len(items), 2)
        merged = items[0]
        self.assertEqual(len(merged["related"]), 1)
        self.assertEqual(merged["related"][0]["source"], "B社")

    def test_collect_drops_old_articles(self):
        payload = make_rss([("古いニュース", "A社", "https://example.com/old")])
        payload = payload.replace(b"Sat, 13 Sep 2026 00:00:00 GMT", b"Mon, 01 Jan 2001 00:00:00 GMT")
        with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: FakeResponse(payload)):
            self.assertEqual(rss.collect([("q1", "policy", 1)], max_age_hours=24), [])


class ImpactTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = impact_mod.load()
        cls.master = stocks_mod.load()

    def _item(self, title, **kw):
        base = {"title": title, "feed_weight": 1, "feed_category": "market",
                "related": [], "feed_categories": ["market"]}
        base.update(kw)
        return base

    def test_theme_keyword_and_exclusion(self):
        weak = [t["id"] for t in impact_mod.match_themes("円安が進行、1ドル158円台", self.rules)]
        self.assertIn("yen_weak", weak)
        self.assertNotIn("yen_strong", weak)
        both = [t["id"] for t in impact_mod.match_themes("円安から円高に転換", self.rules)]
        self.assertNotIn("yen_weak", both)

    def test_and_condition_keyword(self):
        # "日銀 利上げ" は AND 条件。両方含む見出しだけ一致する。
        hit = [t["id"] for t in impact_mod.match_themes("日銀が利上げを決定", self.rules)]
        self.assertIn("boj_hike", hit)
        miss = [t["id"] for t in impact_mod.match_themes("日銀総裁が記者会見", self.rules)]
        self.assertNotIn("boj_hike", miss)

    def test_importance_rises_with_keyword_and_coverage(self):
        plain = self._item("東証、小幅続伸で取引を終える")
        big = self._item("日銀が追加利上げを決定、長期金利は上昇",
                         related=[{}, {}], feed_weight=2, feed_categories=["policy", "market"])
        plain_score, _ = impact_mod.score_importance(plain, impact_mod.match_themes(plain["title"], self.rules), self.rules)
        big_score, reason = impact_mod.score_importance(big, impact_mod.match_themes(big["title"], self.rules), self.rules)
        self.assertLess(plain_score, big_score)
        self.assertEqual(big_score, 5)
        self.assertIn("利上げ", reason)

    def test_affected_stocks_cover_both_directions(self):
        item = self._item("日銀が追加利上げを決定、長期金利は上昇")
        themes = impact_mod.match_themes(item["title"], self.rules)
        impacts = impact_mod.affected_stocks(item, themes, self.rules, self.master, max_items=8)
        directions = {i["direction"] for i in impacts}
        self.assertIn("positive", directions)
        self.assertIn("negative", directions)
        banks = [i for i in impacts if i["code"] == "8306"]
        self.assertEqual(banks[0]["direction"], "positive")
        self.assertTrue(all(i["reason"] for i in impacts))

    def test_named_company_becomes_direct_impact(self):
        item = self._item("トヨタ自動車、通期予想を上方修正 過去最高益へ")
        themes = impact_mod.match_themes(item["title"], self.rules)
        impacts = impact_mod.affected_stocks(item, themes, self.rules, self.master)
        self.assertEqual(impacts[0]["code"], "7203")
        self.assertEqual(impacts[0]["origin"], "direct")
        self.assertEqual(impacts[0]["direction"], "positive")

    def test_named_company_negative_headline(self):
        item = self._item("日産自動車、通期予想を下方修正 赤字転落へ")
        impacts = impact_mod.affected_stocks(item, [], self.rules, self.master)
        self.assertEqual(impacts[0]["code"], "7201")
        self.assertEqual(impacts[0]["direction"], "negative")

    def test_all_rule_themes_resolve_to_real_stocks(self):
        """rules.json の themes タグが stocks.json に存在することを保証する。"""
        for theme in self.rules.themes:
            for rule in theme.get("impacts", []):
                targets = self.master.by_themes(rule.get("themes", []))
                codes = [c for c in rule.get("codes", []) if c in self.master.by_code]
                self.assertTrue(
                    targets or codes,
                    f"テーマ {theme['id']} の impacts が1銘柄も解決できません: {rule.get('themes')}",
                )

    def test_all_theme_categories_exist(self):
        for theme in self.rules.themes:
            self.assertIn(theme["category"], self.rules.category_label, theme["id"])


class AnalyzeTest(unittest.TestCase):
    def test_stock_ranking_aggregates_direction(self):
        news = [
            {"title": "n1", "url": "u1", "importance": 5,
             "impacts": [{"code": "8306", "name": "三菱UFJ", "sector": "銀行", "direction": "positive", "reason": "r"}]},
            {"title": "n2", "url": "u2", "importance": 3,
             "impacts": [{"code": "8306", "name": "三菱UFJ", "sector": "銀行", "direction": "negative", "reason": "r"}]},
        ]
        rows = analyze.stock_ranking(news)
        self.assertEqual(rows[0]["code"], "8306")
        self.assertEqual(rows[0]["mentions"], 2)
        self.assertEqual(rows[0]["positive"], 1)
        self.assertEqual(rows[0]["negative"], 1)
        self.assertEqual(rows[0]["score"], 5 - 3)

    def test_market_snapshot_reads_existing_data_json(self, ):
        import tempfile
        payload = {"nikkei225": {"value": "41,000.00", "change_pct": 1.2, "asof": "15:00"},
                   "fx": {"value": "", "change_pct": None},
                   "us_market": {"sp500": {"value": "6,000", "change_pct": -0.4}}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(payload, f)
            path = f.name
        rows = analyze.market_snapshot(path)
        labels = [r["label"] for r in rows]
        self.assertIn("日経平均", labels)
        self.assertIn("S&P500", labels)
        self.assertNotIn("ドル円", labels)  # 値が空のものは出さない

    def test_market_snapshot_missing_file(self):
        self.assertEqual(analyze.market_snapshot("/nonexistent/data.json"), [])


class RenderTest(unittest.TestCase):
    def setUp(self):
        from newssite.sample import sample_data
        self.data = sample_data()
        self.html = render.build_html(self.data)

    def test_html_contains_news_and_impacts(self):
        self.assertIn("重要ニュース × 影響銘柄", self.html)
        self.assertIn("日銀、追加利上げを決定", self.html)
        self.assertIn("影響が出うる銘柄", self.html)
        self.assertIn("data-code=\"8306\"", self.html)
        self.assertIn("finance.yahoo.co.jp/quote/8306.T", self.html)

    def test_html_escapes_dangerous_text(self):
        data = dict(self.data)
        data["news"] = [dict(self.data["news"][0], title='<script>alert(1)</script>', summary='"><img>')]
        html_text = render.build_html(data)
        self.assertNotIn("<script>alert(1)</script>", html_text)
        self.assertIn("&lt;script&gt;", html_text)

    def test_empty_news_renders_placeholder(self):
        data = dict(self.data, news=[], stock_ranking=[], counts={"news": 0, "high_importance": 0, "stocks": 0})
        html_text = render.build_html(data)
        self.assertIn("ニュースを取得できませんでした", html_text)

    def test_stars(self):
        self.assertEqual(render.stars(5), "★★★★★")
        self.assertEqual(render.stars(2), "★★☆☆☆")
        self.assertEqual(render.stars(0), "★☆☆☆☆")


if __name__ == "__main__":
    unittest.main()
