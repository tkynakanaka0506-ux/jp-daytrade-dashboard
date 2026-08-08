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

## LINE通知のエントリー判定

`notify_line.py` は、場中の通知では材料を検知しただけで送らず、Yahoo Finance の
1分足で通知直前の価格を再確認する。次のいずれかに当てはまる銘柄は
「既に動いた」として通知から除外する。

- 前日終値比が +2.5% 超
- 寄り付きギャップが +1.5% 超
- 当日安値から +2.0% 超
- 当日高値から 1.0% 超下落(高値掴み・失速の回避)
- 東証コードまたはリアルタイム価格を確実に取得できない

基準値は必要に応じて GitHub Actions の環境変数で調整できる。
`LINE_MAX_DAY_CHANGE_PCT`、`LINE_MAX_OPEN_GAP_PCT`、
`LINE_MAX_FROM_DAY_LOW_PCT`、`LINE_MAX_FROM_DAY_HIGH_PCT`、
`LINE_MAX_DATA_AGE_MINUTES` を設定しなければ、上記の既定値を使う。

ただし、当日15:00以降に公表されたTDnetの上方修正・増配等の好材料は例外である。
15:30〜23:55(JST)に「翌営業日監視候補」として通知し、場中用の上昇率フィルターでは
除外しない。同一開示URLは履歴で管理し、夜間・翌朝に重複して通知しない。

## 表示・更新日時

ページ上部の「データ更新記録」には、データ種別ごとに実際に取得できた最終時刻を表示する。
取得に失敗したデータは前回値を保持し、「未更新・前回データを保持」と明記する。
さらに、各セクションと各カードの見出しにページへの表示日時(JST)を表示する。
