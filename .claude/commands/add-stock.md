---
description: 銘柄マスタに銘柄を追加する
argument-hint: 証券コード 銘柄名（例: 7012 川崎重工業）
allowed-tools: Read, Edit, Bash(python3 dev.py:*)
---

`newssite/data/stocks.json` に次の銘柄を追加してください: $ARGUMENTS

手順:
1. 既存の並び（業種ごとのまとまり）を見て、近い業種の隣に入れる。
2. `code` / `name` / `sector` / `aliases` / `themes` を埋める。
   `themes` は既存の銘柄が使っているタグ語彙から選ぶこと（新語を作らない。
   どうしても新タグが要る場合は `newssite/data/rules.json` 側にもそのタグを使うルールを足す）。
3. `python3 dev.py check` を実行し、エラーが無いことを確認する。
4. 追加した銘柄がどのニュースルールで拾われるようになるかを1〜2行で報告する。
