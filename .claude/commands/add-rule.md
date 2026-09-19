---
description: ニュース→影響銘柄のルール（テーマ）を追加する
argument-hint: テーマの説明（例: 水素・脱炭素のニュースで川崎重工などが動くルール）
allowed-tools: Read, Edit, Bash(python3 dev.py:*)
---

`newssite/data/rules.json` の `themes` に次のルールを追加してください: $ARGUMENTS

守ること:
- `keywords` は見出しへの部分一致。半角スペース区切りは AND 条件（"日銀 利上げ" は両方含む見出しのみ）。
  誤爆しそうな語は `exclude` に入れる（例: 円安テーマでは "円高" を除外）。
- `category` は同ファイルの `categories[].id` から選ぶ。
- `impacts[].themes` は `newssite/data/stocks.json` に実在するタグだけを使う。
- `direction` は positive / negative / watch のいずれか。`reason` は「なぜ効くのか」を必ず書き、
  断定表現は使わず「〜につながりやすい」「〜が意識されやすい」とする。
- 追い風だけでなく逆風side も検討する（両方ある材料は両方書く）。

最後に `python3 dev.py check` と `python3 dev.py test` を実行し、
`python3 dev.py sample` で該当見出しがどう表示されるかを確認して報告してください。
