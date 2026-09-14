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
    return f"""
        <div class="chip {cls}" data-code="{esc(imp['code'])}">
          <button class="chip-head" type="button" data-filter-code="{esc(imp['code'])}" title="この銘柄に関係するニュースだけ表示">
            <span class="chip-mark">{mark}</span>
            <span class="chip-name">{esc(imp['name'])}</span>
            <span class="chip-code">{esc(imp['code'])}</span>
            <span class="chip-strength">影響{esc(imp.get('strength', '中'))}</span>
          </button>
          <div class="chip-body">
            <span class="chip-tag">{esc(origin)}</span>
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

    return f"""
    <article class="news-card" data-category="{esc(item['category'])}" data-importance="{esc(item['importance'])}"
             data-codes="{esc(codes)}" data-search="{esc(search_blob)}">
      <div class="news-meta">
        <span class="stars" title="重要度 {esc(item['importance'])} / 5">{stars(item['importance'])}</span>
        <span class="cat">{esc(item.get('category_emoji', '📰'))} {esc(item.get('category_label', ''))}</span>
        <span class="time">{esc(_relative(item.get('published_at'), now))}</span>
        <span class="source">{esc(item.get('source', ''))}</span>
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
:root{
  --bg:#0c1220; --bg-soft:#121a2c; --card:#151f36; --card-2:#1b273f;
  --line:rgba(255,255,255,.09); --text:#e9eefb; --muted:#98a5c0;
  --up:#ff6b6b; --down:#4dabf7; --flat:#c2a24a; --accent:#7aa2ff;
  --shadow:0 10px 30px rgba(0,0,0,.35);
}
:root[data-theme="light"]{
  --bg:#f4f6fb; --bg-soft:#ffffff; --card:#ffffff; --card-2:#f7f9ff;
  --line:rgba(16,24,40,.1); --text:#131a2a; --muted:#5d6b86;
  --up:#d62828; --down:#1864ab; --flat:#8a6d1f; --accent:#2b5fd9;
  --shadow:0 8px 24px rgba(16,24,40,.08);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:"Noto Sans JP",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  line-height:1.7;-webkit-font-smoothing:antialiased}
a{color:inherit}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--flat)}

header.site{position:sticky;top:0;z-index:20;background:rgba(12,18,32,.92);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
:root[data-theme="light"] header.site{background:rgba(255,255,255,.94)}
.head-inner{max-width:1240px;margin:0 auto;padding:14px 20px 10px;
  display:flex;gap:16px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
.brand h1{margin:0;font-size:20px;letter-spacing:.02em}
.brand .eyebrow{font-size:11px;letter-spacing:.18em;color:var(--muted);text-transform:uppercase}
.brand .sub{font-size:12px;color:var(--muted);margin-top:2px}
.head-actions{display:flex;gap:8px;align-items:center}
.theme-toggle{background:var(--card);border:1px solid var(--line);color:var(--text);
  border-radius:999px;padding:7px 13px;cursor:pointer;font-size:13px}
.theme-toggle:hover{border-color:var(--accent)}

.market-bar{display:flex;gap:10px;overflow-x:auto;max-width:1240px;margin:0 auto;
  padding:0 20px 12px;scrollbar-width:thin}
.ticker{display:flex;gap:8px;align-items:baseline;background:var(--card);border:1px solid var(--line);
  border-radius:10px;padding:6px 12px;white-space:nowrap;font-size:12px}
.ticker-label{color:var(--muted)} .ticker-value{font-weight:700}
.ticker-change{font-weight:700;font-size:12px}

.wrap{max-width:1240px;margin:0 auto;padding:20px}
.notice{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:12px;padding:12px 16px;font-size:12.5px;color:var(--muted);margin-bottom:18px}
.notice b{color:var(--text)}
.notice.sample-banner{border-left-color:var(--flat);color:var(--text)}

.controls{position:sticky;top:74px;z-index:15;background:var(--bg);padding:10px 0 12px;
  border-bottom:1px solid var(--line);margin-bottom:18px}
.filter-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.filter-chip{background:var(--card);border:1px solid var(--line);color:var(--text);border-radius:999px;
  padding:6px 13px;font-size:12.5px;cursor:pointer;display:inline-flex;gap:6px;align-items:center}
.filter-chip:hover{border-color:var(--accent)}
.filter-chip.is-active{background:var(--accent);border-color:var(--accent);color:#fff}
.chip-count{opacity:.7;font-size:11px}
.search-row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.search-row input,.search-row select{background:var(--card);border:1px solid var(--line);color:var(--text);
  border-radius:10px;padding:8px 12px;font-size:13px}
.search-row input{flex:1;min-width:200px}
.active-filter{display:none;align-items:center;gap:8px;font-size:12.5px;color:var(--muted)}
.active-filter.is-on{display:inline-flex}
.active-filter button{background:transparent;border:1px solid var(--line);color:var(--text);
  border-radius:999px;padding:3px 10px;cursor:pointer;font-size:12px}

.layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:22px;align-items:start}
@media(max-width:960px){.layout{grid-template-columns:1fr}.controls{top:0}}

.news-card{background:var(--card);border:1px solid var(--line);border-radius:16px;
  padding:18px 20px;margin-bottom:16px;box-shadow:var(--shadow)}
.news-card[data-importance="5"]{border-left:4px solid var(--up)}
.news-card[data-importance="4"]{border-left:4px solid var(--accent)}
.news-meta{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:12px;color:var(--muted)}
.stars{color:#f2c744;letter-spacing:1px}
.cat{background:var(--card-2);border:1px solid var(--line);border-radius:999px;padding:2px 10px}
.news-title{margin:8px 0 6px;font-size:17px;line-height:1.55}
.news-title a{text-decoration:none}
.news-title a:hover{text-decoration:underline;color:var(--accent)}
.summary{margin:6px 0;font-size:13.5px;color:var(--text)}
.comment{margin:6px 0;font-size:13px;color:var(--muted);background:var(--card-2);
  border-radius:10px;padding:9px 12px}
.comment-label{display:inline-block;font-size:11px;color:var(--accent);margin-right:8px;font-weight:700}
.themes{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0 4px;font-size:11.5px;color:var(--muted)}
.theme-tag{background:var(--card-2);border:1px solid var(--line);border-radius:6px;padding:1px 8px}
.why{opacity:.75}

.impact-block{margin-top:12px;border-top:1px dashed var(--line);padding-top:12px}
.impact-block.empty{font-size:12.5px;color:var(--muted)}
.impact-head{font-size:12.5px;font-weight:700;margin-bottom:9px;display:flex;gap:10px;flex-wrap:wrap}
.impact-counts{font-weight:600;font-size:12px;display:flex;gap:10px}
.chips{display:grid;grid-template-columns:repeat(auto-fill,minmax(226px,1fr));gap:8px}
.chip{border:1px solid var(--line);border-radius:12px;background:var(--card-2);overflow:hidden}
.chip.up{border-left:3px solid var(--up)} .chip.down{border-left:3px solid var(--down)}
.chip.flat{border-left:3px solid var(--flat)}
.chip-head{width:100%;display:flex;gap:7px;align-items:baseline;background:transparent;border:0;
  color:var(--text);padding:8px 10px 4px;cursor:pointer;text-align:left;font-size:13px}
.chip-head:hover .chip-name{text-decoration:underline}
.chip.up .chip-mark{color:var(--up)} .chip.down .chip-mark{color:var(--down)}
.chip.flat .chip-mark{color:var(--flat)}
.chip-name{font-weight:700}
.chip-code{font-size:11px;color:var(--muted)}
.chip-strength{margin-left:auto;font-size:10.5px;color:var(--muted);white-space:nowrap}
.chip-body{padding:0 10px 9px;font-size:11.5px;color:var(--muted);display:flex;flex-wrap:wrap;gap:6px}
.chip-tag{background:var(--card);border:1px solid var(--line);border-radius:5px;padding:0 6px;font-size:10.5px}
.chip-reason{flex:1 1 100%;line-height:1.55}
.chip-link{color:var(--accent);text-decoration:none;font-size:11px}

.related{margin-top:10px;font-size:12px;color:var(--muted)}
.related summary{cursor:pointer}
.related ul{margin:8px 0 0;padding-left:18px}
.related li{margin-bottom:4px}
.related-source{margin-left:8px;font-size:11px;opacity:.8}

aside.side{position:sticky;top:150px}
@media(max-width:960px){aside.side{position:static}}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px 16px 8px;
  box-shadow:var(--shadow);margin-bottom:16px}
.panel h2{margin:0 0 4px;font-size:15px}
.panel .panel-desc{margin:0 0 12px;font-size:11.5px;color:var(--muted)}
.rank-row{border-top:1px solid var(--line)}
.rank-row:first-of-type{border-top:0}
.rank-line{display:flex;align-items:center;gap:4px}
.rank-toggle{background:transparent;border:0;color:var(--muted);cursor:pointer;font-size:12px;
  padding:6px 4px;border-radius:6px}
.rank-toggle:hover{color:var(--accent)}
.rank-row.is-open .rank-toggle{transform:rotate(180deg)}
.rank-head{flex:1;display:flex;gap:9px;align-items:center;background:transparent;border:0;color:var(--text);
  padding:9px 2px;cursor:pointer;text-align:left;font-size:13px}
.rank-head:hover .rank-name{color:var(--accent)}
.rank-no{width:20px;font-size:11px;color:var(--muted)}
.rank-name{flex:1;font-weight:600}
.rank-code{display:block;font-size:10.5px;color:var(--muted);font-weight:400}
.rank-badge{font-size:11px;white-space:nowrap}
.rank-mentions{font-size:11px;color:var(--muted)}
.rank-news{display:none;margin:0 0 10px;padding-left:30px;font-size:11.5px}
.rank-row.is-open .rank-news{display:block}
.rank-news li{margin-bottom:4px}
.rank-news a{color:var(--muted);text-decoration:none}
.rank-news a:hover{color:var(--accent)}

.empty,.no-result{background:var(--card);border:1px dashed var(--line);border-radius:14px;
  padding:20px;text-align:center;color:var(--muted);font-size:13px}
.no-result{display:none}
footer{margin-top:28px;padding:20px 0 40px;border-top:1px solid var(--line);font-size:11.5px;color:var(--muted)}
footer a{color:var(--accent)}
.back-top{position:fixed;right:18px;bottom:18px;width:42px;height:42px;border-radius:50%;
  border:1px solid var(--line);background:var(--card);color:var(--text);cursor:pointer;display:none;
  box-shadow:var(--shadow);font-size:16px}
.back-top.is-on{display:block}
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

  var cards = Array.prototype.slice.call(document.querySelectorAll('.news-card'));
  var searchInput = document.getElementById('searchInput');
  var minStars = document.getElementById('minStars');
  var noResult = document.getElementById('noResult');
  var activeFilter = document.getElementById('activeFilter');
  var activeFilterText = document.getElementById('activeFilterText');
  var state = { category:'all', text:'', stars:0, code:'' };

  function apply(){
    var shown = 0;
    cards.forEach(function(card){
      var ok = true;
      if(state.category !== 'all' && card.dataset.category !== state.category){ ok = false; }
      if(ok && state.stars && parseInt(card.dataset.importance,10) < state.stars){ ok = false; }
      if(ok && state.code && (' ' + card.dataset.codes + ' ').indexOf(' ' + state.code + ' ') === -1){ ok = false; }
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

  document.querySelectorAll('.filter-chip').forEach(function(chip){
    chip.addEventListener('click', function(){
      document.querySelectorAll('.filter-chip').forEach(function(c){ c.classList.remove('is-active'); });
      chip.classList.add('is-active');
      state.category = chip.dataset.category;
      apply();
    });
  });

  searchInput && searchInput.addEventListener('input', function(){
    state.text = searchInput.value.trim().toLowerCase();
    apply();
  });
  minStars && minStars.addEventListener('change', function(){
    state.stars = parseInt(minStars.value, 10) || 0;
    apply();
  });

  document.addEventListener('click', function(ev){
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

  var clearBtn = document.getElementById('clearCode');
  clearBtn && clearBtn.addEventListener('click', function(){ state.code = ''; apply(); });

  var backTop = document.getElementById('backTop');
  window.addEventListener('scroll', function(){
    backTop.classList.toggle('is-on', window.scrollY > 600);
  });
  backTop.addEventListener('click', function(){ window.scrollTo({ top:0, behavior:'smooth' }); });

  apply();
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
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
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
