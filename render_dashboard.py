#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
æ¥æ¬æ ª(æ±è¨¼)ãã¤ãã¬ã¼ãæå ±ããã·ã¥ãã¼ã ã¬ã³ãã©ã¼
====================================================
data.json (ãã®ã¹ã¯ãªããã¨åããã©ã«ãã«ç½®ã) ãèª­ã¿è¾¼ã¿ã
è¦ãããHTMLããã·ã¥ãã¼ããçæããã

ãã®ã¹ã¯ãªããèªä½ã¯ãããã¯ã¼ã¯ã«ä¸åã¢ã¯ã»ã¹ããªãã
ãã¼ã¿åé(Webæ¤ç´¢ã»åå¾)ã¯Claude(ã¹ã±ã¸ã¥ã¼ã«ã¿ã¹ã¯)å´ã
æ¯å data.json ãä½ãç´ããã¨ã§è¡ãã

ä½¿ãæ¹:
    python3 render_dashboard.py [data.jsonã®ãã¹] [åºåhtmlã®ãã¹]
ããã©ã«ã:
    data.json ./data.json
    åºåå    ./jp_daytrade_dashboard.html
"""
import json
import re
import sys
import html as html_lib
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

# æ±äº¬ã®å¤æ¯åç(Unsplashã»åç¨å©ç¨å¯ã»ã¯ã¬ã¸ããè¡¨è¨ä¸è¦)
# ãµã¤ãå¨ä½ã®èæ¯ã«ä½¿ãåçãå®è¡æ¥ã¨æ/å¤ã®æ´æ°ã¿ã¤ãã³ã°ã«å¿ãã¦èªåçã«åãæ¿ããã
# (å­æ¬æ¨ãã«ãºã®å®¤åçªè¶ãã«ããã¯å½©åº¦ãä½ãã¢ãã¯ã­ã«è¦ããããé¤å¤ãã¦ãã)
# åèæ¯åçã¯ (URL, æ®å½±å°ã®ã©ãã«) ã®ã¿ãã«ãã©ãã«ã¯ãã¼ã¸æä¸é¨ã®ã­ã£ãã·ã§ã³è¡¨ç¤ºã«ä½¿ãã
BACKGROUND_IMAGES = [
    ("https://images.unsplash.com/photo-1759970752518-b0ffa38c130b?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æ±äº¬ã¿ã¯ã¼"),
    ("https://images.unsplash.com/photo-1749916884078-e8359b2adcdd?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æ¸è°·ã¹ã¯ã©ã³ãã«äº¤å·®ç¹"),
    ("https://images.unsplash.com/photo-1741097574041-d70d3fe6a3ab?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "ã¬ã¤ã³ãã¼ããªãã¸ã»ãå°å ´"),
    ("https://images.unsplash.com/photo-1768711478173-07768f32b426?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æ±äº¬ã¹ã«ã¤ããªã¼"),
    ("https://images.unsplash.com/photo-1758881606455-26cc1c2c8de4?auto=format&fit=crop&w=2400&q=90&sat=40&con=10&vib=25", "æ°å®¿"),
    ("https://images.unsplash.com/photo-1624434512895-2d1887ebfccf?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "å­æ¬æ¨"),
    ("https://images.unsplash.com/photo-1646547571578-bfd7b1457a65?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "ç§èå"),
    ("https://images.unsplash.com/photo-1690971324341-94fac8ec6873?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "ä¸¸ã®åã»æ±äº¬é§"),
    ("https://images.unsplash.com/photo-1622767833293-8d1e6878c27f?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "éåº§"),
    ("https://images.unsplash.com/photo-1671247913568-050c0bb925f5?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "è¡¨åéã¤ã«ããã¼ã·ã§ã³"),
    ("https://images.unsplash.com/photo-1771385706304-19ab1fb5fd61?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æµèã»é·é"),
    ("https://images.unsplash.com/photo-1703702238930-237f139e8115?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "ç¥æ¥½åã®è·¯å°"),
    ("https://images.unsplash.com/photo-1764418366176-0f273a921fab?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "ä¼è¦ç¨²è·å¤§ç¤¾(äº¬é½)"),
    ("https://images.unsplash.com/photo-1711006876033-8baac5dfa718?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æ±çã¤ã«ããã¼ã·ã§ã³"),
    ("https://images.unsplash.com/photo-1739614537933-11eed8f5d449?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æ¨ªæµã¿ãªã¨ã¿ãã"),
    ("https://images.unsplash.com/photo-1660292318896-0c684c801e3f?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "å­æ¬æ¨ãã«ãºå±æå°"),
    ("https://images.unsplash.com/photo-1764268845521-a115101cdde5?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æ± è¢"),
    ("https://images.unsplash.com/photo-1493515322954-4fa727e97985?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "ä¸éã®è£è·¯å°"),
    ("https://images.unsplash.com/photo-1601042879364-f3947d3f9c16?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "ææ¥½çºã»éåº§"),
    ("https://images.unsplash.com/photo-1617869884925-f8f0a51b2374?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æ­èä¼çº"),
    ("https://images.unsplash.com/photo-1626846136629-aa437fcb29a8?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "è¥¿æ°å®¿ã®é«å±¤ãã«ç¾¤"),
    ("https://images.unsplash.com/photo-1734753050499-e766acbe80ce?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "åå·ã»é«å±¤ãã«è¡"),
    ("https://images.unsplash.com/photo-1781525981877-ce6d8d80bcf8?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æ¸è°·ã»ã³ã¿ã¼è¡"),
    ("https://images.unsplash.com/photo-1617870314635-fc819547ec11?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "æ°å®¿ã»æãåºæ¨ªä¸"),
]


def pick_background_image(generated_at: str, run_type: str) -> str:
    """å®è¡æ¥(YYYY-MM-DD)ã¨æ/å¤ã®åºåããèæ¯åçãæ±ºå®ããã
    åãæ¥ã§ãæã¨å¤ã§éãåçã«ãªããæ¥ãå¤ããã¨ã­ã¼ãã¼ã·ã§ã³ãé²ãã"""
    urls = [u for u, _ in BACKGROUND_IMAGES]
    try:
        day_ordinal = datetime.strptime(generated_at[:10], "%Y-%m-%d").toordinal()
    except (ValueError, TypeError):
        day_ordinal = datetime.now().toordinal()
    slot = 0 if run_type == "morning" else 1
    idx = (day_ordinal * 2 + slot) % len(urls)
    return urls[idx]

def esc(x):
    if x is None:
        return ""
    return html_lib.escape(str(x))


def fmt_pct(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "â"
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


def mini_bar_html(value, scale=8.0):
    """åæ¥æ¯ãªã©ã®æ°å¤ããä¸­å¿ããå·¦å³ã«ä¼¸ã³ããã diverging bar ã¨ãã¦å¯è¦åããã
    çã®ã­ã¼ã½ã¯è¶³ãã£ã¼ãã«ã¯æç³»åOHLCãã¼ã¿ãå¿è¦ã§data.jsonã«ã¯å«ã¾ããªãããã
    æ¢å­ã®æ°å¤(åæ¥æ¯%ãªã©)ãè¦è¦çã«ææ¡ããããããç°¡æããã°ã©ãã¨ãã¦æä¾ããã"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    cls = pct_class(v)
    if cls == "flat":
        return '<span class="mini-bar" aria-hidden="true"></span>'
    magnitude = min(abs(v), scale) / scale * 50.0
    side = "right" if v > 0 else "left"
    return (
        f'<span class="mini-bar" aria-hidden="true">'
        f'<span class="mini-bar-fill {cls}" style="{side}:50%; width:{magnitude:.1f}%;"></span>'
        f'</span>'
    )


def rsi_gauge_html(rsi):
    """RSI(14)ã0-100ã®å¸¯ã°ã©ã+ãã¼ã«ã¼ã§å¯è¦åããç°¡æã²ã¼ã¸ã"""
    try:
        v = float(rsi)
    except (TypeError, ValueError):
        return esc(rsi)
    v_clamped = max(0.0, min(100.0, v))
    zone = "warn-hot" if v >= 70 else ("warn-cold" if v <= 30 else "normal")
    return (
        f'<span class="rsi-gauge">'
        f'<span class="rsi-gauge-track">'
        f'<span class="rsi-gauge-marker {zone}" style="left:{v_clamped:.1f}%;"></span>'
        f'</span>'
        f'<span class="rsi-gauge-num">{v:.1f}</span>'
        f'</span>'
    )


def code_link(code):
    """éæã³ã¼ããYahoo!ãã¡ã¤ãã³ã¹ã®è©²å½ãã¼ã¸ã¸ã®ãªã³ã¯ã«ãã(4æ¡åå¾ã®è¨¼å¸ã³ã¼ãã®ã¿)ã"""
    c = (code or "").strip()
    if not c:
        return ""
    if re.match(r"^\d{3,5}[A-Z]?$", c):
        return f'<a href="https://finance.yahoo.co.jp/quote/{esc(c)}.T" target="_blank" rel="noopener">{esc(c)}</a>'
    return esc(c)


def fav_btn_html(code):
    c = esc((code or "").strip())
    if not c:
        return ""
    return (
        f'<button class="fav-btn" type="button" data-code="{c}" '
        f'aria-label="ãæ°ã«å¥ãç»é²" aria-pressed="false">â</button> '
    )


def table_tools_html(placeholder="éæåã»ã³ã¼ãã§æ¤ç´¢"):
    return f'<div class="table-tools"><input type="search" class="table-search" placeholder="ð {esc(placeholder)}"></div>'


def signal_badge(signal):
    """signal: 'å¼·æ°' / 'å¼±æ°' / 'ä¸­ç«' ãªã©ã®æå­å -> è²ä»ãããã¸HTML"""
    s = (signal or "ä¸­ç«").strip()
    cls = "neutral"
    if "å¼·æ°" in s or "è²·ã" in s:
        cls = "bull"
    elif "å¼±æ°" in s or "å£²ã" in s:
        cls = "bear"
    return f'<span class="badge {cls}">{esc(s)}</span>'


def section_index_row(label, value, change=None, note=None):
    change_html = ""
    if change is not None and change != "":
        change_html = f'<span class="chg {pct_class(change)}">{fmt_pct(change)}</span>{mini_bar_html(change)}'
    note_html = f'<div class="note">{esc(note)}</div>' if note else ""
    return f"""
    <div class="idx-card">
      <div class="idx-label">{esc(label)}</div>
      <div class="idx-value">{esc(value)}</div>
      {change_html}
      {note_html}
    </div>"""


def news_list(items, empty_msg="ç¾æç¹ã§è©²å½ãããã¥ã¼ã¹ã¯åå¾ã§ãã¾ããã§ããã"):
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        title = esc(it.get("title", ""))
        url = esc(it.get("url", "")) or "#"
        source = esc(it.get("source", ""))
        time_ = esc(it.get("time", ""))
        meta = " / ".join(x for x in [time_, source] if x)

        # æè³é¢é£åéã»æ³¨ç®ä¼æ¥­(ãã¼ã¿ã«ããã°è¡¨ç¤ºãç¡ãå ´åã¯ä½ãåºããªã=æ§ãã¼ã¿ã¨ã®å¾æ¹äºæ)
        sector = esc((it.get("investment_sector") or "").strip())
        companies_raw = it.get("investment_companies") or ""
        if isinstance(companies_raw, list):
            companies = "ã".join(esc(str(c)) for c in companies_raw if str(c).strip())
        else:
            companies = esc(str(companies_raw).strip())
        impact_html = ""
        if sector or companies:
            bits = []
            if sector:
                bits.append(f'<span class="impact-sector">é¢é£åé: {sector}</span>')
            if companies:
                bits.append(f'<span class="impact-companies">æ³¨ç®ä¼æ¥­: {companies}</span>')
            impact_html = f'<div class="news-impact">{"".join(bits)}</div>'

        rows.append(
            f'<li><a href="{url}" target="_blank" rel="noopener">{title}</a>'
            f'<span class="meta">{meta}</span>'
            f'{impact_html}</li>'
        )
    return "<ul class=\"news-list\">" + "".join(rows) + "</ul>"


def tdnet_table(items, empty_msg="å¯¾è±¡æéã®é©æéç¤ºã¯åå¾ã§ãã¾ããã§ããã"):
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        time_ = esc(it.get("time", ""))
        code = it.get("code", "")
        company = esc(it.get("company", ""))
        title_raw = it.get("title", "") or ""
        title = esc(title_raw)
        url = esc(it.get("url", "")) or "#"
        tag_raw = it.get("tag", "") or ""
        tag = esc(tag_raw)
        tag_html = f'<span class="tag">{tag}</span>' if tag else ""
        sent_cls, sent_label = disclosure_sentiment(tag_raw, title_raw)
        sent_html = f'<span class="badge {sent_cls} sentiment-badge" title="ã¿ã¤ãã«ã®ã­ã¼ã¯ã¼ãã®ã¿ã§æ©æ¢°çã«å¤å®ããåèã©ãã«ã§ã">{sent_label}</span>'
        rows.append(f"""
        <tr>
          <td class="mono">{time_}</td>
          <td class="mono">{fav_btn_html(code)}{code_link(code)}</td>
          <td>{company}</td>
          <td>{sent_html}<a href="{url}" target="_blank" rel="noopener">{title}</a> {tag_html}</td>
        </tr>""")
    return f"""
    {table_tools_html("æå»ã»ã³ã¼ãã»ä¼ç¤¾åã»ã¿ã¤ãã«ã§æ¤ç´¢")}
    <p class="rank-note">ð¡ <b>ãã¸ãã£ã/ãã¬ãã£ã/ä¸­ç«</b>ã¯éç¤ºã¿ã¤ãã«ã®ã­ã¼ã¯ã¼ãä¸è´ã«ããæ©æ¢°çãªåèå¤å®ã§ããAIã«ããè©³ç´°åæã§ã¯ãªããæè³å©è¨ã§ãããã¾ããã</p>
    <div class="scroll-hint">â æ¨ªã«ã¹ã¯ã­ã¼ã«ã§ãã¾ã</div>
    <div class="table-scroll">
    <table class="tdnet-table" data-sortable="true">
      <thead><tr><th>æå»</th><th>ã³ã¼ã</th><th>ä¼ç¤¾å</th><th>éç¤ºã¿ã¤ãã«</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


def movers_table(items, empty_msg="è©²å½ãã¼ã¿ãåå¾ã§ãã¾ããã§ããã"):
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        code = it.get("code", "")
        name = esc(it.get("name", ""))
        price = esc(it.get("price", ""))
        chg = it.get("change_pct")
        vol_note = esc(it.get("volume_note", ""))
        reason = esc(it.get("reason", ""))
        rows.append(f"""
        <tr>
          <td class="mono">{fav_btn_html(code)}{code_link(code)}</td>
          <td>{name}</td>
          <td class="mono">{price}</td>
          <td class="mono {pct_class(chg)}">{fmt_pct(chg)}{mini_bar_html(chg)}</td>
          <td>{vol_note}</td>
          <td class="reason">{reason}</td>
        </tr>""")
    return f"""
    {table_tools_html()}
    <div class="scroll-hint">â æ¨ªã«ã¹ã¯ã­ã¼ã«ã§ãã¾ã</div>
    <div class="table-scroll">
    <table class="movers-table" data-sortable="true">
      <thead><tr><th>ã³ã¼ã</th><th>éæå</th><th>æ ªä¾¡</th><th>åæ¥æ¯</th><th>åºæ¥é«ã¡ã¢</th><th>è©±é¡ã®èæ¯</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


def technical_table(items, empty_msg="ãã¯ãã«ã«ãã¼ã¿ãåå¾ã§ãã¾ããã§ããã"):
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        code = it.get("code", "")
        name = esc(it.get("name", ""))
        price = esc(it.get("price", ""))
        chg = it.get("change_pct")
        ma5 = esc(it.get("ma5_dev", ""))
        ma25 = esc(it.get("ma25_dev", ""))
        rsi = it.get("rsi", "")
        rsi_html = rsi_gauge_html(rsi)
        rsi_note = ""
        try:
            rsi_f = float(rsi)
            if rsi_f >= 70:
                rsi_note = ' <span class="tag tag-warn">éç±æ</span>'
            elif rsi_f <= 30:
                rsi_note = ' <span class="tag tag-warn">å£²ããéã</span>'
        except (TypeError, ValueError):
            pass
        signal = it.get("signal", "ä¸­ç«")
        summary = esc(it.get("summary", ""))
        rows.append(f"""
        <tr>
          <td class="mono">{fav_btn_html(code)}{code_link(code)}</td>
          <td>{name}</td>
          <td class="mono">{price}</td>
          <td class="mono {pct_class(chg)}">{fmt_pct(chg)}{mini_bar_html(chg)}</td>
          <td class="mono">{ma5}</td>
          <td class="mono">{ma25}</td>
          <td class="mono">{rsi_html}{rsi_note}</td>
          <td>{signal_badge(signal)}</td>
          <td class="reason">{summary}</td>
        </tr>""")
    return f"""
    {table_tools_html()}
    <div class="scroll-hint">â æ¨ªã«ã¹ã¯ã­ã¼ã«ã§ãã¾ã</div>
    <div class="table-scroll">
    <table class="technical-table" data-sortable="true">
      <thead><tr><th>ã³ã¼ã</th><th>éæå</th><th>æ ªä¾¡</th><th>åæ¥æ¯</th><th>5æ¥ç·ä¹é¢</th><th>25æ¥ç·ä¹é¢</th><th>RSI(14)</th><th>ã·ã°ãã«</th><th>ã³ã¡ã³ã</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


def parse_signal_counts(summary):
    """summaryæå­åãããä¸­ç«X/å£²ãY/è²·ãZãã¾ãã¯ãå£²ãY/ä¸­ç«X/è²·ãZãå½¢å¼ã®ã·ã°ãã«åè¨³ãæ½åºãè¦ã¤ãããªããã°Noneã"""
    if not summary:
        return None
    # å½¢å¼1: å£²ãN/ä¸­ç«N/è²·ãN (æ°ãã©ã¼ããã)
    m = re.search(r"å£²ã\s*(\d+)\s*/\s*ä¸­ç«\s*(\d+)\s*/\s*è²·ã\s*(\d+)", summary)
    if m:
        sell, neutral, buy = (int(x) for x in m.groups())
        return {"neutral": neutral, "sell": sell, "buy": buy}
    # å½¢å¼2: ä¸­ç«N/å£²ãN/è²·ãN (æ§ãã©ã¼ããã)
    m = re.search(r"ä¸­ç«\s*(\d+)\s*/\s*å£²ã\s*(\d+)\s*/\s*è²·ã\s*(\d+)", summary)
    if m:
        neutral, sell, buy = (int(x) for x in m.groups())
        return {"neutral": neutral, "sell": sell, "buy": buy}
    return None
def rank_label(i):
    medals = ["ð¥", "ð¥", "ð¥"]
    return medals[i] if i < len(medals) else f"{i + 1}ä½"


def bull_ranking_html(items, empty_msg="ã·ã°ãã«ãã¼ã¿ãåå¾ã§ãã¾ããã§ããã"):
    """ãã¯ãã«ã«ææ¨ã®ãè²·ãã·ã°ãã«æ°ããè»¸ã«ãããéå»ãã¼ã¿ãã¼ã¹ã®æ©æ¢°çã©ã³ã­ã³ã°ã
    å°æ¥ã®æ ªä¾¡ä¸æãäºæ³ã»ä¿è¨¼ãããã®ã§ã¯ãªãã"""
    ranked = []
    for it in items:
        counts = parse_signal_counts(it.get("summary", ""))
        if not counts:
            continue
        score = counts["buy"] * 2 - counts["sell"]
        ranked.append((score, counts, it))
    if not ranked:
        return f'<p class="empty">{esc(empty_msg)}</p>'

    def rsi_key(entry):
        try:
            return float(entry[2].get("rsi", 50))
        except (TypeError, ValueError):
            return 50.0

    ranked.sort(key=lambda e: (-e[0], rsi_key(e)))

    def build_rows(group):
        rows = []
        for i, (score, counts, it) in enumerate(group[:5]):
            code = esc(it.get("code", ""))
            name = esc(it.get("name", ""))
            chg = it.get("change_pct")
            rsi = it.get("rsi", "")
            detail = f"ä¸­ç«{counts['neutral']}/å£²ã{counts['sell']}/è²·ã{counts['buy']}"
            overheat = ""
            try:
                if float(rsi) >= 70:
                    overheat = ' <span class="tag tag-warn">éç±æã«æ³¨æ</span>'
            except (TypeError, ValueError):
                pass
            rows.append(f"""
        <div class="rank-item">
          <div class="rank-num">{rank_label(i)}</div>
          <div class="rank-body">
            <div class="rank-head">
              <span class="mono">{code}</span> {name}
              <span class="mono {pct_class(chg)}">{fmt_pct(chg)}</span>
              <span class="score-tag">å¼·æ°ã¹ã³ã¢ {score:+d}</span>
            </div>
            <div class="rank-desc">ã·ã°ãã«å¤å®: {esc(detail)} ã» RSI(14) {esc(rsi)}{overheat}</div>
          </div>
        </div>""")
        return rows

    bull_items = sorted([(s, c, it) for s, c, it in ranked if s > 0], key=lambda e: (-e[0], rsi_key(e)))
    bear_items = sorted([(s, c, it) for s, c, it in ranked if s < 0], key=lambda e: (e[0], rsi_key(e)))

    html_parts = []
    html_parts.append('<h4 style="margin:0.5em 0 0.4em;color:var(--up)">ð¢ å¼·æ°ï¼è²·ãã·ã°ãã«åªå¢ï¼</h4>')
    if bull_items:
        html_parts.extend(build_rows(bull_items))
    else:
        html_parts.append('<p class="empty">ç¾å¨ãè²·ãã·ã°ãã«åªå¢ã®éæã¯ããã¾ããã</p>')
    html_parts.append('<h4 style="margin:1.2em 0 0.4em;color:var(--down)">ð´ å¼±æ°ï¼å£²ãã·ã°ãã«åªå¢ï¼</h4>')
    if bear_items:
        html_parts.extend(build_rows(bear_items))
    else:
        html_parts.append('<p class="empty">ç¾å¨ãå£²ãã·ã°ãã«åªå¢ã®éæã¯ããã¾ããã</p>')
    return "".join(html_parts)


def _technical_lookup(technical):
    """code -> technicalææ¨dict ã®ã«ãã¯ã¢ãããã¼ãã«ãä½ãã"""
    lookup = {}
    for t in technical or []:
        code = str(t.get("code", "")).strip()
        if code:
            lookup[code] = t
    return lookup


def _outlook_comment(code, tech_lookup):
    """ç´è¿ã®ãã¯ãã«ã«ææ¨(RSIã»ç§»åå¹³åä¹é¢ã»ã·ã°ãã«å¤å®)ããããã®éæã«ã¤ãã¦
    ç«¯çãªåèã³ã¡ã³ããæ©æ¢°çã«çµã¿ç«ã¦ããéå»ã®å¤åãå¾åã«åºã¥ãåèæå ±ã§ããã
    ä»å¾ã®æ ªä¾¡å¤åãä¿è¨¼ã»äºæ³ãããã®ã§ã¯ãªãã"""
    t = tech_lookup.get(str(code).strip())
    if not t:
        return "ç´è¿ã®ãã¯ãã«ã«ãã¼ã¿ã¯ä»ååå¾ã§ãã¾ããã§ãããå¤åãã¯åç¨®æ ªä¾¡æå ±ãµã¼ãã¹ã§ãç¢ºèªãã ããã"

    parts = []
    rsi = t.get("rsi")
    if isinstance(rsi, (int, float)):
        if rsi >= 70:
            parts.append(f"RSI(14)ã¯{rsi:.1f}ã§è²·ããããæ°´æºã«ãããç­æçãªéç±æã«çæ")
        elif rsi <= 30:
            parts.append(f"RSI(14)ã¯{rsi:.1f}ã§å£²ããããæ°´æº")
        else:
            parts.append(f"RSI(14)ã¯{rsi:.1f}ã§ä¸­ç«å")

    ma25 = t.get("ma25_dev")
    if ma25:
        parts.append(f"25æ¥ç·ãã{esc(ma25)}ä¹é¢")

    signal = t.get("signal")
    if signal:
        parts.append(f"ã·ã°ãã«å¤å®ã¯ã{esc(signal)}ã")

    if not parts:
        return "ãã¯ãã«ã«ææ¨ã®åèå¤ãç¾æç¹ã§ä¸è¶³ãã¦ãã¾ãã"
    return "ã".join(parts) + "ãç´è¿ã®å¤åãå¾åã«åºã¥ãæ©æ¢°çãªåèæå ±ã§ãããå°æ¥ã®æ ªä¾¡å¤åãä¿è¨¼ãããã®ã§ã¯ããã¾ããã"



# æ¥æ¬æ ª(TDnetéç¤º)ã®å¥½ææã«ãã´ãªå®ç¾©:éã¿ã»å¼·ãã©ãã«ã»å·ä½çãªå¥½ææåå®¹ã»
# éå»ã®é¡ä¼¼éç¤ºã«åºã¥ãæ³å®ã¤ã³ãã¯ã(åèå¤)ã»å¥½ææã¨å¤æ­ããçç±ãã¾ã¨ãã¦ä¿æããã
# æ³å®ã¤ã³ãã¯ãã¯ããã¾ã§éå»ã®é¡ä¼¼ã±ã¼ã¹ã®ä¸è¬çãªå¾åãç¤ºãåèå¤ã§ããã
# æ ªä¾¡ãå®éã«ãã®éãä¸æãããã¨ãç¢ºç´ã»äºæ³ãããã®ã§ã¯ãªãã
JP_CATALYST_INFO = {
    "æé«ç": {
        "weight": 5, "strength": "éå¸¸ã«å¼·ãå¥½ææ",
        "content": "éå»æé«ã®æ¥­ç¸¾(ç´å©çã»å¶æ¥­å©çãªã©)ãè¨é²ã»æ´æ°ãããã¨ãéç¤º",
        "impact": "+5%ã+12%ç¨åº¦",
        "reason": "æ¥­ç¸¾ãå¸å ´ã®æ³å®ãä¸åããã¼ã¹ã§ä¼¸ã³ã¦ãããã¨ãç¤ºããä»å¾ã®å¢çæå¾ããæ ªä¾¡è©ä¾¡ãè¦ç´ããããããã",
    },
    "å¢åå¢ç": {
        "weight": 4, "strength": "å¼·ãå¥½ææ",
        "content": "å£²ä¸ã»å©çãããããåææ¯ã§å¢å ãããã¨ãéç¤º",
        "impact": "+3%ã+8%ç¨åº¦",
        "reason": "åçæ§ã¨æé·æ§ã®ä¸¡æ¹ãæ¹åãã¦ãããã¨ãç¢ºèªãããæ¥­ç¸¾ã®è³ªã®é«ããè©ä¾¡ããããããã",
    },
    "ç¹å¥éå½": {
        "weight": 4, "strength": "å¼·ãå¥½ææ",
        "content": "éå¸¸éå½ã«å ãã¦ç¹å¥éå½ãå®æ½ãããã¨ãéç¤º",
        "impact": "+2%ã+6%ç¨åº¦",
        "reason": "ä¼ç¤¾ã®è³éä½åãæ ªä¸»éåå§¿å¢ã®å¼·ããç¤ºãã·ã°ãã«ã¨ãã¦åãæ­¢ãããããããã",
    },
    "ä¸æ¹ä¿®æ­£": {
        "weight": 4, "strength": "å¼·ãå¥½ææ",
        "content": "æ¥­ç¸¾äºæ³(å£²ä¸ã»å©ç)ãä¸æ¹ä¿®æ­£ãããã¨ãéç¤º",
        "impact": "+3%ã+8%ç¨åº¦",
        "reason": "ä¼ç¤¾èªèº«ãæ¥­ç¸¾è¦éããå¼ãä¸ãããã¨ã§ãã¢ããªã¹ãäºæ³ãå¸å ´æå¾ã®ä¸æ¯ãã«ã¤ãªããããããã",
    },
    "æ¥­ç¸¾ä¸æ¹ä¿®æ­£": {
        "weight": 4, "strength": "å¼·ãå¥½ææ",
        "content": "æ¥­ç¸¾äºæ³(å£²ä¸ã»å©ç)ãä¸æ¹ä¿®æ­£ãããã¨ãéç¤º",
        "impact": "+3%ã+8%ç¨åº¦",
        "reason": "ä¼ç¤¾èªèº«ãæ¥­ç¸¾è¦éããå¼ãä¸ãããã¨ã§ãã¢ããªã¹ãäºæ³ãå¸å ´æå¾ã®ä¸æ¯ãã«ã¤ãªããããããã",
    },
    "å¢é": {
        "weight": 3, "strength": "ããå¼·ãå¥½ææ",
        "content": "1æ ªå½ããéå½ãå¢é¡(å¢é)ãããã¨ãéç¤º",
        "impact": "+2%ã+5%ç¨åº¦",
        "reason": "éå½å¢é¡ã¯çµå¶é£ãæ¥­ç¸¾ã®åè¡ãã«èªä¿¡ãæã£ã¦ãããã¨ã®è¡¨ãã¨ãããæ ªä¸»éåå¼·åã¸ã®è©ä¾¡ãé«ã¾ãããããã",
    },
    "å¢é": {
        "weight": 3, "strength": "ããå¼·ãå¥½ææ",
        "content": "1æ ªå½ããéå½ãå¢é¡(å¢é)ãããã¨ãéç¤º",
        "impact": "+2%ã+5%ç¨åº¦",
        "reason": "éå½å¢é¡ã¯çµå¶é£ãæ¥­ç¸¾ã®åè¡ãã«èªä¿¡ãæã£ã¦ãããã¨ã®è¡¨ãã¨ãããæ ªä¸»éåå¼·åã¸ã®è©ä¾¡ãé«ã¾ãããããã",
    },
    "èªå·±æ ªè²·ã": {
        "weight": 2, "strength": "ããå¼·ãå¥½ææ",
        "content": "èªå·±æ ªå¼ã®åå¾(æ ªä¸»éåç­)ãå®æ½ãããã¨ãéç¤º",
        "impact": "+1%ã+4%ç¨åº¦",
        "reason": "æ ªå¼æ°ã®æ¸å°ã«ãã1æ ªå½ããææ¨(EPSãªã©)ãæ¹åãããããéçµ¦é¢ã§ãè²·ãæ¯ãè¦å ã«ãªãããããã",
    },
    "æ ªå¼åå²": {
        "weight": 2, "strength": "è»½ãã®å¥½ææ",
        "content": "æ ªå¼åå²ãå®æ½ãããã¨ãéç¤º",
        "impact": "+1%ã+3%ç¨åº¦",
        "reason": "1æ ªå½ããã®è³¼å¥åä¾¡ãä¸ããåäººæè³å®¶ãè²·ãããããªããã¨ã§ãéçµ¦ãæ¹åãããããã",
    },
    "éå½": {
        "weight": 1, "strength": "è»½ãã®å¥½ææ",
        "content": "éå½ã«é¢ããéç¤º",
        "impact": "+1%ã+3%ç¨åº¦",
        "reason": "æ ªä¸»éåã«é¢ãããã©ã¹ã®æå ±ã¨ãã¦åãæ­¢ãããããããã",
    },
}
# å¼±ææã­ã¼ã¯ã¼ããå«ã¾ããéç¤ºã¯ãå¥½ææã©ã³ã­ã³ã°ãã®å¯¾è±¡ããé¤å¤ããã
JP_NEGATIVE_KEYWORDS = ["ä¸æ¹ä¿®æ­£", "æ¸é", "ç¹å¥æå¤±", "æ¥­ç¸¾æªå", "èµ¤å­"]

# ç±³å½æ ªã®å¥½ææã«ãã´ãªå®ç¾©(ãã¼ã¿åéã¿ã¹ã¯å´ã headline/category ä»ãã§åéãã
# å¥½ææãã¥ã¼ã¹ãå¯¾è±¡ã¨ãããã«ãã´ãªãã¨ã®æ³å®ã¤ã³ãã¯ãã¯ãéå»ã®é¡ä¼¼ãã¥ã¼ã¹ã«å¯¾ãã
# ä¸è¬çãªæ ªä¾¡åå¿å¾åãç¤ºãåèå¤ã§ãããç¢ºç´ã»äºæ³ã§ã¯ãªã)ã
US_CATALYST_INFO = {
    "earnings_beat": {
        "weight": 5, "strength": "å¼·ãå¥½ææ",
        "content": "å¸å ´äºæ³(ã¢ããªã¹ãäºæ³)ãä¸åãæ±ºç®(å£²ä¸ã»EPSãªã©)ãçºè¡¨",
        "impact": "+3%ã+10%ç¨åº¦",
        "reason": "å®ç¸¾ãäºåã®ã¢ããªã¹ãäºæ³ãä¸åã£ããã¨ã§ãæ¥­ç¸¾ã¸ã®è©ä¾¡ãä¸åãã«è¦ç´ããããããã",
    },
    "guidance_raise": {
        "weight": 4, "strength": "å¼·ãå¥½ææ",
        "content": "æ¬¡æä»¥éã®æ¥­ç¸¾è¦éã(ã¬ã¤ãã³ã¹)ãä¸æ¹ä¿®æ­£",
        "impact": "+3%ã+8%ç¨åº¦",
        "reason": "ä¼ç¤¾èªèº«ãåè¡ãã®æé·æå¾ãå¼ãä¸ãããã¨ã§ãå°æ¥ã®å¢çæå¾ãé«ã¾ãããããã",
    },
    "upgrade": {
        "weight": 3, "strength": "ããå¼·ãå¥½ææ",
        "content": "å¤§æè¨¼å¸ã»ã¢ããªã¹ããç®æ¨æ ªä¾¡ãè©ä¾¡(ã¬ã¼ãã£ã³ã°)ãä¸æ¹ä¿®æ­£",
        "impact": "+1%ã+5%ç¨åº¦",
        "reason": "æåãªç¬¬ä¸èè©ä¾¡ã®æ¹åã¯ãä»ã®æè³å®¶ã®è¦æ¹ã«ãå½±é¿ãä¸ãããããã",
    },
    "buyback": {
        "weight": 2, "strength": "ããå¼·ãå¥½ææ",
        "content": "å¤§è¦æ¨¡ãªèªç¤¾æ ªè²·ããã­ã°ã©ã ãçºè¡¨",
        "impact": "+1%ã+4%ç¨åº¦",
        "reason": "æ ªå¼æ°æ¸å°ã«ããEPSæ¹åæå¾ã¨ãçµå¶é£ã®èªä¿¡è¡¨æã¨ãã¦åãæ­¢ãããããããã",
    },
    "dividend_hike": {
        "weight": 2, "strength": "ããå¼·ãå¥½ææ",
        "content": "å¢éãçºè¡¨",
        "impact": "+1%ã+3%ç¨åº¦",
        "reason": "æ ªä¸»éåå¼·åã®å§¿å¢ãè©ä¾¡ããããããã",
    },
}


def disclosure_sentiment(tag, title):
    """TDnetéç¤º1ä»¶ã®ã¿ã¤ãã«ã»ã¿ã°æå­åãããæ¢å­ã®JP_NEGATIVE_KEYWORDS(å¼±ææ)ã»
    JP_CATALYST_INFO(å¥½ææ)ã®ã­ã¼ã¯ã¼ãä¸è´ã ãã§æ©æ¢°çã«ãã¸ãã£ã/ãã¬ãã£ã/ä¸­ç«ãå¤å®ããã
    AIã«ããæèçè§£ã§ã¯ãªãåç´ãªã­ã¼ã¯ã¼ãä¸è´ã§ãããæè³å©è¨ã§ã¯ãªãã
    æ»ãå¤: (ããã¸ç¨CSSã¯ã©ã¹, è¡¨ç¤ºã©ãã«)"""
    combined = f"{tag or ''} {title or ''}"
    if any(k in combined for k in JP_NEGATIVE_KEYWORDS):
        return ("bear", "ãã¬ãã£ã")
    if any(k in combined for k in JP_CATALYST_INFO):
        return ("bull", "ãã¸ãã£ã")
    return ("neutral", "ä¸­ç«")


def _has_positive_jp_catalyst(tdnet_morning, tdnet_afterclose):
    """å½æ¥ã®TDnetéç¤º(æã»å¼ãå¾ã®ä¸¡æ¹)ã«ãæç¢ºãªå¥½ææã­ã¼ã¯ã¼ããå«ãéç¤ºã
    (å¼±ææãé¤ãã¦)1ä»¶ã§ããããã©ãããå¤å®ããã"""
    items = list(tdnet_morning or []) + list(tdnet_afterclose or [])
    for it in items:
        combined = f"{it.get('tag', '') or ''} {it.get('title', '') or ''}"
        if any(k in combined for k in JP_NEGATIVE_KEYWORDS):
            continue
        if any(k in combined for k in JP_CATALYST_INFO):
            return True
    return False


def _has_negative_jp_news(tdnet_morning, tdnet_afterclose):
    """å½æ¥ã®TDnetéç¤ºã«ãä¸æ¹ä¿®æ­£ã»æ¸éãªã©æç¢ºãªå¼±ææã­ã¼ã¯ã¼ããå«ãéç¤ºã
    1ä»¶ã§ããããã©ãããå¤å®ããã"""
    items = list(tdnet_morning or []) + list(tdnet_afterclose or [])
    for it in items:
        combined = f"{it.get('tag', '') or ''} {it.get('title', '') or ''}"
        if any(k in combined for k in JP_NEGATIVE_KEYWORDS):
            return True
    return False


def _has_positive_us_catalyst(us_good_news):
    """åéæ¸ã¿ã®ç±³å½æ ªå¥½ææãã¥ã¼ã¹ã«ãæ¢ç¥ã®å¥½ææã«ãã´ãªã1ä»¶ã§ãããããå¤å®ããã"""
    for it in us_good_news or []:
        if (it.get("category") or "") in US_CATALYST_INFO:
            return True
    return False


def market_mood_signal(data):
    """ãã¤ãã¬ã¼ãåå¿èåãã®ç´æçãªãä¿¡å·æ©ãå¤å®ã
    ç±³å½3ææ°ã®å¹³ååæ¥æ¯ã»å½åTDnetéç¤ºã®å¥½ææ/å¼±ææã®æç¡ã»ãã¯ãã«ã«ææ¨ã®éç±æ(RSI>=70)ã®
    3ã¤ã ããçµã¿åããããããã¾ã§æ©æ¢°çãªç°¡æå¤å®ã§ãããAIã«ããé«åº¦ãªåæãæè³å©è¨ã§ã¯ãªãã
    å®éã®ç¸å ´ã¯åå¥è¦å ãè¤éã«çµ¡ããããæçµå¤æ­ã¯å¿ãèªèº«ã®è²¬ä»»ã§è¡ããã¨ã
    æ»ãå¤: {"level": "green"|"yellow"|"red", "icon": str, "label": str, "desc": str, "reasons": [str, ...]}"""
    us = data.get("us_market", {}) or {}
    changes = []
    for key in ("sp500", "dow", "nasdaq"):
        v = (us.get(key) or {}).get("change_pct")
        if isinstance(v, (int, float)):
            changes.append(v)
    us_avg = sum(changes) / len(changes) if changes else None

    technical = data.get("technical", []) or []
    rsi_values = []
    for t in technical:
        try:
            rsi_values.append(float(t.get("rsi")))
        except (TypeError, ValueError):
            continue
    overheat_flag = bool(rsi_values) and (sum(1 for r in rsi_values if r >= 70) / len(rsi_values)) >= 0.5

    has_good = _has_positive_jp_catalyst(data.get("tdnet_morning", []), data.get("tdnet_afterclose", [])) \
        or _has_positive_us_catalyst(data.get("us_good_news", []))
    has_bad_jp = _has_negative_jp_news(data.get("tdnet_morning", []), data.get("tdnet_afterclose", []))

    reasons = []
    if us_avg is not None:
        reasons.append(f"ç±³å½3ææ°å¹³å {fmt_pct(us_avg)}")
    if has_good:
        reasons.append("å¥½ææãã¥ã¼ã¹ã»éç¤ºãã")
    if has_bad_jp:
        reasons.append("å½åã«å¼±ææ(ä¸æ¹ä¿®æ­£ç­)ã®éç¤ºãã")
    if overheat_flag:
        reasons.append("RSIéç±(70ä»¥ä¸)ã®éæãå¤ã")

    if (us_avg is not None and us_avg <= -0.5) or (has_bad_jp and (us_avg is None or us_avg < 0)):
        level = "red"
        icon, label = "ð´", "è¦éããç¡é£ãªå°åã"
        desc = "ç±³å½æ ªå®ãã¾ãã¯å½åã«å¼±ææã®éç¤ºãããã¾ããæ°è¦ã®è²·ãã¯æéã«æ¤è¨ãã¾ãããã"
    elif has_good and overheat_flag:
        level = "yellow"
        icon, label = "ð¡", "ææã¯ãããéç±æã«æ³¨æ"
        desc = "å¥½ææã¯ããã¾ãããå¤ä¸ãããå¤§ããç­æçãªéç±æ(RSIé«ã)ãããã¾ããç¦ã£ã¦è¿½ããããæ§å­ãè¦ãã®ãä¸æ¡ã§ãã"
    elif us_avg is not None and us_avg >= 0.3 and has_good and not overheat_flag:
        level = "green"
        icon, label = "ð¢", "è²·ããæ¤è¨ããããå°åã"
        desc = "ç±³å½æ ªé«ã»æç¢ºãªå¥½ææããããéç±æãç®ç«ã¡ã¾ãããæ¯è¼çä»è¾¼ã¿ãããå°åãã¨è¨ãã¾ãã"
    else:
        level = "yellow"
        icon, label = "ð¡", "æ§å­è¦ãç¡é£ãªå°åã"
        desc = "ç±³å½æ ªãå¥½ææã®æ¹åæãä¹ãããç¡çã«åãå¿è¦ã¯ããã¾ããã"

    return {"level": level, "icon": icon, "label": label, "desc": desc, "reasons": reasons}


def market_mood_html(data):
    mood = market_mood_signal(data)
    reasons_html = "".join(f'<span class="tag">{esc(r)}</span>' for r in mood["reasons"])
    return f"""
    <div class="mood-card mood-{mood['level']}">
      <div class="mood-icon" aria-hidden="true">{mood['icon']}</div>
      <div class="mood-body">
        <div class="mood-label">{esc(mood['label'])}</div>
        <div class="mood-desc">{esc(mood['desc'])}</div>
        <div class="mood-reasons">{reasons_html}</div>
        <div class="mood-caveat">â ï¸ ç±³å½æ ªã®æ¹åã»å¥½ææã®æç¡ã»éç±æã ããçµã¿åãããæ©æ¢°çãªç°¡æå¤å®ã§ããæè³å©è¨ã§ã¯ãªããæçµå¤æ­ã¯å¿ããèªèº«ã®è²¬ä»»ã§è¡ã£ã¦ãã ããã</div>
      </div>
    </div>"""


def theme_summary_html(data, empty_msg="ç¾æç¹ã§æè³é¢é£åéã»æ³¨ç®ä¼æ¥­ã®ãã¼ã¿ãããã¾ããã"):
    """æéå¤ã»å¼ãå¾ã®åãã¥ã¼ã¹ã«ä»ä¸ãããæè³é¢é£åé(investment_sector)ã¨
    æ³¨ç®ä¼æ¥­(investment_companies)ãéç´ãããæ¬æ¥ã®æ³¨ç®ãã¼ããã¨ãã¦ä¸è¦§åããã
    ãã¥ã¼ã¹è¦åºãããæ©æ¢°çã«æ½åºããåèæå ±ã§ãããæè³å©è¨ã§ã¯ãªãã"""
    all_news = list(data.get("overnight_news", []) or []) + list(data.get("afterclose_news", []) or [])
    themes = {}
    order = []
    for it in all_news:
        sector = (it.get("investment_sector") or "").strip()
        if not sector:
            continue
        companies_raw = it.get("investment_companies") or []
        if isinstance(companies_raw, str):
            companies_raw = [c.strip() for c in re.split(r"[ã,]", companies_raw) if c.strip()]
        entry = themes.setdefault(sector, {"count": 0, "companies": [], "news": []})
        if sector not in order:
            order.append(sector)
        entry["count"] += 1
        for c in companies_raw:
            c = str(c).strip()
            if c and c not in entry["companies"]:
                entry["companies"].append(c)
        entry["news"].append(it)

    if not themes:
        return f'<p class="empty">{esc(empty_msg)}</p>'

    ranked = sorted(order, key=lambda s: -themes[s]["count"])
    cards = []
    for sector in ranked[:6]:
        entry = themes[sector]
        if entry["companies"]:
            companies_html = "".join(f'<span class="theme-company">{esc(c)}</span>' for c in entry["companies"][:6])
        else:
            companies_html = '<span class="theme-company muted">åå¥éæã¯ç¹å®ããã¦ãã¾ãã</span>'
        news_titles = "ã".join(esc(it.get("title", "")) for it in entry["news"][:2])
        cards.append(f"""
        <div class="theme-card">
          <div class="theme-head"><span class="theme-name">{esc(sector)}</span><span class="tag">é¢é£ãã¥ã¼ã¹{entry['count']}ä»¶</span></div>
          <div class="theme-companies">{companies_html}</div>
          <div class="theme-source">ãã£ãã: {news_titles}</div>
        </div>""")
    return f'<div class="theme-grid">{"".join(cards)}</div>'


def economic_calendar_html(items, empty_msg="çµæ¸ã«ã¬ã³ãã¼ã®ãã¼ã¿ã¯ä»ååå¾ã§ãã¾ããã§ããã"):
    """éç¨çµ±è¨ã»CPIã»æ¥éä¼åãªã©ãç¸å ´å¤åãèµ·ããããã¤ãã³ããéè¦åº¦(â1ã5)ä»ãã§ä¸è¦§åããã
    éè¦åº¦ã¯ã¤ãã³ãã®ä¸è¬çãªå¸å ´ã¤ã³ãã¯ãã®å¤§ãããç¤ºãåèå¤ã§ãããå®éã®å¤åãä¿è¨¼ããªãã"""
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        date_ = esc(it.get("date", ""))
        event = esc(it.get("event", ""))
        try:
            imp = max(1, min(5, int(it.get("importance", 1))))
        except (TypeError, ValueError):
            imp = 1
        stars = "â" * imp + "â" * (5 - imp)
        note = esc(it.get("note", ""))
        note_html = f'<div class="note">{note}</div>' if note else ""
        rows.append(f"""
        <div class="calendar-item">
          <div class="calendar-date mono">{date_}</div>
          <div class="calendar-body">
            <div class="calendar-event">{event}</div>
            <div class="calendar-stars" aria-label="éè¦åº¦{imp}/5" title="éè¦åº¦{imp}/5">{stars}</div>
            {note_html}
          </div>
        </div>""")
    return f'<div class="calendar-list">{"".join(rows)}</div>'


def _catalyst_rank_row(i, code, name, strength_label, content_text, impact_text, reason_text,
                        news_title, news_url, extra_note, outlook_html):
    """å¥½ææã©ã³ã­ã³ã°1ä»¶åã®è¡HTMLãå·ä½çãªå¥½ææåå®¹ã»æ³å®ã¤ã³ãã¯ã(åèå¤)ã»
    å¥½ææã¨å¤æ­ããçç±ãããããæè¨ããã"""
    return f"""
        <div class="rank-item">
          <div class="rank-num">{rank_label(i)}</div>
          <div class="rank-body">
            <div class="rank-head">
              <span class="mono">{esc(code)}</span> {esc(name)}
              <span class="score-tag">{esc(strength_label)}</span>
            </div>
            <div class="rank-desc rank-content">ð å·ä½çãªå¥½ææ: {esc(content_text)}</div>
            <div class="rank-desc rank-impact">ð æ³å®ã¤ã³ãã¯ã: {esc(impact_text)}<span class="tag">éå»ã®é¡ä¼¼ã±ã¼ã¹ã®ä¸è¬çå¾åã»åèå¤(ä¿è¨¼ãªã)</span></div>
            <div class="rank-desc rank-reason">ð¡ ãªãå¥½ææã: {esc(reason_text)}</div>
            <div class="rank-desc rank-news">
              <a href="{esc(news_url) or '#'}" target="_blank" rel="noopener">{esc(news_title)}</a>{esc(extra_note)}
            </div>
            <div class="rank-desc rank-outlook">ð {outlook_html}</div>
          </div>
        </div>"""


def good_news_ranking_html_jp(tdnet_morning, tdnet_afterclose, technical,
                               empty_msg="æ¬æ¥ã¯TDnetéç¤ºã«åºã¥ãæç¢ºãªå¥½ææãã¼ã¿(æ¥æ¬æ ª)ãããã¾ããã"):
    """æ¬æ¥ã®TDnetéç¤ºã®ãã¡ãä¸æ¹ä¿®æ­£ã»å¢éã»æé«çãªã©ãæç¢ºãªå¥½ææãã¨ã¿ãªããéç¤ºã®ã¿ãå¯¾è±¡ã«ã
    åå®¹ã®å¼·ã(å¥½ææã®è³ª)ã§ã©ã³ã­ã³ã°åãããã®ãä¸æ¹ä¿®æ­£ã»æ¸éãªã©å¼±ææã¯å¯¾è±¡å¤ã¨ãã
    ä»¶æ°ãè©±é¡æ§(æ³¨ç®åº¦)ã§ã¯ãªãå¥½ææã¨ãã¦ã®è³ªãéè¦ããã
    åé ä½ã«ã¯ãä½ãããã©ããããã®å¥½ææãããæ³å®ã¤ã³ãã¯ã(åèå¤)ãããªãå¥½ææãã
    ãç´è¿ãã¯ãã«ã«ææ¨ã«åºã¥ãåèã³ã¡ã³ãããä½µè¨ãããæ ªä¾¡ä¸æãç¢ºç´ã»äºæ³ãããã®ã§ã¯ãªãã"""
    items = list(tdnet_morning or []) + list(tdnet_afterclose or [])
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'

    scores = {}
    for it in items:
        code = it.get("code", "")
        company = it.get("company", "")
        tag = it.get("tag", "") or ""
        title = it.get("title", "") or ""
        combined = f"{tag} {title}"

        if any(k in combined for k in JP_NEGATIVE_KEYWORDS):
            continue  # å¼±ææã¯å¥½ææã©ã³ã­ã³ã°ã®å¯¾è±¡å¤

        weight = 0
        keyword = None
        for k, info in JP_CATALYST_INFO.items():
            if k in combined and info["weight"] > weight:
                weight = info["weight"]
                keyword = k
        if weight == 0:
            continue  # æç¢ºãªå¥½ææã­ã¼ã¯ã¼ããç¡ããã°å¯¾è±¡å¤(åãªãè©±é¡æ§ã§ã¯å ç¹ããªã)

        key = (code, company)
        entry = scores.setdefault(key, {"score": 0, "count": 0, "items": [], "keyword": None})
        if entry["keyword"] is None or weight > entry["score"]:
            entry["score"] = weight
            entry["keyword"] = keyword
        entry["count"] += 1
        entry["items"].append(it)

    if not scores:
        return f'<p class="empty">{esc(empty_msg)}</p>'

    tech_lookup = _technical_lookup(technical)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1]["score"])
    rows = []
    for i, ((code, company), entry) in enumerate(ranked[:5]):
        latest = entry["items"][-1]
        title = latest.get("title", "")
        url = latest.get("url", "") or "#"
        extra = f" ã»ã{entry['count'] - 1}ä»¶" if entry["count"] > 1 else ""
        outlook = _outlook_comment(code, tech_lookup)
        info = JP_CATALYST_INFO.get(entry["keyword"], {})
        rows.append(_catalyst_rank_row(
            i, code, company, info.get("strength", "å¥½ææ"),
            info.get("content", title), info.get("impact", "ç®å®ä¸å¯"),
            info.get("reason", ""), title, url, extra, outlook,
        ))
    return "".join(rows)


def good_news_ranking_html_us(us_good_news,
                               empty_msg="æ¬æ¥ã¯ç±³å½æ ªã®æç¢ºãªå¥½ææãã¼ã¿ãããã¾ãã(ãã¼ã¿åå¾ã¯ä»å¾ã®æ´æ°ã«å¯¾å¿äºå®ã§ã)ã"):
    """ãã¼ã¿åéã¿ã¹ã¯ãåéããç±³å½æ ªã®å¥½ææãã¥ã¼ã¹(ticker/company/headline/category/url)ã
    å¯¾è±¡ã«ãã«ãã´ãªã®å¼·ãã§ã©ã³ã­ã³ã°åãããã®ãæ¥æ¬æ ªã¨åæ§ã«ãä½ãããã©ããããã®å¥½ææãã
    ãæ³å®ã¤ã³ãã¯ã(åèå¤)ãããªãå¥½ææãããæè¨ãããæ ªä¾¡ä¸æãç¢ºç´ã»äºæ³ãããã®ã§ã¯ãªãã
    ç±³å½æ ªã¯æ¥æ¬ã®TDnetã®ãããªçµ±ä¸çãªé©æéç¤ºã·ã¹ãã ãç¡ãããããã¯ãã«ã«ææ¨ã³ã¡ã³ãã¯å¯¾è±¡å¤ã"""
    items = list(us_good_news or [])
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'

    scores = {}
    for it in items:
        ticker = it.get("ticker", "") or it.get("code", "")
        company = it.get("company", "") or it.get("name", "")
        category = it.get("category", "")
        info = US_CATALYST_INFO.get(category)
        if not info:
            continue  # æªç¥ã®ã«ãã´ãªã»å¥½ææã«è©²å½ããªããã®ã¯å¯¾è±¡å¤

        key = (ticker, company)
        entry = scores.setdefault(key, {"score": 0, "count": 0, "items": [], "category": None})
        if entry["category"] is None or info["weight"] > entry["score"]:
            entry["score"] = info["weight"]
            entry["category"] = category
        entry["count"] += 1
        entry["items"].append(it)

    if not scores:
        return f'<p class="empty">{esc(empty_msg)}</p>'

    ranked = sorted(scores.items(), key=lambda kv: -kv[1]["score"])
    rows = []
    for i, ((ticker, company), entry) in enumerate(ranked[:5]):
        latest = entry["items"][-1]
        headline = latest.get("headline", "") or latest.get("title", "")
        url = latest.get("url", "") or "#"
        extra = f" ã»ã{entry['count'] - 1}ä»¶" if entry["count"] > 1 else ""
        info = US_CATALYST_INFO.get(entry["category"], {})
        content_text = headline or info.get("content", "")
        rows.append(_catalyst_rank_row(
            i, ticker, company, info.get("strength", "å¥½ææ"),
            content_text, info.get("impact", "ç®å®ä¸å¯"),
            info.get("reason", ""), headline, url, extra,
            "ç±³å½æ ªã®ãããã¯ãã«ã«ææ¨(ç§»åå¹³åã»RSIç­)ã¯å¯¾è±¡å¤ã§ããåå¥ã®æ ªä¾¡æå ±ã¯åç¨®æ ªä¾¡æå ±ãµã¼ãã¹ã§ãç¢ºèªãã ããã",
        ))
    return "".join(rows)


def growth_candidates_html(items, empty_msg="ç¾æç¹ã§å¥½ææéç¤ºã«åºã¥ãæé·æ ªåè£ã¯è¦ã¤ããã¾ããã§ããã"):
    """TDnetãæ¥­ç¸¾äºæ³ã®ä¿®æ­£ãéç¤ºã®ãã¡ãä¸æ¹ä¿®æ­£ã»å¢éãªã©æç¢ºãªå¥½ææã­ã¼ã¯ã¼ããå«ãéç¤ºã®ã¿ã
    æ©æ¢°çã«æ½åºãããæé·æ ªåè£ãä¸è¦§ãååè£ã«ã¯å®éã®éç¤ºPDFã¸ã®ç´ãªã³ã¯ãä»ãã
    æ ¹æ (æ±ºç®ã»å¥½ææ)ãéç¤ºåæã§ç¢ºèªã§ãããå°æ¥ã®æ ªä¾¡ä¸æãä¿è¨¼ãããã®ã§ã¯ãªãã"""
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        company = esc(it.get("company", ""))
        title = esc(it.get("title", ""))
        url = esc(it.get("url", "")) or "#"
        catalyst = esc(it.get("catalyst", ""))
        reason = esc(it.get("reason", ""))
        asof = esc(it.get("asof", ""))
        rows.append(f"""
        <div class="rank-item">
          <div class="rank-num">ð±</div>
          <div class="rank-body">
            <div class="rank-head">
              {company}
              <span class="badge bull">{catalyst}</span>
            </div>
            <div class="rank-desc rank-news">
              <a href="{url}" target="_blank" rel="noopener">{title}</a>
            </div>
            <div class="rank-desc">{reason} ã» éç¤ºæ¥æ: {asof}</div>
          </div>
        </div>""")
    return "".join(rows)


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
  font-family: 'Inter', "Noto Sans JP", -apple-system, "Hiragino Sans", "Yu Gothic", "Segoe UI", sans-serif;
  color: var(--text); line-height: 1.68; letter-spacing: 0.15px;
  font-feature-settings: "palt" 1; font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
  background-color: var(--bg-deep);
}

/* --- èæ¯åç: ç»è³ªãè½ã¨ããopacityã®ã¿ã§ãã£ããã¯ã­ã¹ãã§ã¼ãããã¹ã©ã¤ãã·ã§ã¼ --- */
.bg-photo-stack { position: fixed; inset: 0; z-index: -2; overflow: hidden; background: var(--bg-deep); }
.bg-photo {
  position: absolute; inset: 0;
  background-size: cover; background-position: center; background-repeat: no-repeat;
  opacity: 0; transition: opacity 4s ease-in-out;
  will-change: opacity;
}
.bg-photo.is-active { opacity: 1; }
.bg-spacer { position: relative; height: 90vh; min-height: 650px; }
.bg-caption {
  position: absolute; left: 20px; bottom: 16px;
  font-size: 11px; color: var(--text); background: rgba(0,0,0,0.4);
  padding: 5px 12px; border-radius: 10px; border: 1px solid var(--border-soft);
  backdrop-filter: blur(2px); letter-spacing: 0.02em;
}
:root[data-theme="light"] .bg-caption { background: rgba(255,255,255,0.55); color: var(--text); }
.bg-overlay {
  position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background-repeat: no-repeat;
  background-image:
    radial-gradient(circle at 12% 4%, rgba(212,175,55,0.14), transparent 38%),
    radial-gradient(circle at 90% 2%, rgba(212,175,55,0.07), transparent 42%),
    radial-gradient(circle at 30% 94%, rgba(212,175,55,0.06), transparent 45%),
    radial-gradient(circle at 80% 72%, rgba(212,175,55,0.04), transparent 40%),
    linear-gradient(180deg, rgba(0,0,0,0.42) 0%, rgba(4,3,2,0.5) 45%, rgba(6,5,4,0.6) 100%);
}
body::-webkit-scrollbar { width: 10px; }
body::-webkit-scrollbar-track { background: #000; }
body::-webkit-scrollbar-thumb { background: linear-gradient(180deg, var(--accent), var(--accent-deep)); border-radius: 6px; }
.wrap { max-width: 1080px; margin: 0 auto; padding: 24px 20px 60px; }

/* --- åºå®è¦åºããã¼: å¸¸ã«ç»é¢ä¸é¨ã«è¡¨ç¤ºããã --- */
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
.eyebrow::before { content: "â "; color: var(--accent); }
h1 {
  font-family: "Playfair Display", "Shippori Mincho", "Hiragino Mincho ProN", serif;
  font-size: 19px; margin: 0 0 4px; font-weight: 700; letter-spacing: 0.6px;
  color: var(--accent);
  background: linear-gradient(120deg, var(--accent-bright) 0%, var(--accent) 45%, var(--accent-deep) 100%);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}
.subtitle { color: var(--muted); font-size: 11.5px; letter-spacing: 0.3px; }
.disclaimer {
  background: linear-gradient(155deg, rgba(24,19,8,0.94), rgba(10,8,4,0.96));
  border: 1px solid var(--accent-line); color: #e9d29c;
  border-radius: var(--radius-sm); padding: 14px 16px; font-size: 13px; line-height: 1.7; margin: 16px 20px;
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
.disclaimer b { color: var(--accent-bright); }
nav.tabs {
  display: flex; gap: 10px; flex-wrap: wrap;
}
nav.tabs a {
  color: var(--accent-bright); text-decoration: none; font-size: 12px; letter-spacing: 0.8px;
  text-transform: uppercase; font-weight: 500;
  border: 1px solid var(--border);
  padding: 7px 16px; border-radius: 20px; background: rgba(212,175,55,0.05); white-space: nowrap;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
  transition: border-color .15s ease, box-shadow .15s ease, color .15s ease, background .15s ease;
}
nav.tabs a:hover {
  color: #0a0805; border-color: var(--accent);
  background: linear-gradient(120deg, var(--accent-bright), var(--accent));
  box-shadow: 0 0 20px rgba(212,175,55,0.35);
}
section { margin: 32px 20px; }
section > h2 {
  font-family: "Playfair Display", "Shippori Mincho", "Hiragino Mincho ProN", serif;
  font-size: 18px; border-left: 2px solid var(--accent); padding: 5px 12px; margin-bottom: 4px;
  font-weight: 600; letter-spacing: 0.5px; color: var(--accent-bright);
  background: rgba(10,8,5,0.55); border-radius: 0 8px 8px 0; width: fit-content;
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
.section-desc {
  color: var(--muted); font-size: 12.5px; line-height: 1.6; margin: 6px 0 14px; padding: 5px 10px;
  background: rgba(10,8,5,0.48); border-radius: 8px; width: fit-content;
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
.card {
  background: var(--panel); border: 1px solid var(--border); border-top: 1px solid var(--accent-line);
  border-radius: var(--radius);
  padding: 18px 20px; margin-bottom: 16px; box-shadow: var(--shadow);
  transition: border-color .2s ease, box-shadow .2s ease;
}
.card:hover { border-color: var(--accent-line); box-shadow: var(--shadow), 0 0 24px rgba(212,175,55,0.08); }
.card h3 {
  font-size: 12px; margin: 0 0 12px; color: var(--accent); font-weight: 600;
  letter-spacing: 1.4px; text-transform: uppercase;
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
  padding: 10px 12px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
  transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
}
.idx-card:hover {
  border-color: var(--accent-line); box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 0 18px rgba(212,175,55,0.16);
  transform: translateY(-1px);
}
.idx-label { font-size: 11.5px; color: var(--muted); letter-spacing: 0.4px; text-transform: uppercase; }
.idx-value { font-size: 18px; font-weight: 700; margin-top: 3px; letter-spacing: 0.3px; color: var(--accent-bright); }
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
.news-impact { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 5px; }
.news-impact .impact-sector, .news-impact .impact-companies {
  display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 10px;
  border: 1px solid var(--border-soft); color: var(--accent-bright); background: rgba(212,175,55,0.08);
  line-height: 1.5;
}
.news-impact .impact-companies { color: var(--text); background: rgba(255,255,255,0.04); }
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
.badge { padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; letter-spacing: 0.3px; }
.badge.bull { background: linear-gradient(120deg, rgba(255,107,122,0.2), rgba(255,107,122,0.08)); color: var(--bull); border: 1px solid rgba(255,107,122,0.3); }
.badge.bear { background: linear-gradient(120deg, rgba(53,217,180,0.2), rgba(53,217,180,0.08)); color: var(--bear); border: 1px solid rgba(53,217,180,0.3); }
.badge.neutral { background: rgba(212,175,55,0.1); color: var(--muted); border: 1px solid var(--border-soft); }
.tag { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: var(--border-soft); color: var(--muted); margin-left: 4px; }
.tag-warn { background: rgba(255,184,77,0.18); color: var(--warn); }
.empty { color: var(--muted); font-size: 13px; }
.sentiment-badge { margin-right: 6px; vertical-align: middle; cursor: help; }

/* --- å¸å ´ã ã¼ãä¿¡å·æ© --- */
.mood-card {
  display: flex; gap: 16px; align-items: flex-start; padding: 16px 18px; margin-bottom: 16px;
  border-radius: var(--radius); border: 1px solid var(--border); background: var(--panel);
  box-shadow: var(--shadow);
}
.mood-icon { font-size: 40px; line-height: 1; flex-shrink: 0; filter: drop-shadow(0 0 8px rgba(0,0,0,0.35)); }
.mood-label { font-size: 16px; font-weight: 700; color: var(--text); letter-spacing: 0.3px; }
.mood-desc { font-size: 12.5px; color: var(--muted); margin-top: 4px; line-height: 1.6; }
.mood-reasons { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.mood-reasons .tag { margin-left: 0; }
.mood-caveat { font-size: 10.5px; color: var(--muted); opacity: 0.85; margin-top: 8px; line-height: 1.6; }
.mood-card.mood-green { border-color: rgba(63,196,116,0.45); box-shadow: var(--shadow), 0 0 24px rgba(63,196,116,0.14); }
.mood-card.mood-yellow { border-color: rgba(255,184,77,0.45); box-shadow: var(--shadow), 0 0 24px rgba(255,184,77,0.14); }
.mood-card.mood-red { border-color: rgba(255,90,90,0.45); box-shadow: var(--shadow), 0 0 24px rgba(255,90,90,0.14); }

/* --- çµæ¸ã«ã¬ã³ãã¼ --- */
.calendar-list { display: flex; flex-direction: column; gap: 2px; }
.calendar-item { display: flex; gap: 12px; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid var(--border-soft); }
.calendar-item:last-child { border-bottom: none; }
.calendar-date { width: 76px; flex-shrink: 0; font-size: 12px; color: var(--muted); padding-top: 1px; }
.calendar-body { flex: 1; min-width: 0; }
.calendar-event { font-size: 13.5px; color: var(--text); font-weight: 600; }
.calendar-stars { font-size: 13px; color: var(--accent-bright); letter-spacing: 1px; margin-top: 2px; }

/* --- æ¬æ¥ã®æ³¨ç®ãã¼ã --- */
.theme-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.theme-card {
  background: var(--panel2); border: 1px solid var(--border-soft); border-radius: var(--radius-sm);
  padding: 10px 12px;
}
.theme-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 13.5px; font-weight: 600; color: var(--text); flex-wrap: wrap; }
.theme-name { color: var(--accent-bright); }
.theme-companies { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.theme-company {
  font-size: 11px; padding: 2px 8px; border-radius: 10px; border: 1px solid var(--border-soft);
  background: rgba(255,255,255,0.04); color: var(--text);
}
.theme-company.muted { color: var(--muted); }
.theme-source { font-size: 11px; color: var(--muted); margin-top: 6px; }

/* --- ã©ã³ã­ã³ã°(å¼·æ°ã·ã°ãã«æ° / TDnetå¥½ææ) --- */
.rank-item { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; border-bottom: 1px solid var(--border-soft); }
.rank-item:last-child { border-bottom: none; }
.rank-num { width: 34px; flex-shrink: 0; font-size: 19px; text-align: center; line-height: 1.4; }
.rank-body { flex: 1; min-width: 0; }
.rank-head { font-size: 13.5px; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rank-desc { font-size: 12px; color: var(--muted); margin-top: 4px; }
.rank-news a { color: var(--accent-bright); }
.rank-outlook { font-style: italic; opacity: 0.9; }
.rank-content { color: var(--text); opacity: 0.92; }
.rank-impact { color: var(--accent-bright); }
.rank-impact .tag { margin-left: 6px; }
.rank-reason { opacity: 0.9; }
.rank-note { font-size: 11px; color: var(--muted); margin: 0 0 10px; }
.score-tag {
  font-size: 10.5px; padding: 2px 8px; border-radius: 10px;
  background: rgba(212,175,55,0.12); color: var(--accent-bright); border: 1px solid var(--border);
  white-space: nowrap;
}

footer {
  margin: 40px 20px 10px; color: var(--muted); font-size: 11.5px; line-height: 1.7;
  border-top: 1px solid var(--accent-line);
  background: rgba(10,8,5,0.5); border-radius: var(--radius-sm);
  padding: 16px 18px; border: 1px solid var(--border);
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
footer .disclaimer { margin: 0 0 12px; }
.sources { font-size: 11px; color: var(--muted); }
.run-badge {
  display:inline-block; font-size:11px; padding:2px 10px; border-radius:10px;
  background: rgba(0,0,0,0.4); border:1px solid var(--accent-line); color: var(--accent-bright); margin-left:8px;
  letter-spacing: 0.3px;
}

/* --- PC(åºãç»é¢): ä½ç½ã¨æå¤§å¹ãå°ãåºãã¦èª­ã¿ããããã --- */
@media (min-width: 1200px) {
  .wrap { max-width: 1240px; }
  body { font-size: 15.5px; }
  .idx-grid { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
  .topbar-inner { max-width: 1240px; }
}

/* --- ã¹ãã(ç­ãç»é¢): ä½ç½ã»æå­ãµã¤ãºãè©°ãã¦ã¿ãããããããã --- */
@media (max-width: 640px) {
  .wrap { padding: 12px 12px 48px; }
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
  .rank-num { width: 26px; font-size: 15px; }
  .rank-head { font-size: 12.5px; }
}

/* ==================== è¿½å æ©è½: ã©ã¤ããã¼ã / ãæ°ã«å¥ã / æ¤ç´¢ã»ã½ã¼ã / ããã°ã©ã / ã¢ãã¡ã¼ã·ã§ã³ ==================== */

:root[data-theme="light"] {
  --bg-deep: #f6f0e3; --bg-mid: #f6f0e3; --bg-soft: #f6f0e3;
  --panel: linear-gradient(155deg, rgba(255,255,255,0.92), rgba(250,244,230,0.95));
  --panel2: rgba(90,60,10,0.05);
  --border: rgba(150,108,20,0.35); --border-soft: rgba(60,40,10,0.12);
  --text: #241c0f; --muted: #6d6252;
  --accent: #9c7a22; --accent-bright: #7c5e14; --accent-deep: #5c440e;
  --accent-soft: rgba(156,122,34,0.14); --accent-line: rgba(156,122,34,0.55);
  --up: #c23b4a; --down: #0f8f72;
  --warn: #a5690a; --bull: #c23b4a; --bear: #0f8f72;
  --shadow: 0 10px 26px rgba(90,70,20,0.14);
}
:root[data-theme="light"] .bg-overlay {
  background-image:
    radial-gradient(circle at 12% 4%, rgba(156,122,34,0.10), transparent 38%),
    radial-gradient(circle at 90% 2%, rgba(156,122,34,0.06), transparent 42%),
    radial-gradient(circle at 30% 94%, rgba(156,122,34,0.05), transparent 45%),
    radial-gradient(circle at 80% 72%, rgba(156,122,34,0.03), transparent 40%),
    linear-gradient(180deg, rgba(255,251,242,0.72) 0%, rgba(250,244,230,0.78) 45%, rgba(246,240,227,0.86) 100%);
}
:root[data-theme="light"] body::-webkit-scrollbar-track { background: #efe6d0; }

.top-controls { display: flex; align-items: center; gap: 10px; }
.theme-toggle {
  border: 1px solid var(--border); background: rgba(212,175,55,0.08); color: var(--accent-bright);
  border-radius: 20px; width: 34px; height: 34px; font-size: 15px; cursor: pointer; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center; font-family: inherit;
  transition: border-color .15s ease, background .15s ease, transform .25s ease;
}
.theme-toggle:hover { border-color: var(--accent); background: rgba(212,175,55,0.18); transform: rotate(14deg); }

.rel-time { color: var(--muted); font-size: 11px; margin-left: 2px; }

.fav-filter {
  display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted);
  margin: 10px 20px 0; cursor: pointer; user-select: none;
}
.fav-filter input { accent-color: var(--accent); cursor: pointer; }

.fav-btn {
  background: none; border: none; cursor: pointer; color: var(--border-soft); font-size: 13px;
  padding: 0 3px 0 0; vertical-align: middle; line-height: 1; transition: color .15s ease, transform .15s ease;
}
.fav-btn:hover { color: var(--accent); transform: scale(1.2); }
.fav-btn.active { color: var(--accent-bright); }

tr.fav-hidden, tr.search-hidden { display: none; }

.table-tools { margin: 0 0 8px; }
.table-search {
  width: 100%; max-width: 280px; background: rgba(255,255,255,0.04); color: var(--text);
  border: 1px solid var(--border-soft); border-radius: 16px; padding: 6px 12px; font-size: 12.5px;
  font-family: inherit; outline: none; transition: border-color .15s ease, background .15s ease;
}
.table-search::placeholder { color: var(--muted); }
.table-search:focus { border-color: var(--accent-line); background: rgba(212,175,55,0.06); }

table[data-sortable] thead th { position: relative; user-select: none; cursor: pointer; }
table[data-sortable] thead th:hover { color: var(--accent-bright); }
table[data-sortable] thead th::after { content: "â"; margin-left: 5px; font-size: 9px; opacity: 0.35; }
table[data-sortable] thead th[data-dir="asc"]::after { content: "â²"; opacity: 0.9; }
table[data-sortable] thead th[data-dir="desc"]::after { content: "â¼"; opacity: 0.9; }

.mini-bar {
  position: relative; display: inline-block; width: 44px; height: 6px; margin-left: 8px;
  background: var(--border-soft); border-radius: 3px; vertical-align: middle;
}
.mini-bar::before {
  content: ""; position: absolute; left: 50%; top: -2px; bottom: -2px; width: 1px; background: var(--border-soft);
}
.mini-bar-fill { position: absolute; top: 0; bottom: 0; border-radius: 3px; }
.mini-bar-fill.up { background: var(--up); }
.mini-bar-fill.down { background: var(--down); }

.rsi-gauge { display: inline-flex; align-items: center; gap: 6px; }
.rsi-gauge-track {
  position: relative; width: 54px; height: 6px; border-radius: 3px; flex-shrink: 0;
  background: linear-gradient(90deg, var(--down) 0%, var(--down) 28%, var(--border-soft) 30%, var(--border-soft) 68%, var(--up) 70%, var(--up) 100%);
}
.rsi-gauge-marker {
  position: absolute; top: -3px; width: 2px; height: 12px; background: var(--text);
  border-radius: 1px; transform: translateX(-1px);
}
.rsi-gauge-marker.warn-hot { background: var(--warn); box-shadow: 0 0 6px rgba(255,184,77,0.7); }
.rsi-gauge-marker.warn-cold { background: var(--down); box-shadow: 0 0 6px rgba(53,217,180,0.5); }
.rsi-gauge-num { font-size: 11.5px; color: var(--muted); }

.reveal { opacity: 0; transform: translateY(14px); transition: opacity .6s ease, transform .6s ease; }
.reveal.in-view { opacity: 1; transform: translateY(0); }

#backToTop {
  position: fixed; right: 18px; bottom: 18px; z-index: 30; width: 42px; height: 42px; border-radius: 50%;
  border: 1px solid var(--accent-line); background: linear-gradient(155deg, rgba(20,17,10,0.92), rgba(8,7,5,0.96));
  color: var(--accent-bright); font-size: 16px; cursor: pointer; box-shadow: var(--shadow);
  opacity: 0; transform: translateY(10px); pointer-events: none; transition: opacity .25s ease, transform .25s ease;
}
#backToTop.show { opacity: 1; transform: translateY(0); pointer-events: auto; }
#backToTop:hover { border-color: var(--accent); }

@media (prefers-reduced-motion: reduce) {
  .reveal { opacity: 1; transform: none; transition: none; }
  .bg-photo { transition: none; }
  #backToTop { transition: opacity .01s linear; }
}

@media (max-width: 640px) {
  .table-search { max-width: 100%; }
  .fav-filter { margin: 8px 8px 0; }
  #backToTop { right: 12px; bottom: 12px; width: 38px; height: 38px; }
  .top-controls { width: 100%; justify-content: space-between; }
}

@media print {
  .topbar, .theme-toggle, .fav-filter, .table-tools, #backToTop, .fav-btn, .bg-photo-stack, .bg-overlay, .bg-spacer { display: none !important; }
  body { background: #fff !important; color: #000 !important; }
  .card, .disclaimer, footer, section > h2, .section-desc {
    background: #fff !important; color: #000 !important; border-color: #999 !important; box-shadow: none !important;
    backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
  }
  a { color: #000 !important; text-decoration: underline; }
}
    /* ââ æè³æ¦ç¥ãµããªã¼ ââ */
    #strategy { margin-top: 1em; }
    .strategy-block { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1em 1.2em; margin-bottom: 1em; }
    .strategy-block h4 { margin: 0 0 0.5em; font-size: 1em; }
    .strategy-market { font-size: 1.4em; font-weight: 700; margin: 0.3em 0 0.6em; }
    .strategy-note { font-size: 0.82em; color: var(--muted); margin: 0 0 0.6em; line-height: 1.5; }
    .strategy-list { margin: 0; padding-left: 1.4em; line-height: 1.8; font-size: 0.9em; }
    .strategy-list li { margin-bottom: 0.3em; }
    .strategy-conclusion { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 8%, var(--card)); }
    .strategy-conclusion h4 { color: var(--accent); }
    .strategy-conclusion-list { margin: 0; padding-left: 1.4em; line-height: 1.9; font-size: 0.92em; }
    .strategy-conclusion-list li { margin-bottom: 0.5em; }
"""


JS_SCRIPT = r"""
<script>
(function () {
  "use strict";

  var reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  /* ---------- èæ¯ã¹ã©ã¤ãã·ã§ã¼(ç»è³ªãè½ã¨ããopacityã®ã¿ã§ãã£ããã¯ã­ã¹ãã§ã¼ã) ---------- */
  (function () {
    var photos = document.querySelectorAll(".bg-photo-stack .bg-photo");
    var captionEl = document.getElementById("bgCaption");
    function updateCaption(photo) {
      if (!captionEl || !photo) { return; }
      var cap = photo.getAttribute("data-caption") || "";
      captionEl.textContent = "ð æ±äº¬ã»" + (cap || "æ±äº¬");
    }
    if (photos.length < 2 || reduceMotion) { return; }
    var idx = 0;
    setInterval(function () {
      photos[idx].classList.remove("is-active");
      idx = (idx + 1) % photos.length;
      photos[idx].classList.add("is-active");
      updateCaption(photos[idx]);
    }, 17000);
  })();

  /* ---------- ãã¼ãåæ¿(ã©ã¤ã/ãã¼ã¯) ---------- */
  var THEME_KEY = "jpdt_theme";
  var themeToggle = document.getElementById("themeToggle");
  function applyTheme(mode) {
    if (mode === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
      var next = cur === "light" ? "dark" : "light";
      applyTheme(next);
      try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    });
  }

  /* ---------- ãæ°ã«å¥ã(â) ---------- */
  var FAV_KEY = "jpdt_favorites";
  function loadFavorites() {
    try {
      var raw = localStorage.getItem(FAV_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) { return []; }
  }
  function saveFavorites(list) {
    try { localStorage.setItem(FAV_KEY, JSON.stringify(list)); } catch (e) {}
  }
  var favorites = loadFavorites();
  function isFav(code) { return favorites.indexOf(code) !== -1; }
  function paintFavButtons() {
    var btns = document.querySelectorAll(".fav-btn");
    for (var i = 0; i < btns.length; i++) {
      var btn = btns[i];
      var code = btn.getAttribute("data-code");
      var fav = isFav(code);
      btn.classList.toggle("active", fav);
      btn.setAttribute("aria-pressed", fav ? "true" : "false");
    }
  }
  document.addEventListener("click", function (e) {
    var btn = e.target && e.target.closest ? e.target.closest(".fav-btn") : null;
    if (!btn) { return; }
    var code = btn.getAttribute("data-code");
    if (!code) { return; }
    var idx = favorites.indexOf(code);
    if (idx === -1) { favorites.push(code); } else { favorites.splice(idx, 1); }
    saveFavorites(favorites);
    paintFavButtons();
    applyFavFilter();
  });
  paintFavButtons();

  var favFilter = document.getElementById("favFilterToggle");
  function applyFavFilter() {
    var on = !!(favFilter && favFilter.checked);
    var rows = document.querySelectorAll("table[data-sortable] tbody tr");
    for (var i = 0; i < rows.length; i++) {
      var tr = rows[i];
      if (!on) { tr.classList.remove("fav-hidden"); continue; }
      var star = tr.querySelector(".fav-btn");
      var fav = star && isFav(star.getAttribute("data-code"));
      tr.classList.toggle("fav-hidden", !fav);
    }
  }
  if (favFilter) { favFilter.addEventListener("change", applyFavFilter); }

  /* ---------- ãã¼ãã«æ¤ç´¢ ---------- */
  var searchInputs = document.querySelectorAll(".table-search");
  for (var s = 0; s < searchInputs.length; s++) {
    (function (input) {
      input.addEventListener("input", function () {
        var wrap = input.closest(".table-tools");
        var card = wrap ? wrap.parentElement : null;
        var table = card ? card.querySelector("table") : null;
        if (!table) { return; }
        var q = input.value.trim().toLowerCase();
        var trs = table.querySelectorAll("tbody tr");
        for (var i = 0; i < trs.length; i++) {
          var tr = trs[i];
          var hit = !q || tr.textContent.toLowerCase().indexOf(q) !== -1;
          tr.classList.toggle("search-hidden", !hit);
        }
      });
    })(searchInputs[s]);
  }

  /* ---------- ãã¼ãã«ã½ã¼ã(è¦åºãã¯ãªãã¯) ---------- */
  function parseCell(text) {
    var t = text.replace(/[,å%â]/g, "").trim();
    var n = parseFloat(t);
    return isNaN(n) ? null : n;
  }
  var sortHeads = document.querySelectorAll('table[data-sortable] thead th');
  for (var h = 0; h < sortHeads.length; h++) {
    (function (th) {
      var colIndex = Array.prototype.indexOf.call(th.parentElement.children, th);
      th.addEventListener("click", function () {
        var table = th.closest("table");
        var tbody = table.querySelector("tbody");
        var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
        var dir = th.getAttribute("data-dir") === "asc" ? "desc" : "asc";
        var heads = table.querySelectorAll("thead th");
        for (var i = 0; i < heads.length; i++) { heads[i].removeAttribute("data-dir"); }
        th.setAttribute("data-dir", dir);
        rows.sort(function (a, b) {
          var ca = a.children[colIndex] ? a.children[colIndex].textContent.trim() : "";
          var cb = b.children[colIndex] ? b.children[colIndex].textContent.trim() : "";
          var na = parseCell(ca), nb = parseCell(cb);
          var cmp;
          if (na !== null && nb !== null) { cmp = na - nb; } else { cmp = ca.localeCompare(cb, "ja"); }
          return dir === "asc" ? cmp : -cmp;
        });
        for (var r = 0; r < rows.length; r++) { tbody.appendChild(rows[r]); }
      });
    })(sortHeads[h]);
  }

  /* ---------- ã¹ã¯ã­ã¼ã«æãã§ã¼ãã¤ã³ ---------- */
  var revealTargets = document.querySelectorAll(".card, .idx-card, .rank-item");
  if (!reduceMotion && "IntersectionObserver" in window) {
    for (var rt = 0; rt < revealTargets.length; rt++) { revealTargets[rt].classList.add("reveal"); }
    var io = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i++) {
        var entry = entries[i];
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          io.unobserve(entry.target);
        }
      }
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    for (var rt2 = 0; rt2 < revealTargets.length; rt2++) { io.observe(revealTargets[rt2]); }
  }

  /* ---------- ææ¨ã«ã¼ãã®æ°å¤ã«ã¦ã³ãã¢ãã ---------- */
  if (!reduceMotion) {
    var idxValues = document.querySelectorAll(".idx-value");
    for (var v = 0; v < idxValues.length; v++) {
      (function (el) {
        var raw = el.textContent;
        var m = raw.match(/^-?[\d,]+(\.\d+)?/);
        if (!m) { return; }
        var target = parseFloat(m[0].replace(/,/g, ""));
        if (isNaN(target)) { return; }
        var suffix = raw.slice(m[0].length);
        var decimals = m[1] ? (m[1].length - 1) : 0;
        var t0 = null;
        var duration = 700;
        function step(ts) {
          if (!t0) { t0 = ts; }
          var p = Math.min(1, (ts - t0) / duration);
          var eased = 1 - Math.pow(1 - p, 3);
          var val = target * eased;
          el.textContent = val.toLocaleString("ja-JP", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix;
          if (p < 1) { requestAnimationFrame(step); }
        }
        requestAnimationFrame(step);
      })(idxValues[v]);
    }
  }

  /* ---------- ç¸å¯¾æ´æ°æå» ---------- */
  var relTimes = document.querySelectorAll(".rel-time");
  for (var rtm = 0; rtm < relTimes.length; rtm++) {
    (function (el) {
      var gen = el.getAttribute("data-generated");
      if (!gen) { return; }
      var iso = gen.replace(" ", "T") + ":00+09:00";
      var d = new Date(iso);
      if (isNaN(d.getTime())) { return; }
      var diffMin = Math.round((Date.now() - d.getTime()) / 60000);
      var text;
      if (diffMin < 1) { text = "ãã£ãä»"; }
      else if (diffMin < 60) { text = "ç´" + diffMin + "åå"; }
      else if (diffMin < 60 * 24) { text = "ç´" + Math.round(diffMin / 60) + "æéå"; }
      else { text = "ç´" + Math.round(diffMin / 1440) + "æ¥å"; }
      el.textContent = "(" + text + ")";
    })(relTimes[rtm]);
  }

  /* ---------- ãããã¸æ»ã ---------- */
  var backToTop = document.getElementById("backToTop");
  if (backToTop) {
    window.addEventListener("scroll", function () {
      backToTop.classList.toggle("show", window.scrollY > 480);
    }, { passive: true });
    backToTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
    });
  }
})();
</script>
"""




def strategy_summary_html(data):
    """å°åãã»ãã¯ãã«ã«ç¶æã»å¥½ææéç¤ºã»æè³å¤æ­ã¾ã¨ããçæãã"""
    us = data.get("us_market", {})
    sp500_chg = float((us.get("sp500") or {}).get("change_pct") or 0)
    dow_chg   = float((us.get("dow")   or {}).get("change_pct") or 0)
    nas_chg   = float((us.get("nasdaq") or {}).get("change_pct") or 0)
    us_avg = (sp500_chg + dow_chg + nas_chg) / 3
    futures_chg = float((data.get("nikkei_futures") or {}).get("change_pct") or 0)
    nikkei_chg  = float((data.get("nikkei225") or {}).get("change_pct") or 0)
    fx_chg      = float((data.get("fx") or {}).get("change_pct") or 0)

    if us_avg > 0.5 and futures_chg > -0.3:
        mkt_label, mkt_color, mkt_emoji = "å¼·æ°å°åã", "var(--up)", "ð¢"
    elif us_avg < -0.5 or futures_chg < -0.5 or nikkei_chg < -1.0:
        mkt_label, mkt_color, mkt_emoji = "å¼±æ°å°åã", "var(--down)", "ð´"
    else:
        mkt_label, mkt_color, mkt_emoji = "ä¸­ç«å°åã", "var(--muted)", "ð¡"

    tech_raw = data.get("technical", [])
    technical = list(tech_raw) if isinstance(tech_raw, list) else list(tech_raw.values())
    bull_stocks, bear_stocks, caution_list = [], [], []
    for item in technical:
        counts = parse_signal_counts(item.get("summary", ""))
        if counts:
            score = counts["buy"] * 2 - counts["sell"]
            if score > 0:
                bull_stocks.append((score, item))
            elif score < 0:
                bear_stocks.append((score, item))
        try:
            if float(item.get("rsi", 0) or 0) >= 70:
                caution_list.append(f'{item.get("name","")}ï¼RSIéç±ï¼')
        except (TypeError, ValueError):
            pass
    bull_stocks.sort(key=lambda x: -x[0])
    bear_stocks.sort(key=lambda x: x[0])

    g_raw = data.get("growth_candidates", [])
    growth = list(g_raw) if isinstance(g_raw, list) else list(g_raw.values())

    parts = []

    # å°åã
    parts.append('<div class="strategy-block">')
    parts.append('<h4>ð ä»æ¥ã®å°åã</h4>')
    parts.append(f'<div class="strategy-market" style="color:{mkt_color}">{mkt_emoji} {esc(mkt_label)}</div>')
    parts.append('<ul class="strategy-list">')
    parts.append(f'<li>ç±³å½3ææ°å¹³å: {us_avg:+.2f}%ï¼S&P500 {sp500_chg:+.2f}% / NYãã¦ {dow_chg:+.2f}% / NASDAQ {nas_chg:+.2f}%ï¼</li>')
    if futures_chg:
        parts.append(f'<li>æ¥çµåç©: {futures_chg:+.2f}%</li>')
    if fx_chg:
        yen = "åå®ï¼è¼¸åºæ ªã«è¿½ãé¢¨ï¼" if fx_chg > 0 else "åé«ï¼è¼¸åºæ ªã«éé¢¨ï¼"
        parts.append(f'<li>ãã«å: {yen}ï¼åæ¥æ¯ {fx_chg:+.2f}%ï¼</li>')
    parts.append('</ul></div>')

    # ãã¯ãã«ã«ç¶æè¨ºæ­
    parts.append('<div class="strategy-block">')
    parts.append('<h4>ð ãã¯ãã«ã«ç¶æè¨ºæ­ï¼éå»ãã¼ã¿ã«ããç¾å¨ã®å¼·æ°ã»å¼±æ°ï¼</h4>')
    parts.append('<p class="strategy-note">ç§»åå¹³åç·ã»RSIãªã©<b>éå»ã®æ ªä¾¡ãã¼ã¿</b>ããç®åºãããç¾å¨ã®å¼·æ°ã»å¼±æ°ç¶æãã§ãã<b>å°æ¥ã®æ ªä¾¡ãäºæ¸¬ã»ä¿è¨¼ãããã®ã§ã¯ããã¾ããã</b></p>')
    if bull_stocks:
        parts.append('<p style="margin:0.3em 0 0.2em;font-size:0.88em;color:var(--up)">ð¢ å¼·æ°ï¼è²·ãã·ã°ãã«åªå¢ï¼</p><ul class="strategy-list">')
        for sc, st in bull_stocks:
            rsi = st.get("rsi", "")
            ov = f' â ï¸ RSIéç±({rsi})' if rsi and float(rsi) >= 70 else ""
            chg = st.get("change_pct")
            chg_s = f' / åæ¥æ¯{chg:+.2f}%' if isinstance(chg, (int,float)) else ""
            parts.append(f'<li><b>{esc(st.get("name",""))}</b>ï¼{esc(st.get("code",""))}ï¼â å¼·æ°ã¹ã³ã¢ +{sc}{chg_s}{ov}</li>')
        parts.append('</ul>')
    else:
        parts.append('<p class="empty" style="margin:0.5em 0">ç¾æç¹ã§ãã¯ãã«ã«å¼·æ°ã®éæã¯ããã¾ããã</p>')
    if bear_stocks:
        parts.append('<p style="margin:0.6em 0 0.2em;font-size:0.88em;color:var(--down)">ð´ å¼±æ°ï¼å£²ãã·ã°ãã«åªå¢ï¼</p><ul class="strategy-list">')
        for sc, st in bear_stocks:
            rsi = st.get("rsi","")
            ov = f' â ï¸ RSIéç±({rsi})' if rsi and float(rsi) >= 70 else ""
            parts.append(f'<li><b>{esc(st.get("name",""))}</b>ï¼{esc(st.get("code",""))}ï¼â å¼±æ°ã¹ã³ã¢ {sc}{ov}</li>')
        parts.append('</ul>')
    parts.append('</div>')

    # å¥½ææéç¤º
    parts.append('<div class="strategy-block">')
    parts.append('<h4>ð å¥½ææéç¤ºéæï¼ä¸æ¹ä¿®æ­£ã»å¢éç­ï¼</h4>')
    parts.append('<p class="strategy-note">TDnetã«ä¸æ¹ä¿®æ­£ã»å¢éãªã©å¥½ææãå«ãéç¤ºãè¡ã£ãéæã§ãã<b>ç¿å¶æ¥­æ¥ä»¥éã®æ ªä¾¡åå¿ã«æ³¨ç®ã</b>éç¤ºåæã®ãç¢ºèªãã</p>')
    if growth:
        parts.append('<ul class="strategy-list">')
        for g in growth[:5]:
            co = esc(g.get("company",""))
            ttl = esc((g.get("title") or "")[:45])
            url = g.get("url","")
            cat = esc((g.get("catalyst") or "")[:60])
            lnk = f'<a href="{esc(url)}" target="_blank">{ttl}â¦</a>' if url else ttl
            cat_line = f'<br><span style="font-size:0.82em;color:var(--muted)">{cat}</span>' if cat else ''
            parts.append(f'<li><b>{co}</b> â {lnk}{cat_line}</li>')
        parts.append('</ul>')
    else:
        parts.append('<p class="empty" style="margin:0.5em 0">æ¬æ¥ã¯å¥½ææéç¤ºï¼ä¸æ¹ä¿®æ­£ã»å¢éç­ï¼ãè¦å½ããã¾ããã</p>')
    parts.append('</div>')

    # æè³å¤æ­ã¾ã¨ã
    parts.append('<div class="strategy-block strategy-conclusion">')
    parts.append('<h4>ð¯ æè³å¤æ­ã¾ã¨ãã»ä»å¾ã®è¦éã</h4>')
    conclusions = []
    if bull_stocks and mkt_label != "å¼±æ°å°åã":
        names = "ã»".join(st.get("name","") for _,st in bull_stocks[:3])
        conclusions.append(f'ãã¯ãã«ã«ãå¼·æ°ãã¤{esc(mkt_label)}ã®ããã<b>{esc(names)}</b>ã¯ç©æ¥µçã«æ³¨ç®ã§ããå±é¢ã§ãããã ãåå¥ãªã¹ã¯ï¼æ±ºç®ã»å°æ¿å­¦ï¼ã¯å¥éç¢ºèªãã')
    elif bull_stocks:
        names = "ã»".join(st.get("name","") for _,st in bull_stocks[:3])
        conclusions.append(f'<b>{esc(names)}</b>ã¯ãã¯ãã«ã«å¼·æ°ã§ãããå¨ä½å°åããå¼±ãããè¿½ãããããã«æ³¨æãæ¼ãç®ã§æ¾ãæ¦ç¥ãç¡é£ã§ãã')
    else:
        conclusions.append('ç¾æç¹ã§ãã¯ãã«ã«å¼·æ°ã®éæããªããæ°è¦è²·ãã®æ ¹æ ãèãå±é¢ã§ããç¸å ´å¨ä½ã®ååãç¢ºèªããªããæ§å­è¦ãç¡é£ã§ãã')
    if growth:
        co_names = "ã»".join((g.get("company") or "")[:10] for g in growth[:3])
        conclusions.append(f'å¥½ææéç¤ºéæï¼<b>{esc(co_names)}</b>ç­ï¼ã¯ç¿å¶æ¥­æ¥ã®å¯ãä»ãã§ã®ã®ã£ããã¢ãããæå¾ã§ãã¾ãããã ãææåºå°½ããå£²ãã®ãªã¹ã¯ãå¿µé ­ã«ã')
    if caution_list:
        c_str = "ã".join(caution_list)
        conclusions.append(f'â ï¸ <b>RSIéç±ï¼70è¶ï¼ã®éæ: {esc(c_str)}</b> â ç­æçãªå©çç¢ºå®å£²ããèª¿æ´ãå¥ãããããããæ°è¦è¿½ãããã¯é¿ããæ¹ãç¡é£ã§ãã')
    if mkt_label == "å¼±æ°å°åã":
        conclusions.append('â ï¸ ç±³å½å¸å ´ã»æ¥çµåç©ãè»èª¿ã§ããå¨ä½ç¸å ´ã®ä¸è½ã«å¼ããããããªã¹ã¯ãé«ãã<b>å¨è¬çã«æ°è¦ã®è²·ãã¯æéã«ã</b>ææã¡ãã¸ã·ã§ã³ã¯å©çç¢ºå®ãæåãã©ã¤ã³ã®ç¢ºèªãã')
    parts.append('<ul class="strategy-conclusion-list">')
    for con in conclusions:
        parts.append(f'<li>{con}</li>')
    parts.append('</ul>')
    parts.append('<p class="strategy-note" style="margin-top:0.8em">â ï¸ ä¸è¨ã¯ãã¯ãã«ã«ææ¨ã»éç¤ºæå ±ç­ãçµã¿åãããæ©æ¢°çãªåèæå ±ã§ããæè³å©è¨ã§ã¯ãªããæçµå¤æ­ã¯å¿ããèªèº«ã®è²¬ä»»ã§è¡ã£ã¦ãã ããã</p>')
    parts.append('</div>')
    return "".join(parts)



# ---------------------------------------------------------------------------
# 鮮度フィルター: 当日（平日）または直前の週末分のみ表示
# ---------------------------------------------------------------------------
def _freshness_cutoff(generated_at_str):
    """生成日時文字列(YYYY-MM-DD HH:MM)から表示すべき最古の日付を返す。
    月曜: 土+日+月分を含める（直前の土曜から）
    土・日: 金+土 / 土+日 を含める
    火〜金: 当日のみ"""
    from datetime import date as _d, datetime as _dt, timedelta as _td
    try:
        dt = _dt.strptime(generated_at_str[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    wd = dt.weekday()  # 0=月, 5=土, 6=日
    if wd == 0:    return dt - _td(days=2)   # 月曜: 土まで遡る
    elif wd == 5:  return dt - _td(days=1)   # 土曜: 金まで遡る
    elif wd == 6:  return dt - _td(days=1)   # 日曜: 土まで遡る
    else:          return dt                  # 火〜金: 当日のみ


def _parse_item_date(s, year):
    """'7/24' や '7月23日(木) 15:00' などから date を取り出す。失敗時は None。"""
    if not s:
        return None
    s = str(s)
    m = re.search(r"(\d{1,2})/(\d{1,2})", s)
    if m:
        try:
            from datetime import date as _d
            return _d(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})\u6708(\d{1,2})\u65e5", s)  # M月D日
    if m:
        try:
            from datetime import date as _d
            return _d(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            pass
    return None


def _filter_by_freshness(items, date_key, generated_at_str):
    """date_key フィールドの日付が cutoff 以降のアイテムのみ返す。
    日付解析に失敗したアイテムはそのまま含める。"""
    cutoff = _freshness_cutoff(generated_at_str)
    if cutoff is None:
        return list(items)
    year = int(generated_at_str[:4])
    return [it for it in items
            if _parse_item_date(it.get(date_key, ""), year) is None
            or _parse_item_date(it.get(date_key, ""), year) >= cutoff]


def _filter_tdnet_freshness(items, generated_at_str):
    """TDnet アイテムの title 末尾に埋め込まれた日付 ('M月D日') で鮮度フィルター。"""
    cutoff = _freshness_cutoff(generated_at_str)
    if cutoff is None:
        return list(items)
    year = int(generated_at_str[:4])
    return [it for it in items
            if _parse_item_date(it.get("title", ""), year) is None
            or _parse_item_date(it.get("title", ""), year) >= cutoff]


def build_html(data: dict) -> str:
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    # 鮮度フィルター: 当日以前の古い好材料・成長株データを非表示
    fresh_us_good_news = _filter_by_freshness(data.get("us_good_news", []), "time", generated_at)
    fresh_growth = _filter_by_freshness(data.get("growth_candidates", []), "asof", generated_at)
    fresh_tdnet_morning = _filter_tdnet_freshness(data.get("tdnet_morning", []), generated_at)
    fresh_tdnet_afterclose = _filter_tdnet_freshness(data.get("tdnet_afterclose", []), generated_at)
    run_type = data.get("run_type", "")
    run_label = {"morning": "æ(å¯ãä»ãå)æ´æ°", "evening": "å¤(å¼ãå¾)æ´æ°"}.get(run_type, run_type)

    us = data.get("us_market", {})
    fx = data.get("fx", {})
    fut = data.get("nikkei_futures", {})

    idx_cards = ""
    for key, label in [("sp500", "S&P500"), ("dow", "NYãã¦"), ("nasdaq", "ãã¹ããã¯ç·å"), ("sox", "SOXææ°(åå°ä½)")]:
        d = us.get(key, {})
        idx_cards += section_index_row(label, d.get("value", "â"), d.get("change_pct"), d.get("asof"))
    idx_cards += section_index_row("USD/JPY", fx.get("value", "â"), fx.get("change_pct"), fx.get("asof"))
    idx_cards += section_index_row("æ¥çµ225åç©(CME/å¤§éª)", fut.get("value", "â"), fut.get("change_pct"), fut.get("asof"))
    idx_cards += section_index_row("æ¥çµå¹³å(ç¾ç©ã»ååçµå¤)", data.get("nikkei225", {}).get("value", "â"),
                                     data.get("nikkei225", {}).get("change_pct"), data.get("nikkei225", {}).get("asof"))

    mood_html = market_mood_html(data)
    theme_html = theme_summary_html(data)
    calendar_html = economic_calendar_html(data.get("economic_calendar", []))

    morning_html = f"""
    <section id="morning">
      <h2>ð å¯ãä»ãåã»ã¯ã·ã§ã³</h2>
      <p class="section-desc">åæ¥ã®ç±³å½å¸å ´ã»çºæ¿ã»æéå¤ãã¥ã¼ã¹ã»TDnetæ©æã¾ã§ã®éç¤ºã»è©±é¡æ ªãã¾ã¨ãã¦ãã¾ããå½æ¥ã®ä»è¾¼ã¿éææ¤è¨ã®åèæå ±ã§ãã</p>
      <div class="card">
        <h3>ç±³å½å¸å ´ã»çºæ¿ã»æ¥çµåç©</h3>
        <div class="idx-grid">{idx_cards}</div>
      </div>
      <div class="card">
        <h3>ð çµæ¸ã«ã¬ã³ãã¼(éè¦åº¦)</h3>
        <p class="section-desc">éç¨çµ±è¨ã»CPIã»æ¥éä¼åãªã©ãç¸å ´ãåããããã¤ãã³ããéè¦åº¦(â)ã§ç¤ºãã¦ãã¾ãã<b>å®éã®ç¸å ´å¤åãä¿è¨¼ãããã®ã§ã¯ããã¾ããã</b></p>
        {calendar_html}
      </div>
      <div class="card">
        <h3>ð¯ æ¬æ¥ã®æ³¨ç®ãã¼ãã¨é¢é£éæ</h3>
        <p class="section-desc">ãã¥ã¼ã¹ã®æè³é¢é£åéã»æ³¨ç®ä¼æ¥­ã¿ã°ãéç´ããåèæå ±ã§ãã<b>æè³å©è¨ã§ã¯ãªããå®éã«æ ªä¾¡ãåããã¨ãä¿è¨¼ãããã®ã§ã¯ããã¾ããã</b></p>
        {theme_html}
      </div>
      <div class="card">
        <h3>æéå¤ã»æã®ä¸»è¦ãã¥ã¼ã¹</h3>
        {news_list(data.get("overnight_news", []))}
      </div>
      <div class="card">
        <h3>TDnet é©æéç¤º(æã¾ã§ã®å)</h3>
        {tdnet_table(data.get("tdnet_morning", []))}
      </div>
      <div class="card">
        <h3>åºæ¥é«ã»å¤åãã§è©±é¡ã®éæ</h3>
        {movers_table(data.get("movers_morning", []))}
      </div>
    </section>"""

    good_news_rank_html_jp = good_news_ranking_html_jp(
        fresh_tdnet_morning, fresh_tdnet_afterclose, data.get("technical", [])
    )
    good_news_rank_html_us = good_news_ranking_html_us(
        fresh_us_good_news
    )

    evening_html = f"""
    <section id="evening">
      <h2>ð å¼ãå¾ã»ã¯ã·ã§ã³</h2>
      <p class="section-desc">æ¬æ¥ã®TDneté©æéç¤º(æ±ºç®ã»æ¥­ç¸¾ä¿®æ­£ã»èªå·±æ ªè²·ããªã©)ã¨å¼ãå¾ã®éè¦ãã¥ã¼ã¹ãã¾ã¨ãã¦ãã¾ããç¿æ¥ä»¥éã®ä»è¾¼ã¿éææ¤è¨ã®åèæå ±ã§ãã</p>
      <div class="card">
        <h3>æ¬æ¥ã®TDneté©æéç¤º</h3>
        {tdnet_table(data.get("tdnet_afterclose", []), empty_msg="æ¬æ¥ã®é©æéç¤ºãã¼ã¿ã¯åå¾ã§ãã¾ããã§ããã")}
      </div>
      <div class="card">
        <h3>å¼ãå¾ã®ä¸»è¦ãã¥ã¼ã¹</h3>
        {news_list(data.get("afterclose_news", []))}
      </div>
      <div class="card">
        <h3>æ¬æ¥ã®å¤åãã»åºæ¥é«ã§è©±é¡ã®éæ</h3>
        {movers_table(data.get("movers_afterclose", []))}
      </div>
      <div class="card">
        <h3>TDnetéç¤º å¥½ææã©ã³ã­ã³ã°(æ¥æ¬æ ª TOP5)</h3>
        <p class="rank-note">
          æ¬æ¥ã®TDnetéç¤ºã®ãã¡ãä¸æ¹ä¿®æ­£ã»æé«çã»å¢éãªã©<b>æç¢ºãªå¥½ææã®ã¿</b>ãå¯¾è±¡ã«ãåå®¹ã®å¼·ãã§æ©æ¢°çã«é ä½ä»ããã¦ãã¾ã
          (ä¸æ¹ä¿®æ­£ã»æ¸éãªã©å¼±ææã®éç¤ºã¯å¯¾è±¡å¤)ãåéæã«ã¤ãã¦ãâ å·ä½çã«ä½ãéç¤ºãããããâ¡éå»ã®é¡ä¼¼éç¤ºã«åºã¥ãæ³å®ã¤ã³ãã¯ã(åèå¤)ã
          â¢å¥½ææã¨å¤æ­ããçç±ãâ£ç´è¿ã®ãã¯ãã«ã«ææ¨ã«åºã¥ãåèã³ã¡ã³ãããæè¨ãã¦ãã¾ãã
          <b>æ³å®ã¤ã³ãã¯ãã¯éå»ã®é¡ä¼¼ã±ã¼ã¹ã®ä¸è¬çãªå¾åãç¤ºãåèå¤ã§ãããæ ªä¾¡ãå®éã«ãã®éãä¸æãããã¨ãç¢ºç´ã»äºæ³ãããã®ã§ã¯ããã¾ããã</b>
        </p>
        {good_news_rank_html_jp}
      </div>
      <div class="card">
        <h3>å¥½ææã©ã³ã­ã³ã°(ç±³å½æ ª TOP5)</h3>
        <p class="rank-note">
          æ±ºç®ä¸æ¯ãã»ã¬ã¤ãã³ã¹ä¸æ¹ä¿®æ­£ã»ã¢ããªã¹ãè©ä¾¡å¼ãä¸ããªã©<b>æç¢ºãªå¥½ææã®ã¿</b>ãå¯¾è±¡ã«ãåå®¹ã®å¼·ãã§æ©æ¢°çã«é ä½ä»ããã¦ãã¾ãã
          åéæã«ã¤ãã¦ãâ å·ä½çã«ä½ãçºè¡¨ãããããâ¡éå»ã®é¡ä¼¼ãã¥ã¼ã¹ã«åºã¥ãæ³å®ã¤ã³ãã¯ã(åèå¤)ãâ¢å¥½ææã¨å¤æ­ããçç±ããæè¨ãã¦ãã¾ãã
          <b>æ³å®ã¤ã³ãã¯ãã¯éå»ã®é¡ä¼¼ã±ã¼ã¹ã®ä¸è¬çãªå¾åãç¤ºãåèå¤ã§ãããæ ªä¾¡ãå®éã«ãã®éãä¸æãããã¨ãç¢ºç´ã»äºæ³ãããã®ã§ã¯ããã¾ããã</b>
        </p>
        {good_news_rank_html_us}
      </div>
    </section>"""

    bull_rank_html = bull_ranking_html(data.get("technical", []))

    technical_html = f"""
    <section id="technical">
      <h2>ð æ ªä¾¡è¨ºæ­(ãã¯ãã«ã«ææ¨)</h2>
      <p class="section-desc">
        ç§»åå¹³åç·ã»RSIãªã©ç¡æã§åå¾ã§ãããã¯ãã«ã«ææ¨ã«ãã¨ã¥ãå®¢è¦³çãªãå¼·æ°/å¼±æ°ã·ã°ãã«ãã®ä¸è¦§ã§ãã
        <b>å°æ¥ã®æ ªä¾¡ãäºæ³ã»ä¿è¨¼ãããã®ã§ã¯ããã¾ããã</b>
      </p>
      <div class="card">
        {technical_table(data.get("technical", []))}
      </div>
      <div class="card">
        <h3>å¼·æ°ã»å¼±æ°ã·ã°ãã«ã©ã³ã­ã³ã°</h3>
        <p class="rank-note">
          ç§»åå¹³åç·ã»RSIãªã©éå»ãã¼ã¿ã«åºã¥ãæ©æ¢°çãªãè²·ãã·ã°ãã«æ°ãã®å¾åãã©ã³ã­ã³ã°åãããã®ã§ãã
          <b>ããã¾ã§éå»ãã¼ã¿ã«åºã¥ãå¾åã§ãããå°æ¥ã®æ ªä¾¡å¤åãä¿è¨¼ãããã®ã§ã¯ããã¾ããã</b>
        </p>
        {bull_rank_html}
      </div>
    </section>"""

    growth_html = f"""
    <section id="growth">
      <h2>ð± æé·æ ªã¦ã©ãã(æ±ºç®ã»å¥½ææãã¼ã¹)</h2>
      <p class="section-desc">
        ä¸»åã¦ã©ãããªã¹ãã¯å¤ä½ç½®ãé«ãã®éæãå«ããããå¥æ ã¨ãã¦ãTDnetãæ¥­ç¸¾äºæ³ã®ä¿®æ­£ãéç¤ºã®ãã¡
        <b>ä¸æ¹ä¿®æ­£ã»å¢éãªã©æç¢ºãªå¥½ææã­ã¼ã¯ã¼ããå«ãéç¤ºã®ã¿</b>ãæ©æ¢°çã«æ½åºããåè£ä¸è¦§ã§ãã
        ååè£ã«ã¯å®éã®éç¤ºPDFã¸ã®ç´ãªã³ã¯ãä»ãã¦ãããæ ¹æ ã¯éç¤ºåæã§ãç¢ºèªããã ãã¾ãã
        <b>æè³å©è¨ã§ã¯ãªããå°æ¥ã®æ ªä¾¡ä¸æãä¿è¨¼ãããã®ã§ã¯ããã¾ããã</b>
      </p>
      <div class="card">
        <h3>å¥½ææéç¤ºã«åºã¥ãæé·æ ªåè£</h3>
        {growth_candidates_html(fresh_growth)}
      </div>
    </section>"""

    strategy_summary = strategy_summary_html(data)
    strategy_section_html = f"""
    <section id="strategy">
      <h2>ð¯ æè³æ¦ç¥ã¾ã¨ã</h2>
      <p class="section-desc">ä»æ¥ã®å°åãã»ãã¯ãã«ã«ç¶æã»å¥½ææéç¤ºãçµ±åããæè³å¤æ­ã®åèæå ±ã§ããããã¾ã§åèã§ããã<b>æè³å©è¨ã§ã¯ããã¾ãããæçµå¤æ­ã¯ãèªèº«ã®è²¬ä»»ã§ã</b></p>
      <div class="card">
        {strategy_summary}
      </div>
    </section>"""

    disclaimer_text = (
        "æ¬ãã¼ã¸ã®æå ±ã¯ãYahoo!ãã¡ã¤ãã³ã¹ã»TDnet(é©æéç¤ºæå ±é²è¦§ãµã¼ãã¹)ã»æè³ã®æ£®(ãã¯ãã«ã«åæ)ãªã©"
        "ç¡æã§å¬éããã¦ããæå ±æºããã¨ã«èªåçã«ã¾ã¨ãããã®ã§ãã"
        "åå®¹ã®æ­£ç¢ºæ§ã»å®å¨æ§ã»ææ°æ§ã¯ä¿è¨¼ããã¾ããã"
        "ãå¼·æ°/å¼±æ°ã·ã°ãã«ãç­ã®è¡¨ç¤ºã¯ç§»åå¹³åç·ãRSIãªã©éå»ãã¼ã¿ã«åºã¥ãæ©æ¢°çãªè¨ºæ­ã§ããã"
        "<b>æè³å©è¨ã§ã¯ãªããå°æ¥ã®æ ªä¾¡å¤åãä¿è¨¼ãããã®ã§ãããã¾ããã</b>"
        "æè³ã«é¢ããæçµå¤æ­ã¯ãå¿ããèªèº«ã®è²¬ä»»ã§è¡ã£ã¦ãã ããã"
    )

    sources_html = """
    <div class="sources">
      ä¸»ãªæå ±æº: Yahoo!ãã¡ã¤ãã³ã¹ (finance.yahoo.co.jp) / TDnet é©æéç¤ºæå ±é²è¦§ãµã¼ãã¹
      (release.tdnet.info, éå¬å¼API: webapi.yanoshin.jp) / æè³ã®æ£® ãã¯ãã«ã«åæ (nikkeiyosoku.com)ã
      åæå ±ã®èä½æ¨©ã»å©ç¨æ¡ä»¶ã¯æä¾åã«å¸°å±ãã¾ããè»¢è¼ã»åéå¸ã¯è¡ãããåäººã®æè³å¤æ­ã®åèæå ±ã¨ãã¦ã®ã¿å©ç¨ãã¦ãã ããã
    </div>"""

    bg_url = pick_background_image(generated_at, run_type)
    page_css = CSS.replace("__BG_URL__", bg_url)

    # èæ¯ã¹ã©ã¤ãã·ã§ã¼: ç¾å¨æå»/æå¤ã«å¿ãããæ¬æ¥ã®åçããåé ­(=æåã«è¡¨ç¤º)ã«ãã¦ã
    # æ®ãã®åçããã£ããã¯ã­ã¹ãã§ã¼ãã§å·¡åããããç»è³ªã¯åç»åã®ã¾ã¾(opacityã®ã¿ã§é·ç§»)ã
    bg_urls = [u for u, _ in BACKGROUND_IMAGES]
    if bg_url in bg_urls:
        start = bg_urls.index(bg_url)
        rotation = BACKGROUND_IMAGES[start:] + BACKGROUND_IMAGES[:start]
    else:
        rotation = [(bg_url, "")] + [t for t in BACKGROUND_IMAGES if t[0] != bg_url]
    bg_photo_divs = "".join(
        f'<div class="bg-photo{" is-active" if i == 0 else ""}" '
        f'style="background-image:url(\'{esc(u)}\')" data-order="{i}" data-caption="{esc(cap)}"></div>'
        for i, (u, cap) in enumerate(rotation)
    )

    html_out = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>try{{if(localStorage.getItem('jpdt_theme')==='light'){{document.documentElement.setAttribute('data-theme','light');}}}}catch(e){{}}</script>
<title>æ¥æ¬æ ªãã¤ãã¬ã¼ãæå ±ããã·ã¥ãã¼ã</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Playfair+Display:wght@600;700&family=Shippori+Mincho:wght@600;700&family=Noto+Sans+JP:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{page_css}</style>
</head>
<body>
<div class="bg-photo-stack" aria-hidden="true">{bg_photo_divs}</div>
<div class="bg-overlay" aria-hidden="true"></div>
<header class="topbar">
  <div class="topbar-inner">
    <div class="topbar-title">
      <span class="eyebrow">TOKYO STOCK EXCHANGE ã» DAY TRADE INTELLIGENCE</span>
      <h1>æ¥æ¬æ ª(æ±è¨¼)ãã¤ãã¬ã¼ãæå ±ããã·ã¥ãã¼ã<span class="run-badge">{esc(run_label)}</span></h1>
      <div class="subtitle">æçµæ´æ°: {esc(generated_at)} (JST)<span class="rel-time" data-generated="{esc(generated_at)}"></span> ã» æ¯æ¥ æ6:00 / å¤21:00 ã«èªåæ´æ°</div>
    </div>
    <div class="top-controls">
      <nav class="tabs">
        <a href="#morning">ð å¯ãä»ãå</a>
        <a href="#evening">ð å¼ãå¾</a>
        <a href="#technical">ð æ ªä¾¡è¨ºæ­</a>
        <a href="#growth">ð± æé·æ ª</a>
        <a href="#strategy">ð¯ æè³æ¦ç¥ã¾ã¨ã</a>
      </nav>
      <button id="themeToggle" class="theme-toggle" type="button" aria-label="è¡¨ç¤ºãã¼ããåãæ¿ã" title="ã©ã¤ã/ãã¼ã¯ãã¼ãåæ¿">ð</button>
    </div>
  </div>
</header>
<div class="wrap">
  <div class="disclaimer">
    â ï¸ <b>æ¬ãµã¤ãã¯æå ±æä¾ã®ã¿ãç®çã¨ããæè³å©è¨ã§ã¯ããã¾ããã</b> {disclaimer_text}
  </div>
  {mood_html}
  <label class="fav-filter"><input type="checkbox" id="favFilterToggle"> â ãæ°ã«å¥ãã®ã¿è¡¨ç¤º(ã³ã¼ãæ¬ã®âã§ç»é²)</label>

  {morning_html}
  {evening_html}
  {technical_html}
  {growth_html}

  {strategy_section_html}

  <footer>
    <div class="disclaimer">
      â ï¸ åæ²: {disclaimer_text}
    </div>
    {sources_html}
  </footer>
</div>
<div class="bg-spacer" aria-hidden="true">
  <div class="bg-caption" id="bgCaption">ð æ±äº¬ã»{esc(rotation[0][1]) if rotation and rotation[0][1] else "æ±äº¬"}</div>
</div>
<button id="backToTop" type="button" aria-label="ãã¼ã¸ä¸é¨ã¸æ»ã" title="ãããã¸æ»ã">â</button>
{JS_SCRIPT}
</body>
</html>
"""
    return html_out


def main():
    data_path = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR / "data.json"
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE_DIR / "jp_daytrade_dashboard.html"

    if not data_path.exists():
        print(f"[ERROR] data.json ãè¦ã¤ããã¾ãã: {data_path}", file=sys.stderr)
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    html_out = build_html(data)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"[OK] ããã·ã¥ãã¼ããçæãã¾ãã: {out_path}")


if __name__ == "__main__":
    main()
