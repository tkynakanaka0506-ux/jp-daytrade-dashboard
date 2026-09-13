---
description: プレビューサーバを起動して、保存のたびに自動再生成する
allowed-tools: Bash(python3 dev.py:*)
---

`python3 dev.py serve --watch` をバックグラウンドで起動し、
表示されたURL（http://127.0.0.1:8000/preview.html）をユーザーに伝えてください。

すでに同じポートが使われている場合は `--port 8001` のように番号を変えて再試行します。
