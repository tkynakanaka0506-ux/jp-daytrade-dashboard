#!/usr/bin/env bash
# Cursor でこのリポジトリを触りはじめるときの初回セットアップ(macOS / Linux)。
#
#   ./setup_cursor.sh
#
# やること: Python のバージョン確認 → データ整合性チェック → テスト → サンプルページ生成
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
      PY="$candidate"
      break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "❌ Python 3.9 以上が見つかりませんでした。"
  echo "   https://www.python.org/downloads/ からインストールしてから、もう一度実行してください。"
  exit 1
fi

"$PY" dev.py setup

cat <<'MSG'

--------------------------------------------------------
Cursor での使い方
--------------------------------------------------------
  Cmd/Ctrl + Shift + P → "Tasks: Run Task" から
    ① プレビューを開く(自動再生成つき)
    ④ データの整合性チェック
    ⑤ テスト
  を選べます。

  ターミナル派なら:
    python3 dev.py serve --watch
--------------------------------------------------------
MSG
