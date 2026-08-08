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
- **日経225先物**: 同APIで取得。シンボル変更等で取得できない場合は前回値を使わず、
  空表示と「取得不可」の状態を記録する
- **TDnet適時開示**: 株探(kabutan)モバイル版ミラー `s.kabutan.jp/disclosures/`
  をJsoupでスクレイピング(最大3ページ・20件まで)
- **個別銘柄テクニカル分析**: 投資の森(nikkeiyosoku.com)の該当銘柄ページを
  スクレイピング。対象銘柄は `Main.java` の `WATCHLIST` 配列
  (現在: トヨタ/ソニー/三菱UFJ/ソフトバンクG)。増減はこの配列を編集するだけでよい。

## ニュース・話題株の分析

`news_analyzer.py` が Google News RSS で候補を集め、設定済みの Gemini または Groq を
使って次の項目を更新する。片方のAPIで失敗した場合はもう片方へ再試行する。

- `overnight_news` / `afterclose_news`(市況ニュースの見出し)
- `movers_morning` / `movers_afterclose`(急騰・急落銘柄ランキング)
- `us_good_news`(米国株の好材料ニュース)

**重要:** 両方のAPIが失敗・未設定の場合、または結果反映に失敗した場合は、対象配列を
空にして `data_status` を「取得不可」にする。前回実行のニュース・話題株は表示にも
LINE通知にも使用しない。APIキーは **Settings > Secrets and variables > Actions** に
Secretsとして保存し、コード中にハードコードしないこと。

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

## 表示・更新日時と取得失敗時の挙動

ページ上部の「データ更新記録」には、データ種別ごとに今回の取得状態、確認時刻、理由を
表示する。状態は `更新済み`、`一部取得`、`取得済み(該当なし)`、`取得不可`、`今回未取得`
で区別する。

更新処理の開始時に、表示・通知で使うすべての前回値と前回の更新時刻を消去する。
したがって取得失敗時は、古い内容を残さず対象セクションを空表示にし、理由を明示する。
LINE通知も `data_status` で今回取得済みと確認できたデータのみを候補に使う。
さらに、各セクションと各カードの見出しにページへの表示日時(JST)を表示する。
