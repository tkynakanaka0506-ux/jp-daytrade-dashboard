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

# 東京の夜景写真(Unsplash・商用利用可・クレジット表記不要)
# ヘッダー上部でゆっくりクロスフェードさせる背景写真
HERO_IMAGES = [
    "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?auto=format&fit=crop&w=1600&q=75",
    "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=1600&q=75",
    "https://images.unsplash.com/photo-1513407030348-c983a97b98d8?auto=format&fit=crop&w=1600&q=75",
    "https://images.unsplash.com/photo-1604928141064-207cea6f571f?auto=format&fit=crop&w=1600&q=75",
]


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
  --bg-deep: #000000; --bg-mid: #07060a; --bg-soft: #0a0908;
  --panel: linear-gradient(155deg, rgba(20,17,10,0.96), rgba(8,7,5,0.97));
  --panel2: rgba(255,255,255,0.03);
  --border: rgba(212,175,55,0.22); --border-soft: rgba(255,255,255,0.06);
  --text: #f3ede0; --muted: #9c9484;
  --accent: #d4af37; --accent-bright: #f5d78e; --accent-deep: #a9812f;
  --accent-soft: rgba(212,175,55,0.14); --accent-line: rgba(212,175,55,0.5);
  --up: #ff6b7a; --down: #35d9b4;
  --warn: #ffb84d; --bull: #ff6b7a; --bear: #35d9b4;
  --radius: 14px; --radius-sm: 10px;
  --shadow: 0 12px 34px rgba(0,0,0,0.6);
}
* { box-sizing: border-box; }
a { color: var(--accent-bright); text-decoration: none; }
a:visited { color: var(--accent-deep); }
a:hover { color: var(--accent); text-decoration: underline; }
body {
  margin: 0;
  font-family: 'Inter', -apple-system, "Hiragino Sans", "Yu Gothic", "Segoe UI", sans-serif;
  color: var(--text); line-height: 1.6;
  background-color: var(--bg-deep);
  background-image:
    radial-gradient(circle at 12% 4%, rgba(212,175,55,0.14), transparent 38%),
    radial-gradient(circle at 90% 2%, rgba(212,175,55,0.07), transparent 42%),
    radial-gradient(circle at 30% 94%, rgba(212,175,55,0.06), transparent 45%),
    radial-gradient(circle at 80% 72%, rgba(212,175,55,0.04), transparent 40%),
    linear-gradient(180deg, var(--bg-deep) 0%, var(--bg-mid) 45%, var(--bg-soft) 100%);
  background-attachment: fixed, fixed, fixed, fixed, fixed;
}
body::-webkit-scrollbar { width: 10px; }
body::-webkit-scrollbar-track { background: #000; }
body::-webkit-scrollbar-thumb { background: linear-gradient(180deg, var(--accent), var(--accent-deep)); border-radius: 6px; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 24px 20px 60px; }

/* --- ヒーロー: 東京の夜景写真がゆっくりクロスフェードする帯 --- */
.hero { position: relative; width: 100%; height: 300px; overflow: hidden; background: var(--bg-deep); }
.hero-slides { position: absolute; inset: 0; }
.hero-slide {
  position: absolute; inset: 0; background-size: cover; background-position: center;
  opacity: 0; transform: scale(1.08);
  filter: saturate(1.15) brightness(0.7);
  animation: heroFade 24s ease-in-out infinite;
}
@keyframes heroFade {
  0% { opacity: 0; }
  5% { opacity: 1; }
  22% { opacity: 1; }
  30% { opacity: 0; }
  100% { opacity: 0; }
}
.hero-overlay {
  position: absolute; inset: 0;
  background:
    radial-gradient(circle at 14% 18%, rgba(212,175,55,0.20), transparent 42%),
    radial-gradient(circle at 86% 8%, rgba(212,175,55,0.10), transparent 45%),
    linear-gradient(180deg, rgba(0,0,0,0.20) 0%, rgba(0,0,0,0.6) 55%, var(--bg-deep) 100%);
}
/* --- 固定見出しバー: 常に画面上部に表示される --- */
.topbar {
  position: sticky; top: 0; z-index: 25;
  background: linear-gradient(180deg, #050403 0%, #030302 100%);
  border-bottom: 1px solid var(--accent-line);
  box-shadow: 0 1px 0 rgba(212,175,55,0.12), 0 10px 30px rgba(0,0,0,0.6);
}
.topbar-inner {
  max-width: 1080px; margin: 0 auto; padding: 16px 20px;
  display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap;
}
.topbar-title { min-width: 0; }
.eyebrow {
  display: block; font-size: 9.5px; font-weight: 600; letter-spacing: 2.6px; text-transform: uppercase;
  color: var(--accent-deep); margin-bottom: 5px;
}
.eyebrow::before { content: "◆ "; color: var(--accent); }
h1 {
  font-family: "Playfair Display", "Hiragino Mincho ProN", serif;
  font-size: 19px; margin: 0 0 4px; font-weight: 700; letter-spacing: 0.4px;
  color: var(--accent);
  background: linear-gradient(120deg, var(--accent-bright) 0%, var(--accent) 45%, var(--accent-deep) 100%);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}
.subtitle { color: var(--muted); font-size: 11.5px; letter-spacing: 0.2px; }
.disclaimer {
  background: linear-gradient(155deg, rgba(24,19,8,0.94), rgba(10,8,4,0.96));
  border: 1px solid var(--accent-line); color: #e9d29c;
  border-radius: var(--radius-sm); padding: 14px 16px; font-size: 13px; margin: 16px 20px;
}
.disclaimer b { color: var(--accent-bright); }
nav.tabs {
  display: flex; gap: 10px; flex-wrap: wrap;
}
nav.tabs a {
  color: var(--accent-bright); text-decoration: none; font-size: 12.5px; letter-spacing: 0.3px;
  border: 1px solid var(--border);
  padding: 7px 16px; border-radius: 20px; background: rgba(212,175,55,0.05); white-space: nowrap;
  transition: border-color .15s ease, box-shadow .15s ease, color .15s ease, background .15s ease;
}
nav.tabs a:hover {
  color: #0a0805; border-color: var(--accent);
  background: linear-gradient(120deg, var(--accent-bright), var(--accent));
  box-shadow: 0 0 20px rgba(212,175,55,0.35);
}
section { margin: 32px 20px; }
section > h2 {
  font-family: "Playfair Display", "Hiragino Mincho ProN", serif;
  font-size: 18px; border-left: 2px solid var(--accent); padding-left: 12px; margin-bottom: 4px;
  font-weight: 700; letter-spacing: 0.3px; color: var(--accent-bright);
}
.section-desc { color: var(--muted); font-size: 12.5px; margin: 2px 0 14px; }
.card {
  background: var(--panel); border: 1px solid var(--border); border-top: 1px solid var(--accent-line);
  border-radius: var(--radius);
  padding: 18px 20px; margin-bottom: 16px; box-shadow: var(--shadow);
  transition: border-color .2s ease, box-shadow .2s ease;
}
.card:hover { border-color: var(--accent-line); box-shadow: var(--shadow), 0 0 24px rgba(212,175,55,0.08); }
.card h3 {
  font-size: 12px; margin: 0 0 12px; color: var(--accent); font-weight: 600;
  letter-spacing: 1.2px; text-transform: uppercase;
  padding-bottom: 8px; border-bottom: 1px solid var(--border-soft);
  position: relative;
}
.card h3::after {
  content: ""; position: absolute; left: 0; bottom: -1px; width: 34px; height: 1px;
  background: linear-gradient(90deg, var(--accent), transparent);
}
.idx-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }
.idx-card {
  background: var(--panel2); border: 1px solid var(--border-soft); border-radius: var(--radius-sm);
  padding: 10px 12px; transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
}
.idx-card:hover {
  border-color: var(--accent-line); box-shadow: 0 0 18px rgba(212,175,55,0.16);
  transform: translateY(-1px);
}
.idx-label { font-size: 11.5px; color: var(--muted); letter-spacing: 0.3px; text-transform: uppercase; }
.idx-value { font-size: 18px; font-weight: 700; margin-top: 3px; letter-spacing: 0.2px; color: var(--accent-bright); }
.chg { font-size: 13px; font-weight: 600; }
.chg.up, .up { color: var(--up); }
.chg.down, .down { color: var(--down); }
.chg.flat, .flat { color: var(--muted); }
.note { font-size: 11px; color: var(--muted); margin-top: 4px; }
.news-list { list-style: none; margin: 0; padding: 0; }
.news-list li { padding: 7px 0; border-bottom: 1px solid var(--border-soft); font-size: 13.5px; }
.news-list li:last-child { border-bottom: none; }
.news-list a { color: var(--text); text-decoration: none; }
.news-list a:hover { color: var(--accent-bright); }
.news-list .meta { display: block; color: var(--muted); font-size: 11px; margin-top: 2px; }
.scroll-hint { display: none; color: var(--muted); font-size: 11px; margin: 0 0 4px; }
.table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 10px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
.tdnet-table { min-width: 560px; }
.movers-table { min-width: 680px; }
.technical-table { min-width: 820px; }
th, td { text-align: left; padding: 8px 8px; border-bottom: 1px solid var(--border-soft); }
th {
  color: var(--accent); font-weight: 600; font-size: 11px; white-space: nowrap;
  letter-spacing: 0.8px; text-transform: uppercase; border-bottom: 1px solid var(--accent-line);
}
td.mono { font-family: "SF Mono", Menlo, monospace; white-space: nowrap; }
td.reason { color: var(--muted); }
tbody tr:nth-child(even) { background: rgba(212,175,55,0.02); }
tbody tr:hover { background: rgba(212,175,55,0.08); }
.badge { padding: 2px 9px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge.bull { background: rgba(255,107,122,0.15); color: var(--bull); border: 1px solid rgba(255,107,122,0.3); }
.badge.bear { background: rgba(53,217,180,0.15); color: var(--bear); border: 1px solid rgba(53,217,180,0.3); }
.badge.neutral { background: rgba(212,175,55,0.1); color: var(--muted); border: 1px solid var(--border-soft); }
.tag { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: var(--border-soft); color: var(--muted); margin-left: 4px; }
.tag-warn { background: rgba(255,184,77,0.18); color: var(--warn); }
.empty { color: var(--muted); font-size: 13px; }
footer { margin: 40px 20px 10px; color: var(--muted); font-size: 11.5px; border-top: 1px solid var(--accent-line); padding-top: 16px; }
footer .disclaimer { margin: 0 0 12px; }
.sources { font-size: 11px; color: var(--muted); }
.run-badge {
  display:inline-block; font-size:11px; padding:2px 10px; border-radius:10px;
  background: rgba(0,0,0,0.4); border:1px solid var(--accent-line); color: var(--accent-bright); margin-left:8px;
  letter-spacing: 0.3px;
}

/* --- PC(広い画面): 余白と最大幅を少し広げて読みやすくする --- */
@media (min-width: 1200px) {
  .wrap { max-width: 1240px; }
  body { font-size: 15.5px; }
  .idx-grid { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
  .hero { height: 360px; }
  .topbar-inner { max-width: 1240px; }
}

/* --- スマホ(狭い画面): 余白・文字サイズを詰めてタップしやすくする --- */
@media (max-width: 640px) {
  .wrap { padding: 12px 12px 48px; }
  .hero { height: 150px; }
  .topbar-inner { padding: 12px; flex-direction: column; align-items: flex-start; gap: 8px; }
  h1 { font-size: 15.5px; line-height: 1.4; }
  .subtitle { font-size: 11px; }
  .disclaimer { margin: 12px 8px; padding: 10px 12px; font-size: 12px; }
  nav.tabs { gap: 6px; }
  nav.tabs a { font-size: 12px; padding: 6px 10px; }
  section { margin: 20px 8px; }
  section > h2 { font-size: 15px; }
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

    n_slides = len(HERO_IMAGES)
    hero_slides_html = "".join(
        f'<div class="hero-slide" style="background-image:url(\'{esc(url)}\');'
        f' animation-delay:{i * (24 // n_slides)}s;"></div>'
        for i, url in enumerate(HERO_IMAGES)
    )

    html_out = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>日本株デイトレード情報ダッシュボード</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="hero">
  <div class="hero-slides">
    {hero_slides_html}
  </div>
  <div class="hero-overlay"></div>
</div>
<header class="topbar">
  <div class="topbar-inner">
    <div class="topbar-title">
      <span class="eyebrow">TOKYO STOCK EXCHANGE ・ DAY TRADE INTELLIGENCE</span>
      <h1>日本株(東証)デイトレード情報ダッシュボード<span class="run-badge">{esc(run_label)}</span></h1>
      <div class="subtitle">最終更新: {esc(generated_at)} (JST) ・ 毎日 朝6:00 / 夜21:00 に自動更新</div>
    </div>
    <nav class="tabs">
      <a href="#morning">🌅 寄り付き前</a>
      <a href="#evening">🌙 引け後</a>
      <a href="#technical">📊 株価診断</a>
    </nav>
  </div>
</header>
<div class="wrap">
  <div class="disclaimer">
    ⚠️ <b>本サイトは情報提供のみを目的とし、投資助言ではありません。</b> {disclaimer_text}
  </div>

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
