#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日本株(東証)デイトレード情報ダッシュボード レンダラー
====================================================
data.json (このスクリプトと同じフォルダに置く) を読み込み、
見やすいHTMLダッシュボードを生成する。

このスクリプト自体はネットワークに一切アクセスしない。
データ収集(Web検索・取得)はClaude(スケジュールタスク)側が
毎回 data.json を作り直すことで行う。

使い方:
    python3 render_dashboard.py [data.jsonのパス] [出力htmlのパス]
デフォルト:
    data.json ./data.json
    出力先    ./jp_daytrade_dashboard.html
"""
import json
import sys
import html as html_lib
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent


def esc(x):
    if x is None:
        return ""
    return html_lib.escape(str(x))


def fmt_pct(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "―"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"


def pct_class(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "flat"
    if v > 0:
        return "up"
    if v < 0:
        return "down"
    return "flat"


def signal_badge(signal):
    """signal: '強気' / '弱気' / '中立' などの文字列 -> 色付きバッジHTML"""
    s = (signal or "中立").strip()
    cls = "neutral"
    if "強気" in s or "買い" in s:
        cls = "bull"
    elif "弱気" in s or "売り" in s:
        cls = "bear"
    return f'<span class="badge {cls}">{esc(s)}</span>'


def section_index_row(label, value, change=None, note=None):
    change_html = ""
    if change is not None and change != "":
        change_html = f'<span class="chg {pct_class(change)}">{fmt_pct(change)}</span>'
    note_html = f'<div class="note">{esc(note)}</div>' if note else ""
    return f"""
    <div class="idx-card">
      <div class="idx-label">{esc(label)}</div>
      <div class="idx-value">{esc(value)}</div>
      {change_html}
      {note_html}
    </div>"""


def news_list(items, empty_msg="現時点で該当するニュースは取得できませんでした。"):
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        title = esc(it.get("title", ""))
        url = esc(it.get("url", "")) or "#"
        source = esc(it.get("source", ""))
        time_ = esc(it.get("time", ""))
        meta = " / ".join(x for x in [time_, source] if x)
        rows.append(
            f'<li><a href="{url}" target="_blank" rel="noopener">{title}</a>'
            f'<span class="meta">{meta}</span></li>'
        )
    return "<ul class=\"news-list\">" + "".join(rows) + "</ul>"


def tdnet_table(items, empty_msg="対象期間の適時開示は取得できませんでした。"):
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        time_ = esc(it.get("time", ""))
        code = esc(it.get("code", ""))
        company = esc(it.get("company", ""))
        title = esc(it.get("title", ""))
        url = esc(it.get("url", "")) or "#"
        tag = esc(it.get("tag", ""))
        tag_html = f'<span class="tag">{tag}</span>' if tag else ""
        rows.append(f"""
        <tr>
          <td class="mono">{time_}</td>
          <td class="mono">{code}</td>
          <td>{company}</td>
          <td><a href="{url}" target="_blank" rel="noopener">{title}</a> {tag_html}</td>
        </tr>""")
    return f"""
    <div class="scroll-hint">← 横にスクロールできます</div>
    <div class="table-scroll">
    <table class="tdnet-table">
      <thead><tr><th>時刻</th><th>コード</th><th>会社名</th><th>開示タイトル</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


def movers_table(items, empty_msg="該当データが取得できませんでした。"):
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        code = esc(it.get("code", ""))
        name = esc(it.get("name", ""))
        price = esc(it.get("price", ""))
        chg = it.get("change_pct")
        vol_note = esc(it.get("volume_note", ""))
        reason = esc(it.get("reason", ""))
        rows.append(f"""
        <tr>
          <td class="mono">{code}</td>
          <td>{name}</td>
          <td class="mono">{price}</td>
          <td class="mono {pct_class(chg)}">{fmt_pct(chg)}</td>
          <td>{vol_note}</td>
          <td class="reason">{reason}</td>
        </tr>""")
    return f"""
    <div class="scroll-hint">← 横にスクロールできます</div>
    <div class="table-scroll">
    <table class="movers-table">
      <thead><tr><th>コード</th><th>銘柄名</th><th>株価</th><th>前日比</th><th>出来高メモ</th><th>話題の背景</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


def technical_table(items, empty_msg="テクニカルデータが取得できませんでした。"):
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        code = esc(it.get("code", ""))
        name = esc(it.get("name", ""))
        price = esc(it.get("price", ""))
        chg = it.get("change_pct")
        ma5 = esc(it.get("ma5_dev", ""))
        ma25 = esc(it.get("ma25_dev", ""))
        rsi = it.get("rsi", "")
        rsi_disp = esc(rsi)
        rsi_note = ""
        try:
            rsi_f = float(rsi)
            if rsi_f >= 70:
                rsi_note = ' <span class="tag tag-warn">過熱感</span>'
            elif rsi_f <= 30:
                rsi_note = ' <span class="tag tag-warn">売られ過ぎ</span>'
        except (TypeError, ValueError):
            pass
        signal = it.get("signal", "中立")
        summary = esc(it.get("summary", ""))
        rows.append(f"""
        <tr>
          <td class="mono">{code}</td>
          <td>{name}</td>
          <td class="mono">{price}</td>
          <td class="mono {pct_class(chg)}">{fmt_pct(chg)}</td>
          <td class="mono">{ma5}</td>
          <td class="mono">{ma25}</td>
          <td class="mono">{rsi_disp}{rsi_note}</td>
          <td>{signal_badge(signal)}</td>
          <td class="reason">{summary}</td>
        </tr>""")
    return f"""
    <div class="scroll-hint">← 横にスクロールできます</div>
    <div class="table-scroll">
    <table class="technical-table">
      <thead><tr><th>コード</th><th>銘柄名</th><th>株価</th><th>前日比</th><th>5日線乖離</th><th>25日線乖離</th><th>RSI(14)</th><th>シグナル</th><th>コメント</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


CSS = """
:root {
  --bg: #0f1720; --panel: #161f2b; --panel2: #1b2531; --border: #2a3646;
  --text: #e6edf3; --muted: #92a1b3; --accent: #4da3ff; --up: #ff5c5c; --down: #4dd0a3;
  --warn: #ffb84d; --bull: #ff5c5c; --bear: #4dd0a3;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: -apple-system, "Hiragino Sans", "Yu Gothic", "Segoe UI", sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.6;
}
.wrap { max-width: 1080px; margin: 0 auto; padding: 24px 20px 60px; }
header.top { padding: 20px 20px 16px; }
h1 { font-size: 22px; margin: 0 0 4px; }
.subtitle { color: var(--muted); font-size: 13px; }
.disclaimer {
  background: #2a1f1f; border: 1px solid #5a3a3a; color: #ffcfcf;
  border-radius: 10px; padding: 14px 16px; font-size: 13px; margin: 16px 20px;
}
.disclaimer b { color: #ffb0b0; }
nav.tabs {
  display: flex; gap: 10px; margin: 0 0 8px; flex-wrap: wrap; padding: 10px 20px;
  position: sticky; top: 0; z-index: 20; background: rgba(15,23,32,0.92);
  backdrop-filter: blur(6px); border-bottom: 1px solid var(--border);
}
nav.tabs a {
  color: var(--accent); text-decoration: none; font-size: 13px; border: 1px solid var(--border);
  padding: 7px 14px; border-radius: 20px; background: var(--panel2); white-space: nowrap;
}
section { margin: 28px 20px; }
section > h2 {
  font-size: 17px; border-left: 4px solid var(--accent); padding-left: 10px; margin-bottom: 4px;
}
.section-desc { color: var(--muted); font-size: 12.5px; margin: 2px 0 14px; }
.card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
  padding: 16px 18px; margin-bottom: 16px;
}
.card h3 { font-size: 14px; margin: 0 0 10px; color: var(--muted); font-weight: 600; }
.idx-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }
.idx-card {
  background: var(--panel2); border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px;
}
.idx-label { font-size: 12px; color: var(--muted); }
.idx-value { font-size: 18px; font-weight: 700; margin-top: 2px; }
.chg { font-size: 13px; font-weight: 600; }
.chg.up, .up { color: var(--up); }
.chg.down, .down { color: var(--down); }
.chg.flat, .flat { color: var(--muted); }
.note { font-size: 11px; color: var(--muted); margin-top: 4px; }
.news-list { list-style: none; margin: 0; padding: 0; }
.news-list li { padding: 7px 0; border-bottom: 1px solid var(--border); font-size: 13.5px; }
.news-list li:last-child { border-bottom: none; }
.news-list a { color: var(--text); text-decoration: none; }
.news-list a:hover { color: var(--accent); }
.news-list .meta { display: block; color: var(--muted); font-size: 11px; margin-top: 2px; }
.scroll-hint { display: none; color: var(--muted); font-size: 11px; margin: 0 0 4px; }
.table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
.tdnet-table { min-width: 560px; }
.movers-table { min-width: 680px; }
.technical-table { min-width: 820px; }
th, td { text-align: left; padding: 8px 8px; border-bottom: 1px solid var(--border); }
th { color: var(--muted); font-weight: 600; font-size: 12px; white-space: nowrap; }
td.mono { font-family: "SF Mono", Menlo, monospace; white-space: nowrap; }
td.reason { color: var(--muted); }
tbody tr:nth-child(even) { background: rgba(255,255,255,0.025); }
tbody tr:hover { background: rgba(77,163,255,0.08); }
.badge { padding: 2px 9px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge.bull { background: rgba(255,92,92,0.15); color: var(--bull); }
.badge.bear { background: rgba(77,208,163,0.15); color: var(--bear); }
.badge.neutral { background: rgba(146,161,179,0.15); color: var(--muted); }
.tag { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: var(--border); color: var(--muted); margin-left: 4px; }
.tag-warn { background: rgba(255,184,77,0.18); color: var(--warn); }
.empty { color: var(--muted); font-size: 13px; }
footer { margin: 40px 20px 10px; color: var(--muted); font-size: 11.5px; border-top: 1px solid var(--border); padding-top: 16px; }
footer .disclaimer { margin: 0 0 12px; }
.sources { font-size: 11px; color: var(--muted); }
.run-badge { display:inline-block; font-size:11px; padding:2px 10px; border-radius:10px; background:var(--panel2); border:1px solid var(--border); margin-left:8px; }

/* --- PC(広い画面): 余白と最大幅を少し広げて読みやすくする --- */
@media (min-width: 1200px) {
  .wrap { max-width: 1240px; }
  body { font-size: 15.5px; }
  .idx-grid { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
}

/* --- スマホ(狭い画面): 余白・文字サイズを詰めてタップしやすくする --- */
@media (max-width: 640px) {
  .wrap { padding: 12px 12px 48px; }
  header.top { padding: 12px 8px 10px; }
  h1 { font-size: 17px; line-height: 1.4; }
  .subtitle { font-size: 11.5px; }
  .disclaimer { margin: 12px 8px; padding: 10px 12px; font-size: 12px; }
  nav.tabs { margin: 0 0 8px; padding: 8px 8px; gap: 6px; }
  nav.tabs a { font-size: 12px; padding: 6px 10px; }
  section { margin: 20px 8px; }
  section > h2 { font-size: 15.5px; }
  .section-desc { font-size: 11.5px; }
  .card { padding: 12px 12px; margin-bottom: 12px; }
  .idx-grid { grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: 8px; }
  .idx-value { font-size: 16px; }
  table { font-size: 12px; }
  th, td { padding: 6px 6px; }
  .scroll-hint { display: block; }
  footer { margin: 28px 8px 10px; }
}
"""


def build_html(data: dict) -> str:
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    run_type = data.get("run_type", "")
    run_label = {"morning": "朝(寄り付き前)更新", "evening": "夜(引け後)更新"}.get(run_type, run_type)

    us = data.get("us_market", {})
    fx = data.get("fx", {})
    fut = data.get("nikkei_futures", {})

    idx_cards = ""
    for key, label in [("sp500", "S&P500"), ("dow", "NYダウ"), ("nasdaq", "ナスダック総合")]:
        d = us.get(key, {})
        idx_cards += section_index_row(label, d.get("value", "―"), d.get("change_pct"), d.get("asof"))
    idx_cards += section_index_row("USD/JPY", fx.get("value", "―"), fx.get("change_pct"), fx.get("asof"))
    idx_cards += section_index_row("日経225先物(CME/大阪)", fut.get("value", "―"), fut.get("change_pct"), fut.get("asof"))
    idx_cards += section_index_row("日経平均(現物・前回終値)", data.get("nikkei225", {}).get("value", "―"),
                                     data.get("nikkei225", {}).get("change_pct"), data.get("nikkei225", {}).get("asof"))

    morning_html = f"""
    <section id="morning">
      <h2>🌅 寄り付き前セクション</h2>
      <p class="section-desc">前日の米国市場・為替・時間外ニュース・TDnet早朝までの開示・話題株をまとめています。当日の仕込み銘柄検討の参考情報です。</p>
      <div class="card">
        <h3>米国市場・為替・日経先物</h3>
        <div class="idx-grid">{idx_cards}</div>
      </div>
      <div class="card">
        <h3>時間外・朝の主要ニュース</h3>
        {news_list(data.get("overnight_news", []))}
      </div>
      <div class="card">
        <h3>TDnet 適時開示(朝までの分)</h3>
        {tdnet_table(data.get("tdnet_morning", []))}
      </div>
      <div class="card">
        <h3>出来高・値動きで話題の銘柄</h3>
        {movers_table(data.get("movers_morning", []))}
      </div>
    </section>"""

    evening_html = f"""
    <section id="evening">
      <h2>🌙 引け後セクション</h2>
      <p class="section-desc">本日のTDnet適時開示(決算・業績修正・自己株買いなど)と引け後の重要ニュースをまとめています。翌日以降の仕込み銘柄検討の参考情報です。</p>
      <div class="card">
        <h3>本日のTDnet適時開示</h3>
        {tdnet_table(data.get("tdnet_afterclose", []), empty_msg="本日の適時開示データは取得できませんでした。")}
      </div>
      <div class="card">
        <h3>引け後の主要ニュース</h3>
        {news_list(data.get("afterclose_news", []))}
      </div>
      <div class="card">
        <h3>本日の値動き・出来高で話題の銘柄</h3>
        {movers_table(data.get("movers_afterclose", []))}
      </div>
    </section>"""

    technical_html = f"""
    <section id="technical">
      <h2>📊 株価診断(テクニカル指標)</h2>
      <p class="section-desc">
        移動平均線・RSIなど無料で取得できるテクニカル指標にもとづく客観的な「強気/弱気シグナル」の一覧です。
        <b>将来の株価を予想・保証するものではありません。</b>
      </p>
      <div class="card">
        {technical_table(data.get("technical", []))}
      </div>
    </section>"""

    disclaimer_text = (
        "本ページの情報は、Yahoo!ファイナンス・TDnet(適時開示情報閲覧サービス)・投資の森(テクニカル分析)など"
        "無料で公開されている情報源をもとに自動的にまとめたものです。"
        "内容の正確性・完全性・最新性は保証されません。"
        "「強気/弱気シグナル」等の表示は移動平均線やRSIなど過去データに基づく機械的な診断であり、"
        "<b>投資助言ではなく、将来の株価変動を保証するものでもありません。</b>"
        "投資に関する最終判断は、必ずご自身の責任で行ってください。"
    )

    sources_html = """
    <div class="sources">
      主な情報源: Yahoo!ファイナンス (finance.yahoo.co.jp) / TDnet 適時開示情報閲覧サービス
      (release.tdnet.info, 非公式API: webapi.yanoshin.jp) / 投資の森 テクニカル分析 (nikkeiyosoku.com)。
      各情報の著作権・利用条件は提供元に帰属します。転載・再配布は行わず、個人の投資判断の参考情報としてのみ利用してください。
    </div>"""

    html_out = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>日本株デイトレード情報ダッシュボード</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>日本株(東証)デイトレード情報ダッシュボード<span class="run-badge">{esc(run_label)}</span></h1>
    <div class="subtitle">最終更新: {esc(generated_at)} (JST) ・ 毎日 朝6:00 / 夜21:00 に自動更新</div>
  </header>

  <div class="disclaimer">
    ⚠️ <b>本サイトは情報提供のみを目的とし、投資助言ではありません。</b> {disclaimer_text}
  </div>

  <nav class="tabs">
    <a href="#morning">🌅 寄り付き前</a>
    <a href="#evening">🌙 引け後</a>
    <a href="#technical">📊 株価診断</a>
  </nav>

  {morning_html}
  {evening_html}
  {technical_html}

  <footer>
    <div class="disclaimer">
      ⚠️ 再掲: {disclaimer_text}
    </div>
    {sources_html}
  </footer>
</div>
</body>
</html>
"""
    return html_out


def main():
    data_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "data.json"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE_DIR / "jp_daytrade_dashboard.html"

    if not data_path.exists():
        print(f"[ERROR] data.json が見つかりません: {data_path}", file=sys.stderr)
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    html_out = build_html(data)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"[OK] ダッシュボードを生成しました: {out_path}")


if __name__ == "__main__":
    main()
