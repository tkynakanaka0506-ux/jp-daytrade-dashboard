@echo off
REM Cursor でこのリポジトリを触りはじめるときの初回セットアップ(Windows)。
REM   setup_cursor.bat をダブルクリック、または PowerShell で .\setup_cursor.bat
setlocal
cd /d "%~dp0"

set PY=
for %%C in (py python python3) do (
  if not defined PY (
    %%C -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
    if not errorlevel 1 set PY=%%C
  )
)

if not defined PY (
  echo [ERROR] Python 3.9 以上が見つかりませんでした。
  echo         https://www.python.org/downloads/ からインストールし、
  echo         インストール時に "Add python.exe to PATH" にチェックを入れてください。
  pause
  exit /b 1
)

%PY% dev.py setup
if errorlevel 1 (
  echo.
  echo [ERROR] セットアップが途中で失敗しました。上のログを確認してください。
  pause
  exit /b 1
)

echo.
echo --------------------------------------------------------
echo Cursor での使い方
echo --------------------------------------------------------
echo   Ctrl + Shift + P  =^>  "Tasks: Run Task" から
echo     (1) プレビューを開く(自動再生成つき)
echo     (4) データの整合性チェック
echo     (5) テスト
echo.
echo   ターミナル派なら:  py dev.py serve --watch
echo --------------------------------------------------------
pause
