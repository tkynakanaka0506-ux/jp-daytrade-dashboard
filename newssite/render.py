#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""news.json から index.html(重要ニュース × 影響銘柄サイト)を生成する。

外部ライブラリもビルド工程も使わない素のHTML/CSS/JSを吐くだけなので、
デザインを変えたいときは下の CSS / テンプレート文字列を直接編集すればよい。
"""
import html
import json
from datetime import datetime

from .config import JST

YAHOO_QUOTE = "https://finance.yahoo.co.jp/quote/{code}.T"

DIRECTION_CLASS = {"positive": "up", "negative": "down", "watch": "flat"}
DIRECTION_MARK = {"positive": "▲", "negative": "▼", "watch": "●"}
ORIGIN_CLASS = {"direct": "origin-direct", "llm": "origin-llm", "rule": "origin-rule"}


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def stars(n):
    n = max(1, min(5, int(n or 1)))
    return "★" * n + "☆" * (5 - n)


def fmt_change(value):
    if value is None:
        return "", "flat"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "", "flat"
    cls = "up" if v > 0 else ("down" if v < 0 else "flat")
    return f"{v:+.2f}%", cls


def _relative(published_at, now):
    if not published_at:
        return ""
    try:
        dt = datetime.strptime(published_at, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
    except ValueError:
        return esc(published_at)
    minutes = int((now - dt).total_seconds() // 60)
    if minutes < 1:
        return "たった今"
    if minutes < 60:
        return f"{minutes}分前"
    if minutes < 24 * 60:
        return f"{minutes // 60}時間前"
    return f"{minutes // (60 * 24)}日前"


def market_bar_html(market):
    if not market:
        return ""
    cells = []
    for m in market:
        text, cls = fmt_change(m.get("change_pct"))
        cells.append(
            f'<div class="ticker"><span class="ticker-label">{esc(m["label"])}</span>'
            f'<span class="ticker-value">{esc(m["value"])}</span>'
            f'<span class="ticker-change {cls}">{esc(text)}</span></div>'
        )
    return f'<div class="market-bar">{"".join(cells)}</div>'


def impact_chip_html(imp):
    cls = DIRECTION_CLASS.get(imp["direction"], "flat")
    mark = DIRECTION_MARK.get(imp["direction"], "●")
    origin = {"direct": "当事者", "llm": "AI補強", "rule": imp.get("theme", "")}.get(imp.get("origin"), "")
    origin_cls = ORIGIN_CLASS.get(imp.get("origin"), "")
    return f"""
        <div class="chip {cls}" data-code="{esc(imp['code'])}">
          <button class="fav-star" type="button" data-fav-code="{esc(imp['code'])}"
                  title="お気に入り登録/解除" aria-label="お気に入り登録/解除">☆</button>
          <button class="chip-head" type="button" data-filter-code="{esc(imp['code'])}" title="この銘柄に関係するニュースだけ表示">
            <span class="chip-mark">{mark}</span>
            <span class="chip-name">{esc(imp['name'])}</span>
            <span class="chip-code">{esc(imp['code'])}</span>
            <span class="chip-strength">影響{esc(imp.get('strength', '中'))}</span>
          </button>
          <div class="chip-body">
            <span class="chip-tag {origin_cls}">{esc(origin)}</span>
            {f'<span class="chip-tag tier-{esc(imp["beneficiary_tier"])}">{esc(imp["beneficiary_tier_label"])}</span>' if imp.get('beneficiary_tier') else ''}
            {f'<span class="chip-tag">⏱ {esc(imp["revenue_horizon_label"])}</span>' if imp.get('revenue_horizon') else ''}
            {f'<span class="chip-tag" title="政策発表→予算確保→受注→設備投資→売上→利益のどこまで来ていそうか(政策の確度×業績到達時期の見積もりから推定。表示専用)">🛤 {esc(imp["policy_to_earnings_stage"])}</span>' if imp.get('policy_to_earnings_stage') else ''}
            {f'<span class="chip-tag" title="政策実現度×受益距離×時間軸×感応度の合成スコア(表示専用、銘柄判定には使っていません)">🎯 {esc(imp["policy_impact_score"])}</span>' if imp.get('policy_impact_score') is not None else ''}
            {f'<span class="chip-tag" title="巨大テックのAI設備投資サイクルが強さの拠り所(政府政策ではなく企業投資が起点。Policy Impact Scoreとは別物、表示専用)">🖥️ {esc(imp["ai_capex_impact_score"])}</span>' if imp.get('ai_capex_impact_score') is not None else ''}
            <span class="chip-reason">{esc(imp.get('reason', ''))}</span>
            <a class="chip-link" href="{esc(YAHOO_QUOTE.format(code=imp['code']))}" target="_blank" rel="noopener">株価 ↗</a>
          </div>
        </div>"""


def news_card_html(item, now):
    impacts = item.get("impacts", [])
    if impacts:
        chips = "".join(impact_chip_html(i) for i in impacts)
        pos = sum(1 for i in impacts if i["direction"] == "positive")
        neg = sum(1 for i in impacts if i["direction"] == "negative")
        watch = sum(1 for i in impacts if i["direction"] == "watch")
        counts = []
        if pos:
            counts.append(f'<span class="up">▲追い風 {pos}</span>')
        if neg:
            counts.append(f'<span class="down">▼逆風 {neg}</span>')
        if watch:
            counts.append(f'<span class="flat">●注目 {watch}</span>')
        impact_block = f"""
      <div class="impact-block">
        <div class="impact-head">影響が出うる銘柄 <span class="impact-counts">{" / ".join(counts)}</span></div>
        <div class="chips">{chips}</div>
      </div>"""
    else:
        impact_block = """
      <div class="impact-block empty">このニュースに対応する影響銘柄は、現在のルールでは特定できませんでした。</div>"""

    summary = f'<p class="summary">{esc(item["summary"])}</p>' if item.get("summary") else ""
    comment = (
        f'<p class="comment"><span class="comment-label">想定される波及</span>{esc(item["impact_comment"])}</p>'
        if item.get("impact_comment") else ""
    )
    themes = "".join(f'<span class="theme-tag">#{esc(t)}</span>' for t in item.get("themes", []))
    related = ""
    if item.get("related"):
        links = "".join(
            f'<li><a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])}</a>'
            f'<span class="related-source">{esc(r.get("source", ""))}</span></li>'
            for r in item["related"]
        )
        related = f"""
      <details class="related">
        <summary>同じ話題の他媒体 {len(item['related'])}件</summary>
        <ul>{links}</ul>
      </details>"""

    codes = " ".join(i["code"] for i in impacts)
    names = " ".join(i["name"] for i in impacts)
    search_blob = f"{item['title']} {item.get('source', '')} {' '.join(item.get('themes', []))} {codes} {names}"

    future_badge = (
        '<span class="future-badge" title="審議会・検討会・パブコメなど、報道になる前の一次情報らしき見出しです">'
        '🔮 先行情報</span>'
        if item.get("future_signal") else ""
    )
    maturity_score = item.get("policy_maturity")
    maturity_badge = (
        f'<span class="maturity-badge" data-maturity="{esc(maturity_score)}" '
        f'title="政策の進行段階(0=検討段階〜100=施策実施済み)。表示のみで銘柄判定には影響しません">'
        f'📊 {esc(item.get("policy_maturity_label", ""))} {esc(maturity_score)}</span>'
        if maturity_score is not None else ""
    )
    # ライフサイクル状態。NEW(初出)はほとんどの記事が該当し視覚ノイズに
    # なるため非表示にし、続報以降(UPDATE/MATURED/CLOSED)だけ明示する。
    lifecycle_state = item.get("policy_event_state")
    lifecycle_emoji = {"UPDATE": "🔁", "MATURED": "✅", "CLOSED": "🏁"}.get(lifecycle_state, "")
    lifecycle_label = {"UPDATE": "続報", "MATURED": "制度成立", "CLOSED": "施策実施済み"}.get(lifecycle_state, "")
    lifecycle_badge = (
        f'<span class="lifecycle-badge" data-state="{esc(lifecycle_state)}" '
        f'title="同じ政策の続報を束ねて追跡した進行状況(表示のみで銘柄判定には影響しません)">'
        f'{lifecycle_emoji} {esc(lifecycle_label)}</span>'
        if lifecycle_emoji else ""
    )
    novelty_badge = (
        f'<span class="novelty-badge" data-novelty="{esc(item.get("news_novelty"))}" '
        f'title="似た見出しが過去に記録されている、または複数媒体が同時報道済みです。'
        f'重要でも既に市場に知られている可能性があります(表示のみで銘柄判定には影響しません)">'
        f'♻️ {esc(item.get("news_novelty_label", ""))}</span>'
        if item.get("news_novelty") == "low" else ""
    )
    # ⑤ 一次情報/二次情報/市場解説。secondary(大多数)は無表示にして視覚的な
    # ノイズを避け、primary(信頼度を上げた)とcommentary(下げた)だけ明示する。
    source_tier = item.get("source_tier")
    source_tier_badge = (
        f'<span class="source-tier-badge tier-{esc(source_tier)}" '
        f'title="情報源の区分。政策インパクトスコアの信頼度に反映済み(一次情報=そのまま/'
        f'二次情報=×0.85/市場解説=×0.65)。表示のみでtheme/direction等の判定には影響しません">'
        f'{"🏛️" if source_tier == "primary" else "💬"} {esc(item.get("source_tier_label", ""))}</span>'
        if source_tier in ("primary", "commentary") else ""
    )
    return f"""
    <article class="news-card" data-category="{esc(item['category'])}" data-importance="{esc(item['importance'])}"
             data-codes="{esc(codes)}" data-search="{esc(search_blob)}" data-ts="{esc(item.get('published_at', ''))}"
             data-future="{'1' if item.get('future_signal') else '0'}"
             data-maturity="{esc(maturity_score) if maturity_score is not None else ''}">
      <div class="news-meta">
        <span class="stars" title="重要度 {esc(item['importance'])} / 5">{stars(item['importance'])}</span>
        <span class="cat">{esc(item.get('category_emoji', '📰'))} {esc(item.get('category_label', ''))}</span>
        {future_badge}
        {maturity_badge}
        {lifecycle_badge}
        {novelty_badge}
        {source_tier_badge}
        <span class="time">{esc(_relative(item.get('published_at'), now))}</span>
        <span class="source">{esc(item.get('source', ''))}</span>
        <button class="copy-link" type="button" data-url="{esc(item['url'])}" data-title="{esc(item['title'])}"
                title="リンクをコピー" aria-label="リンクをコピー">🔗 コピー</button>
      </div>
      <h3 class="news-title"><a href="{esc(item['url'])}" target="_blank" rel="noopener">{esc(item['title'])}</a></h3>
      {summary}
      {comment}
      <div class="themes">{themes}<span class="why" title="重要度の根拠">重要度の根拠: {esc(item.get('importance_reason', ''))}</span></div>
      {impact_block}
      {related}
    </article>"""


def ranking_html(rows):
    if not rows:
        return '<p class="empty">集計できる影響銘柄がありませんでした。</p>'
    out = []
    for i, row in enumerate(rows, 1):
        if row["score"] > 0:
            tone, label = "up", f"追い風 {row['positive']}件"
        elif row["score"] < 0:
            tone, label = "down", f"逆風 {row['negative']}件"
        else:
            tone, label = "flat", f"注目 {row['mentions']}件"
        details = "".join(
            f'<li class="{DIRECTION_CLASS.get(n["direction"], "flat")}">'
            f'<a href="{esc(n["url"])}" target="_blank" rel="noopener">{esc(n["title"])}</a></li>'
            for n in row.get("news", [])
        )
        out.append(f"""
      <div class="rank-row" data-code="{esc(row['code'])}">
        <div class="rank-line">
          <button class="rank-head" type="button" data-filter-code="{esc(row['code'])}"
                  title="この銘柄に関係するニュースだけ表示">
            <span class="rank-no">{i}</span>
            <span class="rank-name">{esc(row['name'])}<span class="rank-code">{esc(row['code'])}</span></span>
            <span class="rank-badge {tone}">{esc(label)}</span>
            <span class="rank-mentions">{row['mentions']}本</span>
          </button>
          <button class="fav-star" type="button" data-fav-code="{esc(row['code'])}"
                  title="お気に入り登録/解除" aria-label="お気に入り登録/解除">☆</button>
          <button class="rank-toggle" type="button" aria-label="関連ニュースの見出しを開く">▾</button>
        </div>
        <ul class="rank-news">{details}</ul>
      </div>""")
    return "".join(out)


def category_filter_html(categories, news):
    counts = {}
    for n in news:
        counts[n["category"]] = counts.get(n["category"], 0) + 1
    chips = ['<button class="filter-chip is-active" type="button" data-category="all">すべて'
             f'<span class="chip-count">{len(news)}</span></button>']
    for cat in categories:
        count = counts.get(cat["id"], 0)
        if not count:
            continue
        chips.append(
            f'<button class="filter-chip" type="button" data-category="{esc(cat["id"])}">'
            f'{esc(cat.get("emoji", "📰"))} {esc(cat["label"])}<span class="chip-count">{count}</span></button>'
        )
    return "".join(chips)


CSS = """
@property --card{
  syntax:'<color>';
  inherits:true;
  initial-value:rgba(10,26,19,.86);
}
@property --card-2{
  syntax:'<color>';
  inherits:true;
  initial-value:rgba(14,34,25,.86);
}
:root{
  --bg:#010402; --bg-soft:#050f0a; --card:rgba(10,26,19,.86); --card-2:rgba(14,34,25,.86);
  --line:rgba(120,255,180,.28); --text:#f4fff9; --muted:#8fe6b6;
  --up:#ff5d7a; --down:#3fd0ff; --flat:#e0c34a; --accent:#4dff7e; --accent-2:#22d3ee; --accent-3:#a78bfa;
  --accent-4:#ff4fa3; --accent-5:#ffb347; --accent-lime:#c6ff3d;
  animation:cardFill 8s ease-in-out infinite;
  --shadow:0 14px 40px rgba(0,0,0,.7), 0 0 0 1px rgba(57,255,136,.05);
  --glow:0 0 18px rgba(77,255,126,.45);
  --glow-cyan:0 0 16px rgba(34,211,238,.35);
  --glow-violet:0 0 16px rgba(167,139,250,.35);
  --glow-pink:0 0 16px rgba(255,79,163,.35);
  --glow-lime:0 0 18px rgba(198,255,61,.45);
  --glass-blur:blur(22px) saturate(150%);
  --glass-edge:inset 0 1px 0 rgba(255,255,255,.1), inset 0 0 0 1px rgba(57,255,136,.07);
  --font-body:"Noto Sans JP",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --font-head:"Zen Kaku Gothic New","Noto Sans JP",sans-serif;
  --font-mono:"JetBrains Mono","Noto Sans JP",monospace;
}
@keyframes cardFill{
  0%,100%{--card:rgba(10,26,19,.86); --card-2:rgba(14,34,25,.86);}
  50%{--card:rgba(8,32,38,.86); --card-2:rgba(10,38,44,.86);}
}
:root[data-theme="light"]{
  --bg:#eef7f1; --bg-soft:#ffffff; --card:rgba(255,255,255,.55); --card-2:rgba(235,250,242,.6);
  --line:rgba(4,60,35,.14); --text:#0c211a; --muted:#2e4a3d;
  --up:#c81e3c; --down:#0b6fa8; --flat:#8a6d1f; --accent:#0aa858; --accent-2:#0c8fae; --accent-3:#6d4aff;
  --accent-4:#d6297c; --accent-5:#c97a12; --accent-lime:#7cb500; animation:none;
  --shadow:0 8px 24px rgba(10,40,25,.1);
  --glow:0 0 0 rgba(0,0,0,0);
  --glow-cyan:0 0 0 rgba(0,0,0,0);
  --glow-violet:0 0 0 rgba(0,0,0,0);
  --glow-pink:0 0 0 rgba(0,0,0,0);
  --glow-lime:0 0 0 rgba(0,0,0,0);
  --glass-blur:blur(18px) saturate(140%);
  --glass-edge:inset 0 1px 0 rgba(255,255,255,.5), inset 0 0 0 1px rgba(10,168,88,.06);
}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;position:relative;isolation:isolate;color:var(--text);
  font-family:var(--font-body);
  line-height:1.7;-webkit-font-smoothing:antialiased;min-height:100vh}
body::before{content:"";position:fixed;inset:-10%;z-index:-2;
  background:
    radial-gradient(36% 30% at 10% 6%, rgba(77,255,126,.16), transparent 60%),
    radial-gradient(26% 24% at 40% 2%, rgba(198,255,61,.09), transparent 60%),
    radial-gradient(28% 26% at 92% 8%, rgba(34,211,238,.10), transparent 60%),
    radial-gradient(32% 30% at 84% 84%, rgba(124,92,255,.11), transparent 60%),
    radial-gradient(26% 26% at 4% 88%, rgba(255,79,163,.08), transparent 60%),
    radial-gradient(24% 24% at 55% 40%, rgba(255,179,71,.05), transparent 60%),
    linear-gradient(160deg, #000201 0%, #000704 45%, #000a06 75%, #000302 100%);
  filter:blur(70px) saturate(125%);
  animation:auroraDrift 26s ease-in-out infinite alternate, hueSwing 9s ease-in-out infinite;
}
@keyframes hueSwing{
  0%{filter:blur(70px) saturate(125%) hue-rotate(0deg)}
  50%{filter:blur(70px) saturate(140%) hue-rotate(24deg)}
  100%{filter:blur(70px) saturate(125%) hue-rotate(0deg)}
}
:root[data-theme="light"] body::before{animation:none}
:root[data-theme="light"] body::before{
  background:
    radial-gradient(38% 32% at 12% 8%, rgba(10,168,88,.28), transparent 60%),
    radial-gradient(32% 30% at 88% 14%, rgba(0,180,190,.16), transparent 60%),
    radial-gradient(34% 32% at 82% 88%, rgba(109,74,255,.12), transparent 60%),
    radial-gradient(26% 26% at 6% 88%, rgba(214,41,124,.09), transparent 60%),
    linear-gradient(160deg, #f4fbf6 0%, #e7f6ec 50%, #dcf3e6 100%);
  filter:blur(50px) saturate(130%);
}
body::after{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.5;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.35'/></svg>");
  mix-blend-mode:overlay}
:root[data-theme="light"] body::after{opacity:.15;mix-blend-mode:multiply}
@keyframes auroraDrift{
  0%{transform:translate3d(0,0,0) scale(1)}
  50%{transform:translate3d(-2%,1.5%,0) scale(1.04)}
  100%{transform:translate3d(1.5%,-2%,0) scale(1.02)}
}
a{color:inherit}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--flat)}
::selection{background:rgba(57,255,136,.3);color:#04120a}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:rgba(57,255,136,.25);border-radius:8px}
::-webkit-scrollbar-track{background:transparent}

header.site{position:sticky;top:0;z-index:20;background:rgba(4,14,10,.42);
  -webkit-backdrop-filter:var(--glass-blur);backdrop-filter:var(--glass-blur);
  border-bottom:1px solid var(--line);box-shadow:var(--glass-edge),0 8px 24px rgba(0,0,0,.3);
  overflow:hidden}
header.site::before{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(90deg,transparent,rgba(57,255,136,.5) 20%,rgba(34,211,238,.6) 50%,rgba(167,139,250,.5) 80%,transparent);
  height:2px;top:auto;bottom:0;opacity:.8}
:root[data-theme="light"] header.site{background:rgba(255,255,255,.5)}
.head-inner{max-width:1240px;margin:0 auto;padding:14px 20px 10px;
  display:flex;gap:16px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
.brand h1{margin:0;font-size:24px;font-weight:900;letter-spacing:.05em;font-family:var(--font-head);
  background:linear-gradient(100deg,var(--accent-lime) 0%,var(--accent) 30%,var(--accent-2) 60%,var(--accent-3) 85%,var(--accent-lime) 100%);
  background-size:220% auto;
  -webkit-background-clip:text;background-clip:text;color:transparent;
  filter:drop-shadow(0 0 16px rgba(57,255,136,.4));
  animation:titleShine 7s ease-in-out infinite}
:root[data-theme="light"] .brand h1{filter:none;animation:none}
@keyframes titleShine{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
.brand .eyebrow{font-size:12.5px;letter-spacing:.3em;color:var(--accent-2);text-transform:uppercase;
  font-family:"Orbitron","Noto Sans JP",sans-serif;position:relative;padding-left:14px}
.brand .eyebrow::before{content:"";position:absolute;left:0;top:50%;width:9px;height:9px;
  transform:translateY(-50%);border-left:2px solid var(--accent-2);border-top:2px solid var(--accent-2)}
.brand .sub{font-size:13.5px;color:var(--muted);margin-top:4px;font-variant-numeric:tabular-nums}
.head-actions{display:flex;gap:8px;align-items:center}
.theme-toggle{background:var(--card);border:1px solid var(--line);color:var(--text);
  border-radius:999px;padding:7px 13px;cursor:pointer;font-size:14.5px;transition:box-shadow .2s,border-color .2s}
.theme-toggle:hover{border-color:var(--accent);box-shadow:var(--glow)}

.market-bar{display:flex;gap:10px;overflow-x:auto;max-width:1240px;margin:0 auto;
  padding:0 20px 12px;scrollbar-width:thin}
.ticker{display:flex;gap:8px;align-items:baseline;background:var(--card);border:1px solid var(--line);
  -webkit-backdrop-filter:var(--glass-blur);backdrop-filter:var(--glass-blur);box-shadow:var(--glass-edge);
  border-radius:10px;padding:6px 12px;white-space:nowrap;font-size:13.5px}
.ticker-label{color:var(--muted);font-family:var(--font-head);font-size:12.5px}
.ticker-value{font-weight:700;font-family:var(--font-mono);font-variant-numeric:tabular-nums}
.ticker-change{font-weight:700;font-size:13.5px;font-family:var(--font-mono);font-variant-numeric:tabular-nums}

.wrap{max-width:1240px;margin:0 auto;padding:20px}
.notice{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
  -webkit-backdrop-filter:var(--glass-blur);backdrop-filter:var(--glass-blur);box-shadow:var(--glass-edge);
  border-radius:12px;padding:12px 16px;font-size:14px;color:var(--muted);margin-bottom:18px}
.notice b{color:var(--text)}
.notice.sample-banner{border-left-color:var(--flat);color:var(--text)}

.controls{position:sticky;top:74px;z-index:15;background:rgba(4,14,10,.32);
  -webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);padding:10px 0 12px;
  border-bottom:1px solid var(--line);margin-bottom:18px}
:root[data-theme="light"] .controls{background:rgba(255,255,255,.4)}
.filter-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.filter-chip{background:var(--card);border:1px solid var(--line);color:var(--text);border-radius:999px;
  -webkit-backdrop-filter:var(--glass-blur);backdrop-filter:var(--glass-blur);
  padding:6px 13px;font-size:14px;cursor:pointer;display:inline-flex;gap:6px;align-items:center;
  transition:box-shadow .2s,border-color .2s}
.filter-chip:hover{border-color:var(--accent);box-shadow:var(--glow)}
.filter-chip:not(.is-active):nth-of-type(5n+2){border-left:3px solid var(--accent-2)}
.filter-chip:not(.is-active):nth-of-type(5n+3){border-left:3px solid var(--accent-3)}
.filter-chip:not(.is-active):nth-of-type(5n+4){border-left:3px solid var(--accent-4)}
.filter-chip:not(.is-active):nth-of-type(5n+5){border-left:3px solid var(--accent-5)}
.filter-chip:not(.is-active):nth-of-type(5n+6){border-left:3px solid var(--accent-lime)}
.filter-chip.is-active{background:linear-gradient(100deg,var(--accent-lime),var(--accent),var(--accent-lime));
  background-size:220% auto;animation:duoFill 5s ease-in-out infinite;
  border-color:var(--accent);color:#04140b;font-weight:700;box-shadow:var(--glow)}
@keyframes duoFill{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
:root[data-theme="light"] .filter-chip.is-active{animation:none}
.chip-count{opacity:.95;font-size:12.5px;font-family:var(--font-mono)}
.search-row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.search-row input,.search-row select{background:var(--card);border:1px solid var(--line);color:var(--text);
  -webkit-backdrop-filter:var(--glass-blur);backdrop-filter:var(--glass-blur);
  border-radius:10px;padding:8px 12px;font-size:14.5px}
.search-row input:focus,.search-row select:focus{outline:none;border-color:var(--accent);box-shadow:var(--glow)}
.search-row input{flex:1;min-width:200px}
.active-filter{display:none;align-items:center;gap:8px;font-size:14px;color:var(--muted)}
.active-filter.is-on{display:inline-flex}
.active-filter button{background:transparent;border:1px solid var(--line);color:var(--text);
  border-radius:999px;padding:3px 10px;cursor:pointer;font-size:13.5px}
.fav-toggle.is-active{background:linear-gradient(135deg,var(--flat),var(--accent-5));color:#241a02;
  border-color:var(--flat);animation:none}
.future-toggle.is-active{background:linear-gradient(135deg,var(--accent-3),var(--accent-2));color:#0a0620;
  border-color:var(--accent-3);animation:none}
.future-badge{background:linear-gradient(135deg,var(--accent-3),var(--accent-2));color:#0a0620;
  border-radius:999px;padding:1px 10px;font-size:12px;font-weight:700;box-shadow:var(--glow-violet);
  white-space:nowrap}
.maturity-badge{background:var(--card-2);border:1px solid var(--line);color:var(--muted);
  border-radius:999px;padding:1px 10px;font-size:12px;white-space:nowrap;font-family:var(--font-mono)}
.novelty-badge{background:var(--card-2);border:1px solid rgba(224,195,74,.4);color:var(--flat);
  border-radius:999px;padding:1px 10px;font-size:12px;white-space:nowrap}
.source-tier-badge{border-radius:999px;padding:1px 10px;font-size:12px;white-space:nowrap;background:var(--card-2)}
.source-tier-badge.tier-primary{border:1px solid rgba(77,255,126,.4);color:var(--accent)}
.source-tier-badge.tier-commentary{border:1px solid rgba(224,195,74,.4);color:var(--flat)}
.lifecycle-badge{background:var(--card-2);border:1px solid var(--line);color:var(--muted);
  border-radius:999px;padding:1px 10px;font-size:12px;white-space:nowrap}
.lifecycle-badge[data-state="MATURED"]{border-color:rgba(77,255,126,.4);color:var(--accent)}
.lifecycle-badge[data-state="CLOSED"]{border-color:rgba(167,139,250,.4);color:var(--accent-3)}

.scroll-progress{position:fixed;top:0;left:0;height:3px;width:0%;z-index:30;
  background:linear-gradient(90deg,var(--accent-lime),var(--accent),var(--accent-2),var(--accent-3));
  box-shadow:0 0 10px rgba(77,255,126,.6);transition:width .12s linear}

.fav-star{background:transparent;border:0;color:var(--muted);cursor:pointer;font-size:15.5px;
  line-height:1;padding:4px;border-radius:6px;transition:color .15s,transform .15s}
.fav-star:hover{color:var(--flat);transform:scale(1.15)}
.fav-star.is-fav{color:var(--flat);text-shadow:0 0 10px rgba(224,195,74,.6)}
.chip{position:relative}
.chip .fav-star{position:absolute;top:4px;right:6px;z-index:2}
.chip-head{padding-right:26px}

.copy-link{margin-left:auto;background:transparent;border:1px solid var(--line);color:var(--muted);
  border-radius:999px;padding:2px 9px;font-size:12.5px;cursor:pointer;transition:border-color .15s,color .15s}
.copy-link:hover{border-color:var(--accent);color:var(--accent)}
.copy-link.is-copied{border-color:var(--accent);color:var(--accent)}

:is(a,button,input,select,summary):focus-visible{outline:2px solid var(--accent-2);outline-offset:2px;
  box-shadow:var(--glow-cyan)}

@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;
    transition-duration:.001ms!important;scroll-behavior:auto!important}
}

.layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:22px;align-items:start}
@media(max-width:960px){.layout{grid-template-columns:1fr}.controls{top:0}}

.news-card{background:var(--card);border:1px solid var(--line);border-radius:16px;
  -webkit-backdrop-filter:var(--glass-blur);backdrop-filter:var(--glass-blur);
  padding:18px 20px;margin-bottom:16px;box-shadow:var(--shadow),var(--glass-edge);
  transition:box-shadow .2s,border-color .2s}
.news-card:hover{border-color:var(--accent);box-shadow:var(--shadow),var(--glass-edge),var(--glow)}
.news-card[data-importance="5"]{border-left:4px solid var(--accent-4);box-shadow:var(--shadow),var(--glass-edge),var(--glow-pink)}
.news-card[data-importance="4"]{border-left:4px solid var(--accent-2);box-shadow:var(--shadow),var(--glass-edge),var(--glow-cyan)}
.news-meta{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:13.5px;color:var(--muted)}
.stars{color:#f2c744;letter-spacing:1px}
.cat{background:var(--card-2);border:1px solid var(--line);border-radius:999px;padding:2px 10px}
.news-title{margin:8px 0 6px;font-size:18.5px;line-height:1.55;font-family:var(--font-head);font-weight:700}
.news-title a{text-decoration:none}
.news-title a:hover{text-decoration:underline;color:var(--accent)}
.summary{margin:6px 0;font-size:15px;color:var(--text)}
.comment{margin:6px 0;font-size:14.5px;color:var(--muted);background:var(--card-2);
  border-radius:10px;padding:9px 12px}
.comment-label{display:inline-block;font-size:12.5px;color:var(--accent);margin-right:8px;font-weight:700}
.themes{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0 4px;font-size:13px;color:var(--muted)}
.theme-tag{background:var(--card-2);border:1px solid var(--line);border-radius:6px;padding:1px 8px}
.why{opacity:.95}

.impact-block{margin-top:12px;border-top:1px dashed var(--line);padding-top:12px}
.impact-block.empty{font-size:14px;color:var(--muted)}
.impact-head{font-size:14px;font-weight:700;margin-bottom:9px;display:flex;gap:10px;flex-wrap:wrap}
.impact-counts{font-weight:600;font-size:13.5px;display:flex;gap:10px}
.chips{display:grid;grid-template-columns:repeat(auto-fill,minmax(226px,1fr));gap:8px}
.chip{border:1px solid var(--line);border-radius:12px;background:var(--card-2);overflow:hidden;
  transition:box-shadow .2s,border-color .2s}
.chip:hover{border-color:var(--accent);box-shadow:var(--glow)}
.chip.up{border-left:3px solid var(--up)} .chip.down{border-left:3px solid var(--down)}
.chip.flat{border-left:3px solid var(--flat)}
.chip-head{width:100%;display:flex;gap:7px;align-items:baseline;background:transparent;border:0;
  color:var(--text);padding:8px 10px 4px;cursor:pointer;text-align:left;font-size:14.5px}
.chip-head:hover .chip-name{text-decoration:underline}
.chip.up .chip-mark{color:var(--up)} .chip.down .chip-mark{color:var(--down)}
.chip.flat .chip-mark{color:var(--flat)}
.chip-name{font-weight:700;font-family:var(--font-head)}
.chip-code{font-size:12.5px;color:var(--muted);font-family:var(--font-mono)}
.chip-strength{margin-left:auto;font-size:12px;color:var(--muted);white-space:nowrap}
.chip-body{padding:0 10px 9px;font-size:13px;color:var(--muted);display:flex;flex-wrap:wrap;gap:6px}
.chip-tag{background:var(--card);border:1px solid var(--line);border-radius:5px;padding:0 6px;font-size:12px}
.chip-tag.origin-direct{border-color:rgba(34,211,238,.5);color:var(--accent-2)}
.chip-tag.origin-llm{border-color:rgba(167,139,250,.5);color:var(--accent-3)}
.chip-tag.origin-rule{border-color:rgba(57,255,136,.4);color:var(--accent)}
.chip-tag.tier-direct{border-color:rgba(77,255,126,.5);color:var(--accent)}
.chip-tag.tier-primary{border-color:rgba(34,211,238,.5);color:var(--accent-2)}
.chip-tag.tier-secondary{border-color:rgba(255,179,71,.5);color:var(--accent-5)}
.chip-tag.tier-peripheral{border-color:var(--line);color:var(--muted)}
.chip-reason{flex:1 1 100%;line-height:1.55;color:var(--text)}
.chip-link{color:var(--accent);text-decoration:none;font-size:12.5px}

.related{margin-top:10px;font-size:13.5px;color:var(--muted)}
.related summary{cursor:pointer}
.related ul{margin:8px 0 0;padding-left:18px}
.related li{margin-bottom:4px}
.related-source{margin-left:8px;font-size:12.5px;opacity:.95}

aside.side{position:sticky;top:150px;max-height:calc(100vh - 170px);
  overflow-y:auto;overflow-x:hidden;padding-right:4px;scrollbar-width:thin}
aside.side::-webkit-scrollbar{width:8px}
aside.side::-webkit-scrollbar-thumb{background:rgba(57,255,136,.25);border-radius:8px}
@media(max-width:960px){aside.side{position:static;max-height:none;overflow-y:visible}}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 16px 8px;
  -webkit-backdrop-filter:var(--glass-blur);backdrop-filter:var(--glass-blur);
  box-shadow:var(--shadow),var(--glass-edge);margin-bottom:16px}
.panel h2{margin:0 0 4px;font-size:16.5px;font-family:var(--font-head);font-weight:900;letter-spacing:.02em}
.panel .panel-desc{margin:0 0 12px;font-size:13px;color:var(--muted)}
.rank-row{border-top:1px solid var(--line)}
.rank-row:first-of-type{border-top:0}
.rank-line{display:flex;align-items:center;gap:4px}
.rank-toggle{background:transparent;border:0;color:var(--muted);cursor:pointer;font-size:13.5px;
  padding:6px 4px;border-radius:6px}
.rank-toggle:hover{color:var(--accent)}
.rank-row.is-open .rank-toggle{transform:rotate(180deg)}
.rank-head{flex:1;display:flex;gap:9px;align-items:center;background:transparent;border:0;color:var(--text);
  padding:9px 2px;cursor:pointer;text-align:left;font-size:14.5px}
.rank-head:hover .rank-name{color:var(--accent)}
.rank-no{width:20px;font-size:12.5px;color:var(--muted)}
.rank-name{flex:1;font-weight:600}
.rank-code{display:block;font-size:12px;color:var(--muted);font-weight:400}
.rank-badge{font-size:12.5px;white-space:nowrap}
.rank-mentions{font-size:12.5px;color:var(--muted)}
.rank-news{display:none;margin:0 0 10px;padding-left:30px;font-size:13px}
.rank-row.is-open .rank-news{display:block}
.rank-news li{margin-bottom:4px}
.rank-news a{color:var(--muted);text-decoration:none}
.rank-news a:hover{color:var(--accent)}

.empty,.no-result{background:var(--card);border:1px dashed var(--line);border-radius:14px;
  -webkit-backdrop-filter:var(--glass-blur);backdrop-filter:var(--glass-blur);
  padding:20px;text-align:center;color:var(--muted);font-size:14.5px}
.no-result{display:none}
footer{margin-top:28px;padding:20px 0 40px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
footer a{color:var(--accent)}
.back-top{position:fixed;right:18px;bottom:18px;width:42px;height:42px;border-radius:50%;
  border:1px solid var(--line);background:var(--card);color:var(--text);cursor:pointer;display:none;
  -webkit-backdrop-filter:var(--glass-blur);backdrop-filter:var(--glass-blur);
  box-shadow:var(--shadow),var(--glass-edge);font-size:17.5px;transition:box-shadow .2s,border-color .2s}
.back-top.is-on{display:block}
.back-top:hover{border-color:var(--accent);box-shadow:var(--shadow),var(--glow)}
"""

JS = r"""
<script>
(function(){
  var root = document.documentElement;
  try{ if(localStorage.getItem('news_theme') === 'light'){ root.setAttribute('data-theme','light'); } }catch(e){}

  var toggle = document.getElementById('themeToggle');
  toggle && toggle.addEventListener('click', function(){
    var light = root.getAttribute('data-theme') === 'light';
    if(light){ root.removeAttribute('data-theme'); } else { root.setAttribute('data-theme','light'); }
    try{ localStorage.setItem('news_theme', light ? 'dark' : 'light'); }catch(e){}
  });

  var main = document.querySelector('main');
  var cards = Array.prototype.slice.call(document.querySelectorAll('.news-card'));
  var searchInput = document.getElementById('searchInput');
  var minStars = document.getElementById('minStars');
  var sortSelect = document.getElementById('sortSelect');
  var favOnlyToggle = document.getElementById('favOnlyToggle');
  var futureOnlyToggle = document.getElementById('futureOnlyToggle');
  var noResult = document.getElementById('noResult');
  var activeFilter = document.getElementById('activeFilter');
  var activeFilterText = document.getElementById('activeFilterText');
  var state = { category:'all', text:'', stars:0, code:'', sort:'new', favOnly:false, futureOnly:false };

  var favorites = [];
  try{ favorites = JSON.parse(localStorage.getItem('fav_stocks') || '[]'); }catch(e){ favorites = []; }
  function isFav(code){ return favorites.indexOf(code) !== -1; }
  function syncFavButtons(){
    document.querySelectorAll('.fav-star').forEach(function(btn){
      var on = isFav(btn.dataset.favCode);
      btn.classList.toggle('is-fav', on);
      btn.textContent = on ? '★' : '☆';
    });
  }
  function toggleFav(code){
    var i = favorites.indexOf(code);
    if(i === -1){ favorites.push(code); } else { favorites.splice(i, 1); }
    try{ localStorage.setItem('fav_stocks', JSON.stringify(favorites)); }catch(e){}
    syncFavButtons();
    if(state.favOnly){ apply(); }
  }

  function persist(){
    try{
      localStorage.setItem('news_filters', JSON.stringify({
        category: state.category, stars: state.stars, text: state.text,
        sort: state.sort, favOnly: state.favOnly, futureOnly: state.futureOnly
      }));
    }catch(e){}
  }
  try{
    var saved = JSON.parse(localStorage.getItem('news_filters') || 'null');
    if(saved){
      state.category = saved.category || 'all';
      state.stars = saved.stars || 0;
      state.text = saved.text || '';
      state.sort = saved.sort || 'new';
      state.favOnly = !!saved.favOnly;
      state.futureOnly = !!saved.futureOnly;
    }
  }catch(e){}

  function apply(){
    var shown = 0;
    cards.forEach(function(card){
      var ok = true;
      if(state.category !== 'all' && card.dataset.category !== state.category){ ok = false; }
      if(ok && state.stars && parseInt(card.dataset.importance,10) < state.stars){ ok = false; }
      if(ok && state.code && (' ' + card.dataset.codes + ' ').indexOf(' ' + state.code + ' ') === -1){ ok = false; }
      if(ok && state.favOnly){
        var codes = (card.dataset.codes || '').split(/\s+/).filter(Boolean);
        ok = codes.some(isFav);
      }
      if(ok && state.futureOnly && card.dataset.future !== '1'){ ok = false; }
      if(ok && state.text){
        var blob = (card.dataset.search || '').toLowerCase();
        ok = state.text.split(/\s+/).every(function(w){ return !w || blob.indexOf(w) !== -1; });
      }
      card.style.display = ok ? '' : 'none';
      if(ok){ shown++; }
    });
    noResult.style.display = shown ? 'none' : 'block';
    if(state.code){
      activeFilter.classList.add('is-on');
      activeFilterText.textContent = '銘柄コード ' + state.code + ' に関係するニュースのみ表示中';
    } else {
      activeFilter.classList.remove('is-on');
    }
  }

  function sortCards(){
    if(!main){ return; }
    var arr = cards.slice();
    if(state.sort === 'importance'){
      arr.sort(function(a,b){ return parseInt(b.dataset.importance,10) - parseInt(a.dataset.importance,10); });
    } else {
      arr.sort(function(a,b){ return (b.dataset.ts||'').localeCompare(a.dataset.ts||''); });
    }
    arr.forEach(function(card){ main.insertBefore(card, noResult); });
  }

  document.querySelectorAll('.filter-chip[data-category]').forEach(function(chip){
    chip.classList.toggle('is-active', chip.dataset.category === state.category);
    chip.addEventListener('click', function(){
      document.querySelectorAll('.filter-chip[data-category]').forEach(function(c){ c.classList.remove('is-active'); });
      chip.classList.add('is-active');
      state.category = chip.dataset.category;
      apply(); persist();
    });
  });
  if(searchInput){ searchInput.value = state.text; }
  if(minStars){ minStars.value = String(state.stars); }
  if(sortSelect){ sortSelect.value = state.sort; }
  if(favOnlyToggle){ favOnlyToggle.classList.toggle('is-active', state.favOnly); }
  if(futureOnlyToggle){ futureOnlyToggle.classList.toggle('is-active', state.futureOnly); }

  searchInput && searchInput.addEventListener('input', function(){
    state.text = searchInput.value.trim().toLowerCase();
    apply(); persist();
  });
  minStars && minStars.addEventListener('change', function(){
    state.stars = parseInt(minStars.value, 10) || 0;
    apply(); persist();
  });
  sortSelect && sortSelect.addEventListener('change', function(){
    state.sort = sortSelect.value;
    sortCards(); persist();
  });
  favOnlyToggle && favOnlyToggle.addEventListener('click', function(){
    state.favOnly = !state.favOnly;
    favOnlyToggle.classList.toggle('is-active', state.favOnly);
    apply(); persist();
  });
  futureOnlyToggle && futureOnlyToggle.addEventListener('click', function(){
    state.futureOnly = !state.futureOnly;
    futureOnlyToggle.classList.toggle('is-active', state.futureOnly);
    apply(); persist();
  });

  function flashCopied(btn){
    var original = btn.textContent;
    btn.textContent = 'コピーしました';
    btn.classList.add('is-copied');
    setTimeout(function(){ btn.textContent = original; btn.classList.remove('is-copied'); }, 1400);
  }
  function copyText(text){
    if(navigator.clipboard && navigator.clipboard.writeText){
      return navigator.clipboard.writeText(text);
    }
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try{ document.execCommand('copy'); }catch(e){}
    document.body.removeChild(ta);
    return Promise.resolve();
  }

  document.addEventListener('click', function(ev){
    var favBtn = ev.target.closest ? ev.target.closest('.fav-star') : null;
    if(favBtn){ toggleFav(favBtn.dataset.favCode); return; }

    var copyBtn = ev.target.closest ? ev.target.closest('.copy-link') : null;
    if(copyBtn){
      copyText(copyBtn.dataset.title + ' ' + copyBtn.dataset.url).then(function(){ flashCopied(copyBtn); });
      return;
    }

    var rankToggle = ev.target.closest ? ev.target.closest('.rank-toggle') : null;
    if(rankToggle){ rankToggle.closest('.rank-row').classList.toggle('is-open'); return; }
    var btn = ev.target.closest ? ev.target.closest('[data-filter-code]') : null;
    if(btn){
      state.code = (state.code === btn.dataset.filterCode) ? '' : btn.dataset.filterCode;
      apply();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
  });

  document.addEventListener('keydown', function(ev){
    var tag = document.activeElement ? document.activeElement.tagName : '';
    var typing = tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA';
    if(ev.key === '/' && !typing){
      ev.preventDefault();
      searchInput && searchInput.focus();
      return;
    }
    if(ev.key === 'Escape'){
      if(searchInput){ searchInput.value = ''; searchInput.blur(); }
      state.text = ''; state.code = '';
      apply(); persist();
    }
  });

  var clearBtn = document.getElementById('clearCode');
  clearBtn && clearBtn.addEventListener('click', function(){ state.code = ''; apply(); });

  var backTop = document.getElementById('backTop');
  var scrollProgress = document.getElementById('scrollProgress');
  function onScroll(){
    backTop.classList.toggle('is-on', window.scrollY > 600);
    if(scrollProgress){
      var h = document.documentElement;
      var scrollable = h.scrollHeight - h.clientHeight;
      scrollProgress.style.width = (scrollable > 0 ? (h.scrollTop / scrollable) * 100 : 0) + '%';
    }
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  backTop.addEventListener('click', function(){ window.scrollTo({ top:0, behavior:'smooth' }); });

  syncFavButtons();
  sortCards();
  apply();
  onScroll();
})();
</script>
"""

DISCLAIMER = (
    "本サイトは Google ニュースの公開RSSで集めた見出しを、あらかじめ定義したキーワードルール"
    "(および任意で生成AI)で機械的に分類・関連付けした<b>情報提供のみを目的としたページ</b>です。"
    "「影響が出うる銘柄」は、過去の一般的な連想関係にもとづく機械的な推定であり、"
    "<b>実際にその銘柄の株価が動くことを保証・予想するものではありません。投資助言でもありません。</b>"
    "見出しの解釈には誤りが含まれることがあります。必ずリンク先の原文と実際の株価をご自身で確認し、"
    "投資判断はご自身の責任で行ってください。"
)


def build_html(data):
    now = datetime.now(JST)
    news = data.get("news", [])
    categories = data.get("categories", [])
    counts = data.get("counts", {})

    cards = "".join(news_card_html(n, now) for n in news) or (
        '<p class="empty">今回はニュースを取得できませんでした。'
        '古い情報で判断してしまわないよう、前回取得した内容は表示していません。<br>'
        '次回の自動更新(市場時間帯は15分おき)をお待ちください。</p>'
    )
    sample_banner = (
        '<div class="notice sample-banner">🧪 <b>これはサンプルデータで生成した表示確認用のページです。</b>'
        '掲載されている見出しは実際のニュースではありません。</div>'
        if data.get("status") == "sample" else ""
    )
    llm_note = (
        "見出しの要約・波及コメントは生成AIによる補強を含みます。"
        if data.get("llm_used") else
        "今回は生成AIによる補強なし(キーワードルールのみ)で生成しています。"
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="日本株に影響しうる重要ニュースと、その影響が出うる銘柄をまとめた自動更新サイト">
<title>重要ニュース × 影響銘柄 | 日本株ニュースインパクト</title>
<script>try{{if(localStorage.getItem('news_theme')==='light'){{document.documentElement.setAttribute('data-theme','light');}}}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700&family=Zen+Kaku+Gothic+New:wght@500;700;900&family=JetBrains+Mono:wght@500;700&family=Orbitron:wght@600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="scroll-progress" id="scrollProgress"></div>
<header class="site">
  <div class="head-inner">
    <div class="brand">
      <div class="eyebrow">JAPAN EQUITY ・ NEWS IMPACT</div>
      <h1>重要ニュース × 影響銘柄</h1>
      <div class="sub">最終更新 {esc(data.get('generated_at', ''))} (JST) ・ ニュース {counts.get('news', 0)}件
        (うち重要度★4以上 {counts.get('high_importance', 0)}件) ・ 影響銘柄 {counts.get('stocks', 0)}銘柄</div>
    </div>
    <div class="head-actions">
      <button id="themeToggle" class="theme-toggle" type="button">🌗 テーマ</button>
    </div>
  </div>
  {market_bar_html(data.get('market', []))}
</header>

<div class="wrap">
  {sample_banner}
  <div class="notice">
    ⚠️ <b>投資助言ではありません。</b> 各ニュースの「影響が出うる銘柄」は、キーワードルールにもとづく
    機械的な関連付けであり、株価の値動きを保証するものではありません。{esc(llm_note)}
  </div>

  <div class="controls">
    <div class="filter-row">{category_filter_html(categories, news)}</div>
    <div class="search-row">
      <input id="searchInput" type="search" placeholder="キーワード・銘柄名・証券コードで絞り込み(例: 半導体 8035)">
      <select id="minStars">
        <option value="0">重要度: すべて</option>
        <option value="3">★3以上</option>
        <option value="4">★4以上</option>
        <option value="5">★5のみ</option>
      </select>
      <select id="sortSelect">
        <option value="new">新着順</option>
        <option value="importance">重要度順</option>
      </select>
      <button id="favOnlyToggle" class="filter-chip fav-toggle" type="button">★ お気に入りのみ</button>
      <button id="futureOnlyToggle" class="filter-chip future-toggle" type="button">🔮 先行情報のみ</button>
      <span class="active-filter" id="activeFilter">
        <span id="activeFilterText"></span>
        <button id="clearCode" type="button">解除</button>
      </span>
    </div>
  </div>

  <div class="layout">
    <main>
      {cards}
      <p class="no-result" id="noResult">条件に一致するニュースはありません。絞り込みを緩めてください。</p>
    </main>
    <aside class="side">
      <div class="panel">
        <h2>📌 材料が集まっている銘柄</h2>
        <p class="panel-desc">表示中のニュース全体で、影響銘柄として挙がった回数と方向を集計しています。
          クリックでその銘柄のニュースだけ表示します。</p>
        {ranking_html(data.get('stock_ranking', []))}
      </div>
      <div class="panel">
        <h2>🔎 このページの作り方</h2>
        <p class="panel-desc">
          Google ニュースRSSの見出しを収集 → 重複を束ねて重要度を採点 → キーワードルール
          (newssite/data/rules.json)で「影響が出うる銘柄」を紐づけ → このページを生成、という流れです。
          銘柄やルールは <code>newssite/data/stocks.json</code> と <code>newssite/data/rules.json</code> を
          編集するだけで変更できます。
        </p>
      </div>
    </aside>
  </div>

  <footer>
    <p>⚠️ {DISCLAIMER}</p>
    <p>情報源: Google ニュース RSS (news.google.com) / 株価リンク: Yahoo!ファイナンス。
      各情報の著作権は提供元に帰属します。</p>
    <p>以前のテクニカル指標つきデイトレードダッシュボードは
      <a href="dashboard.html">dashboard.html</a> に残しています。</p>
    <p>生成日時: {esc(data.get('generated_iso', ''))} ・ {esc(data.get('status_message', ''))}</p>
  </footer>
</div>
<button class="back-top" id="backTop" type="button" aria-label="上に戻る">↑</button>
{JS}
</body>
</html>
"""


def render_to_file(data, out_path):
    html_text = build_html(data)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    return html_text


def load_and_render(news_json_path, out_path):
    with open(news_json_path, encoding="utf-8") as f:
        data = json.load(f)
    return render_to_file(data, out_path)
