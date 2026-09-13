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

## Cursor で開発する

### 最初の1回

```bash
git clone https://github.com/tkynakanaka0506-ux/jp-daytrade-dashboard.git
cd jp-daytrade-dashboard
./setup_cursor.sh          # Windows は setup_cursor.bat をダブルクリック
```

`setup_cursor.sh` / `setup_cursor.bat` が、Pythonのバージョン確認 → データ整合性チェック →
テスト → サンプルページ生成まで一気に済ませます。**pip install は不要**（標準ライブラリのみ）。
そのまま Cursor でフォルダを開いてください。

### ふだんの作業

```bash
python3 dev.py serve --watch   # これ1つでOK(Windows は py dev.py serve --watch)
```

ローカルサーバが立ち上がってブラウザでプレビューが開きます。`newssite/` のファイルを保存すると
**自動でページを作り直し、ブラウザも自動で再読み込み**します。CSSや文言をいじりながら確認できます。

Cursor のコマンドパレット（Cmd/Ctrl + Shift + P →「Tasks: Run Task」）からも同じことができます。
`.vscode/tasks.json` に①〜⑥を登録済みです。

### dev.py のコマンド

| コマンド | 内容 |
| --- | --- |
| `python3 dev.py setup` | 初回セットアップ（環境確認＋チェック＋テスト＋生成） |
| `python3 dev.py serve --watch` | プレビューを開いて、保存のたびに自動再生成・自動リロード |
| `python3 dev.py sample` | サンプルデータで生成（ネット接続不要） |
| `python3 dev.py build` | 実際のニュースを取得して生成（`--llm` でAI補強あり） |
| `python3 dev.py render` | データはそのままHTMLだけ作り直す |
| `python3 dev.py check` | `stocks.json` / `rules.json` のタグ誤字・コード重複を検査 |
| `python3 dev.py test` | テストを実行 |
| `python3 dev.py open` | 生成済みプレビューをブラウザで開く |

`--port 8001` でポート変更、`--no-open` でブラウザ自動起動なし。

> **ローカル作業は `preview.html` にだけ書き出します。**
> 公開される `index.html` / `news.json` は GitHub Actions だけが生成するので、
> ローカルの試し打ちが公開ページを壊すことはありません（両ファイルは `.gitignore` 済み）。

### 手動で直接動かしたいとき

```bash
python3 build_news_site.py --sample      # 本番と同じ出力先(index.html)に書きます
python3 build_news_site.py --no-llm
python3 build_news_site.py --render-only
python3 -m unittest discover -s tests -v
```

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
setup_cursor.sh / .bat    初回セットアップ(Cursorで開発を始めるとき)
dev.py                    ローカル開発コマンド(serve/sample/build/check/test)
.vscode/tasks.json        Cursorのコマンドパレットから実行できるタスク
build_news_site.py        生成本体(GitHub Actions が実行する)
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
index.html / news.json    生成物(Actionsが生成・コミットする)
preview.html              ローカル確認用の生成物(gitignore済み)

# 以下は旧デイトレードダッシュボード(dashboard.html として存続)
render_dashboard.py, news_analyzer.py, notify_line.py, data.json,
watchlist.json, pom.xml, src/main/java/Main.java, README_AUTOMATION.md
```
