# 重要ニュース × 影響銘柄サイト

日本株に影響しうる重要ニュースを自動収集し、各ニュースで「どの銘柄に影響が出うるか」を
表示する静的サイト。GitHub Actions が定期生成し、GitHub Pages で公開している。

公開URL: https://tkynakanaka0506-ux.github.io/jp-daytrade-dashboard/

## コマンド

ローカル作業は `dev.py` を使う。出力は `preview.html` / `preview.news.json` のみで、
公開される `index.html` / `news.json` は GitHub Actions だけが生成する（ローカルから上書きしない）。

```bash
python3 dev.py serve --watch   # プレビュー＋保存のたび自動再生成・自動リロード
python3 dev.py sample          # サンプルデータで生成（ネット接続不要）
python3 dev.py build           # 実ニュースを取得して生成（--llm でAI補強）
python3 dev.py check           # stocks.json / rules.json の整合性チェック
python3 dev.py test            # テスト（tests/test_pipeline.py・22件）
```

**JSONデータを変えたら `dev.py check`、ロジックを変えたら `dev.py test` を必ず通してから終わる。**

## 構成

```
build_news_site.py   生成本体（Actionsが実行）
dev.py               ローカル開発コマンド
newssite/
  config.py          収集フィード(FEEDS)・定数
  rss.py             Google ニュースRSS取得・同じ話題の重複統合
  stocks.py          銘柄マスタの読み込み・検索
  impact.py          重要度/カテゴリ/影響銘柄のルール判定
  llm.py             Gemini/Groq 補強（任意）
  analyze.py         news.json の組み立て
  render.py          HTML生成（CSS・JSもこの中）
  sample.py          ネット接続なしの表示確認用データ
  data/stocks.json   銘柄マスタ（150銘柄）
  data/rules.json    ニュース→影響銘柄のルール（23テーマ）
tests/test_pipeline.py
```

## 編集する場所

| やりたいこと | ファイル |
| --- | --- |
| 銘柄を増やす・テーマタグを変える | `newssite/data/stocks.json` |
| ニュース→銘柄の関係、重要度キーワード | `newssite/data/rules.json` |
| 集めるニュースの種類 | `newssite/config.py` の `FEEDS` |
| 見た目（配色・レイアウト） | `newssite/render.py` の `CSS` |
| ページ構成・文言 | `newssite/render.py` の `build_html` |
| AIへの指示文 | `newssite/llm.py` の `PROMPT_HEADER` |

`stocks.json` の `themes` と `rules.json` の `impacts[].themes` は同じタグ語彙。
新しいタグを使うときは両方に入れる（`dev.py check` とテストが不整合を検出する）。

## 守ること

- **依存を増やさない**: Python標準ライブラリのみ（`pip install` 不要を維持）。
  フレームワーク・npmパッケージ・ビルドツールは入れない。
- **APIキー無しでも動く**: 生成AI（`newssite/llm.py`）は補強にすぎない。キーが無い/失敗しても
  ルール判定だけでページが完成する状態を壊さない。
- **ネットワーク失敗で落とさない**: RSS取得やAPI呼び出しの失敗はログに残して処理を続ける。
  取得できなかったときは前回値を使わず空表示にする（古い情報で判断させない）。
- **断定表現を書かない**: 表示文・プロンプトとも「必ず上がる」等の確約表現は使わず、
  「〜の可能性がある」「〜が意識されやすい」に留める。投資助言にしない。
- **数字を創作しない**: 見出しに無い株価・業績数値をコードやプロンプトで作らない。
- **生成物を手で編集しない**: `index.html` / `news.json` / `preview.html` は自動生成物。
  直すのは生成元のコード。

## 旧ダッシュボード

`render_dashboard.py` / `news_analyzer.py` / `notify_line.py` / `src/main/java/Main.java` は
旧デイトレードダッシュボード（`dashboard.html`）用。市況ヘッダーの指数は `data.json` 経由で
ニュースサイトも使っているため消さずに残している。
