#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ネット接続なしで表示を確認するためのサンプルデータ。

`python3 build_news_site.py --sample` から使う。ルール判定は本番と同じコードを通すので、
data/rules.json や data/stocks.json を編集した結果の確認にも使える。
"""
from datetime import datetime, timedelta

from . import analyze, impact as impact_mod, stocks as stocks_mod
from .config import JST
from .rss import news_id

SAMPLE_HEADLINES = [
    ("日銀、追加利上げを決定 政策金利0.75%に 長期金利は上昇", "日本経済新聞", "policy", 2, 3),
    ("米政権、日本車への追加関税を表明 自動車業界に影響懸念", "ロイター", "trade", 2, 2),
    ("中東情勢が緊迫 ホルムズ海峡に警戒感、原油価格が急騰", "時事通信", "geopolitics", 2, 1),
    ("エヌビディア決算が市場予想を上回る AI半導体とデータセンター投資が拡大", "Bloomberg", "tech", 2, 1),
    ("円安進行、一時1ドル=158円台 輸入コスト上昇に警戒", "NHK", "fx", 1, 0),
    ("政府、半導体の対中輸出規制を強化へ 経済安全保障を重視", "共同通信", "trade", 2, 2),
    ("トヨタ自動車、通期業績予想を上方修正 過去最高益へ", "日経QUICK", "corporate", 2, 1),
    ("訪日外国人客が過去最高を更新 インバウンド消費も拡大", "観光経済新聞", "japan", 1, 0),
    ("政府が経済対策を閣議決定 補正予算は規模拡大へ", "読売新聞", "japan", 1, 1),
    ("米国株、ナスダックが反落 ハイテク株に利益確定売り", "ロイター", "us", 1, 0),
    ("データセンター向け電力需要が急増 原発の再稼働論議も", "電気新聞", "resources", 1, 0),
    ("大手商社に大規模なサイバー攻撃 情報漏えいの可能性", "ITmedia", "tech", 1, 0),
]


def sample_data():
    rules = impact_mod.load()
    master = stocks_mod.load()
    now = datetime.now(JST)

    items = []
    for i, (title, source, category, weight, related_count) in enumerate(SAMPLE_HEADLINES):
        published = now - timedelta(hours=i * 2 + 1)
        items.append({
            "id": news_id(title, f"https://example.com/sample/{i}"),
            "title": title,
            "url": f"https://news.google.com/search?q={i}",
            "source": source,
            "published": published,
            "feed_query": "sample",
            "feed_category": category,
            "feed_weight": weight,
            "feed_categories": [category],
            "related": [
                {"title": f"{title}(関連報道 {j + 1})", "url": f"https://example.com/related/{i}/{j}",
                 "source": "関連媒体"}
                for j in range(related_count)
            ],
        })

    news = []
    for item in items:
        themes = impact_mod.match_themes(item["title"], rules)
        stars, reason = impact_mod.score_importance(item, themes, rules)
        category = impact_mod.pick_category(item, themes, rules)
        news.append({
            "id": item["id"],
            "title": item["title"],
            "url": item["url"],
            "source": item["source"],
            "published_at": item["published"].strftime("%Y-%m-%d %H:%M"),
            "published_ts": item["published"].timestamp(),
            "category": category,
            "category_label": rules.category_label.get(category, "市況"),
            "category_emoji": rules.category_emoji.get(category, "📰"),
            "importance": stars,
            "importance_reason": reason,
            "themes": [t["label"] for t in themes],
            "summary": "",
            "impact_comment": "",
            "impacts": impact_mod.affected_stocks(item, themes, rules, master, max_items=8),
            "related": item["related"],
        })
    news.sort(key=lambda n: (-n["importance"], -n["published_ts"]))
    ranking = analyze.stock_ranking(news)

    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "generated_iso": now.isoformat(timespec="seconds"),
        "status": "sample",
        "status_message": "サンプルデータで生成した表示確認用のページです。",
        "llm_used": False,
        "categories": rules.categories,
        "market": [
            {"label": "日経平均", "value": "41,250.10", "change_pct": 0.82, "asof": "15:00"},
            {"label": "ドル円", "value": "157.42", "change_pct": 0.31, "asof": "18:00"},
            {"label": "S&P500", "value": "6,102.44", "change_pct": -0.45, "asof": "終値"},
        ],
        "news": news,
        "stock_ranking": ranking,
        "counts": {
            "news": len(news),
            "high_importance": sum(1 for n in news if n["importance"] >= 4),
            "stocks": len(ranking),
        },
    }
