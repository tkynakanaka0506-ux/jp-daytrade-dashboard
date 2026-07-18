# dashboard自動更新(GitHub Actions + Java)

Claude(LLM)がWebSearch等でトークンを消費しながらデータ収集・pushする方式から、
GitHub Actions上でJavaプログラムが決定論的にデータ取得〜commit&pushまで
全自動で行う方式に切り替えるための追加ファイル一式です。

## 構成

```
pom.xml                          Maven設定(Java 21, Jsoup, Jackson)
src/main/java/Main.java          データ取得ロジック本体
.github/workflows/update.yml     朝6時・夜21時(JST)に自動実行するワークフロー
```

## 導入手順

1. 上記3点(pom.xml, src/, .github/workflows/update.yml)を
   `jp-daytrade-dashboard` リポジトリの**ルート**にコピーする
   (既存の `index.html` / `data.json` / `render_dashboard.py` と同じ階層)。
2. GitHubリポジトリの **Settings > Actions > General > Workflow permissions** を
   **「Read and write permissions」** に変更する(これをしないと自動pushが失敗する)。
3. これで完了。以後は毎日 JST 6:00 / 21:00 に自動実行され、`data.json` と
   `index.html` が更新・commit・push・GitHub Pagesへの反映まで自動で行われる。
4. 即座に試したい場合は、Actionsタブ → 「Update JP Daytrade Dashboard」→
   「Run workflow」から手動実行できる(modeにmorning/eveningを指定可能)。

## 何を自動取得しているか

- **米国3指数・日経225・ドル円**: Yahoo Financeのchart API
  (`query1.finance.yahoo.com/v8/finance/chart/...`, キー不要・無料)
- **日経225先物**: 同APIでベストエフォート取得(シンボルが変わりやすく、
  取得できない場合は既存値を保持するだけで処理は継続する)
- **TDnet適時開示**: 株探(kabutan)モバイル版ミラー `s.kabutan.jp/disclosures/`
  をJsoupでスクレイピング(最大3ページ・20件まで)
- **個別銘柄テクニカル分析**: 投資の森(nikkeiyosoku.com)の該当銘柄ページを
  スクレイピング。対象銘柄は `Main.java` の `WATCHLIST` 配列
  (現在: トヨタ/ソニー/三菱UFJ/ソフトバンクG)。増減はこの配列を編集するだけでよい。

## 自動化していないもの(制約)

以下は「話題性のあるニュース・銘柄を選ぶ」という主観的な作業を含むため、
無料の決定論的APIだけでは再現できず、このJava版では対象外にしている
(該当フィールドは前回の値がそのまま残る):

- `overnight_news` / `afterclose_news`(市況ニュースの見出し)
- `movers_morning` / `movers_afterclose`(急騰・急落銘柄ランキング)

必要であれば、有料/無料のニュースAPI等を導入し、APIキーは
**Settings > Secrets and variables > Actions** に登録して
`Main.java` から `System.getenv("...")` で読み込む形に拡張できる。
その場合もキーをコード中にハードコードしないこと。

## Claude側の旧スケジュールタスクについて

`jp-stock-dashboard-morning` / `jp-stock-dashboard-evening` の2つの
Claudeスケジュールタスクは、このGitHub Actionsワークフローが有効になれば
不要になる(同じ処理を毎回LLMがブラウザ操作で行っていたもの)。
重複更新やコンフリクトを避けるため、Actionsの動作確認後に無効化/削除することを推奨する。
