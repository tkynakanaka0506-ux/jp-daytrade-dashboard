# 重要ニュース × 影響銘柄サイト

日本株に影響しうる重要ニュースを自動で集めて、**そのニュースでどの銘柄に影響が出うるか**を
並べて表示する静的サイトです。GitHub Actions が定期実行し、GitHub Pages で公開されます。

公開URL: https://tkynakanaka0506-ux.github.io/jp-daytrade-dashboard/

> ⚠️ 投資助言ではありません。「影響が出うる銘柄」はキーワードルールにもとづく機械的な関連付けで、
> 株価の値動きを保証するものではありません。

## 何をしているか

```
Google ニュース RSS(21クエリ)
  ↓ newssite/rss.py        …… 取得・同じ話題の重複を1件に束ねる
  ↓ newssite/impact.py     …… 重要度(★1〜5)・カテゴリ・影響銘柄をルールで判定
  ↓ newssite/llm.py        …… (任意)Gemini/Groqで要約・波及コメント・追加銘柄を補強
  ↓ newssite/analyze.py    …… news.json のデータ構造を組み立てる
  ↓ newssite/render.py     …… index.html を生成
index.html(GitHub Pagesで公開)
```

APIキーが無くても、キーワードルールだけでサイトは完成します（AI補強は任意）。

### 影響銘柄の決め方

1. **当事者**: 見出しに社名・証券コードが直接出ている銘柄。見出しの言葉（上方修正／下方修正など）
   から追い風・逆風を判定します。
2. **波及**: 見出しが該当したテーマ（例「日銀の利上げ」）から、`newssite/data/rules.json` の
   定義に沿って関連銘柄を引き当てます。例えば利上げなら銀行・保険が「追い風」、不動産・高PER株が
   「逆風」といった対応づけです。

各銘柄には「なぜ効くのか」の理由文が必ず付きます。

## ローカルで動かす（Cursor での作業手順）

Python 3.9 以上があれば依存パッケージのインストールは不要です（標準ライブラリのみ）。

```bash
# 1. 表示確認だけしたい(ネット接続不要・サンプルデータ)
python3 build_news_site.py --sample
open index.html          # Windows は start index.html

# 2. 実際にニュースを取得して生成する
python3 build_news_site.py --no-llm      # ルール判定のみ
python3 build_news_site.py               # GEMINI_API_KEY / GROQ_API_KEY があればAI補強あり

# 3. news.json はそのままでHTMLだけ作り直す(デザイン調整時に速い)
python3 build_news_site.py --render-only

# 4. テスト(ルール判定・重複統合・HTML生成)
python3 -m unittest discover -s tests -v
```

生成物は `news.json`（データ）と `index.html`（ページ）の2つだけです。

## よくある編集

| やりたいこと | 触るファイル |
| --- | --- |
| 銘柄を増やす・テーマタグを変える | `newssite/data/stocks.json` |
| 「このニュース→この銘柄」の関係を変える | `newssite/data/rules.json` の `themes` |
| 重要度の付け方（★の基準）を変える | `newssite/data/rules.json` の `importance_keywords` / `newssite/impact.py` の `score_importance` |
| 集めるニュースの種類を増やす | `newssite/config.py` の `FEEDS` |
| 見た目（配色・レイアウト） | `newssite/render.py` の `CSS` |
| ページの構成・文言 | `newssite/render.py` の `build_html` |
| AIへの指示文 | `newssite/llm.py` の `PROMPT_HEADER` |

### 銘柄を追加する例

`newssite/data/stocks.json` に追記します。`themes` がルール側と結びつく唯一のキーです。

```json
{"code": "1234", "name": "サンプル製作所", "sector": "機械",
 "aliases": ["サンプル"], "themes": ["防衛", "円安メリット"]}
```

### ニュース→銘柄のルールを追加する例

`newssite/data/rules.json` の `themes` に追記します。`keywords` は見出しへの部分一致で、
半角スペース区切りは AND 条件（`"日銀 利上げ"` は両方含む見出しだけ該当）です。

```json
{
  "id": "hydrogen", "label": "水素・脱炭素", "category": "resources", "weight": 2,
  "keywords": ["水素", "アンモニア発電"], "exclude": [],
  "impacts": [
    {"themes": ["水素"], "limit": 4, "direction": "positive", "strength": "中",
     "reason": "水素関連の需要拡大が材料視されやすい"}
  ]
}
```

追記したら `python3 -m unittest discover -s tests` を実行してください。
ルールが1銘柄も引き当てられない（タグ名のtypo）と落ちるようにしてあります。

## 自動更新

`.github/workflows/update.yml` が実行します（JSTの市場時間帯は15分おき、それ以外は2時間おき）。

1. `mvn package` → `java -jar target/dashboard-updater.jar`（指数・為替・TDnet等を `data.json` へ）
2. `news_analyzer.py`（旧ダッシュボード用のニュース分析）
3. **`build_news_site.py`（このサイト本体。`news.json` と `index.html` を生成）**
4. `render_dashboard.py`（旧ダッシュボードを `dashboard.html` として保存）
5. `notify_line.py`（LINE通知・任意）
6. 差分があれば `main` へ push

Secrets（すべて任意）: `GEMINI_API_KEY`, `GROQ_API_KEY`, `EDINET_API_KEY`,
`LINE_CHANNEL_ACCESS_TOKEN`, `LINE_USER_ID`。

## ファイル構成

```
build_news_site.py        エントリポイント(これを実行する)
newssite/
  config.py               収集フィード・定数
  rss.py                  Google ニュースRSS取得・重複統合
  stocks.py               銘柄マスタの読み込み・検索
  impact.py               重要度・カテゴリ・影響銘柄のルール判定
  llm.py                  Gemini/Groq 補強(任意)
  analyze.py              全体の組み立て
  render.py               HTML生成(CSS・JSもここ)
  sample.py               ネット接続なしの表示確認用データ
  data/stocks.json        銘柄マスタ(150銘柄)
  data/rules.json         ニュース→影響銘柄のルール
tests/test_pipeline.py    テスト
index.html / news.json    生成物

# 以下は旧デイトレードダッシュボード(dashboard.html として存続)
render_dashboard.py, news_analyzer.py, notify_line.py, data.json,
watchlist.json, pom.xml, src/main/java/Main.java, README_AUTOMATION.md
```
