"""重要ニュース × 影響銘柄サイトのビルド用パッケージ。

モジュール構成:
  config.py   … 収集するニュースフィード・定数
  rss.py      … Google News RSS の取得と正規化
  stocks.py   … 銘柄マスタ(data/stocks.json)の読み込みと検索
  impact.py   … 見出し→重要度・カテゴリ・影響銘柄のルール判定(data/rules.json)
  llm.py      … Gemini / Groq による要約・補正(APIキーが無ければ自動でスキップ)
  analyze.py  … 収集〜判定をまとめて news.json のデータ構造を組み立てる
  render.py   … news.json から index.html を生成する
"""

__all__ = ["config", "rss", "stocks", "impact", "llm", "analyze", "render"]
