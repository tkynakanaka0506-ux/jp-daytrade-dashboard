---
description: チェック・テストを通してからコミット＆プッシュする
allowed-tools: Bash(python3 dev.py:*), Bash(git:*), Read
---

変更を確定します。次の順で実行してください。

1. `python3 dev.py check`（失敗したら直してから進む）
2. `python3 dev.py test`（失敗したら直してから進む）
3. `git status` と `git diff` で変更内容を確認する。
   `preview.html` / `preview.news.json` が含まれていたらコミットしない（.gitignore 済みのはず）。
4. 変更内容を1行で表す日本語のコミットメッセージでコミットする。
5. `git push` する。現在のブランチが `main` の場合は、先に作業用ブランチを切ってからプッシュする。
6. **作業用ブランチにいる場合は、ここで終わらない。** `main` を最新化してから
   作業用ブランチをマージし、`main` も push する（`git checkout main && git pull
   && git merge <作業用ブランチ> && python3 dev.py test && git push origin main`）。
   本番(GitHub Actions)は `main` だけを見て自動生成しているため、`main` に
   届かない変更は永久に本番へ反映されない。作業用ブランチへのpushだけで
   「ship完了」にしない。
   マージがコンフリクトする、または内容のレビューを先にしたい場合だけ、
   マージせずにPRを作成した上でその旨をユーザーに報告する。
