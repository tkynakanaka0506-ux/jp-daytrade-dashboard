#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""収集対象フィードと共通定数。

ニュースの取得元を増やしたいときは FEEDS に1行足すだけでよい。
category は data/rules.json の categories[].id と対応させること。
"""
from datetime import timedelta, timezone

JST = timezone(timedelta(hours=9))

UA = "Mozilla/5.0 (compatible; jp-news-impact-bot/1.0)"

# 1フィードあたりの取得件数と、ページに載せるニュースの最大件数
PER_FEED_LIMIT = 12
MAX_NEWS_ITEMS = 40

# これより古い記事は捨てる(時間)
MAX_AGE_HOURS = 48

# Google News RSS 検索クエリ。(query, category, 基礎重要度)
FEEDS = [
    ("日銀 金融政策 金利", "policy", 2),
    ("FRB FOMC 利上げ 利下げ", "policy", 2),
    ("長期金利 国債利回り", "policy", 1),
    ("円相場 為替 ドル円", "fx", 1),
    ("為替介入 円安 円高", "fx", 2),
    ("関税 貿易摩擦 通商", "trade", 2),
    ("輸出規制 経済安全保障 半導体", "trade", 2),
    ("中東情勢 原油 イスラエル イラン", "geopolitics", 2),
    ("ウクライナ ロシア 停戦", "geopolitics", 1),
    ("台湾 中国 安全保障", "geopolitics", 1),
    ("原油価格 OPEC 資源価格", "resources", 1),
    ("電力需要 データセンター 原発", "resources", 1),
    ("半導体 AI 投資 増産", "tech", 2),
    ("エヌビディア 生成AI 決算", "tech", 1),
    ("日本株 東証 株式市場", "market", 1),
    ("日経平均 急騰 急落", "market", 1),
    ("上方修正 業績予想 決算", "corporate", 2),
    ("自社株買い 増配 TOB 買収", "corporate", 2),
    ("経済対策 補正予算 政府", "japan", 1),
    ("訪日客 インバウンド 消費", "japan", 1),
    ("米国株 ダウ ナスダック", "us", 1),
]

# 市況ヘッダーに出す指標(data.json 由来。取得できない場合は非表示)
MARKET_TICKERS = [
    ("nikkei225", "日経平均"),
    ("nikkei_futures", "日経先物"),
    ("fx", "ドル円"),
    ("us_market.sp500", "S&P500"),
    ("us_market.nasdaq", "ナスダック"),
    ("us_market.sox", "SOX指数"),
]
