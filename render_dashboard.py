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
import re
import sys
import html as html_lib
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

# 東京の夜景写真(Unsplash・商用利用可・クレジット表記不要)
# サイト全体の背景に使う写真。実行日と朝/夜の更新タイミングに応じて自動的に切り替える。
# (六本木ヒルズの室内窓越しカットは彩度が低くモノクロに見えるため除外している)
# 各背景写真は (URL, 撮影地のラベル) のタプル。ラベルはページ最下部のキャプション表示に使う。
BACKGROUND_IMAGES = [
    ("https://images.unsplash.com/photo-1759970752518-b0ffa38c130b?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "東京タワー"),
    ("https://images.unsplash.com/photo-1749916884078-e8359b2adcdd?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "渋谷スクランブル交差点"),
    ("https://images.unsplash.com/photo-1741097574041-d70d3fe6a3ab?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "レインボーブリッジ・お台場"),
    ("https://images.unsplash.com/photo-1768711478173-07768f32b426?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "東京スカイツリー"),
    ("https://images.unsplash.com/photo-1758881606455-26cc1c2c8de4?auto=format&fit=crop&w=2400&q=90&sat=40&con=10&vib=25", "新宿"),
    ("https://images.unsplash.com/photo-1624434512895-2d1887ebfccf?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "六本木"),
    ("https://images.unsplash.com/photo-1646547571578-bfd7b1457a65?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "秋葉原"),
    ("https://images.unsplash.com/photo-1690971324341-94fac8ec6873?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "丸の内・東京駅"),
    ("https://images.unsplash.com/photo-1622767833293-8d1e6878c27f?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "銀座"),
]


def pick_background_image(generated_at: str, run_type: str) -> str:
    """実行日(YYYY-MM-DD)と朝/夜の区分から背景写真を決定する。
    同じ日でも朝と夜で違う写真になり、日が変わるとローテーションが進む。"""
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


def mini_bar_html(value, scale=8.0):
    """前日比などの数値を、中心から左右に伸びるミニ diverging bar として可視化する。
    真のローソク足チャートには時系列OHLCデータが必要でdata.jsonには含まれないため、
    既存の数値(前日比%など)を視覚的に把握しやすくする簡易ミニグラフとして提供する。"""
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
    """RSI(14)を0-100の帯グラフ+マーカーで可視化する簡易ゲージ。"""
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
    """銘柄コードをYahoo!ファイナンスの該当ページへのリンクにする(4桁前後の証券コードのみ)。"""
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
        f'aria-label="お気に入り登録" aria-pressed="false">★</button> '
    )


def table_tools_html(placeholder="銘柄名・コードで検索"):
    return f'<div class="table-tools"><input type="search" class="table-search" placeholder="🔍 {esc(placeholder)}"></div>'


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
        change_html = f'<span class="chg {pct_class(change)}">{fmt_pct(change)}</span>{mini_bar_html(change)}'
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
        code = it.get("code", "")
        company = esc(it.get("company", ""))
        title = esc(it.get("title", ""))
        url = esc(it.get("url", "")) or "#"
        tag = esc(it.get("tag", ""))
        tag_html = f'<span class="tag">{tag}</span>' if tag else ""
        rows.append(f"""
        <tr>
          <td class="mono">{time_}</td>
          <td class="mono">{fav_btn_html(code)}{code_link(code)}</td>
          <td>{company}</td>
          <td><a href="{url}" target="_blank" rel="noopener">{title}</a> {tag_html}</td>
        </tr>""")
    return f"""
    {table_tools_html("時刻・コード・会社名・タイトルで検索")}
    <div class="scroll-hint">← 横にスクロールできます</div>
    <div class="table-scroll">
    <table class="tdnet-table" data-sortable="true">
      <thead><tr><th>時刻</th><th>コード</th><th>会社名</th><th>開示タイトル</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


def movers_table(items, empty_msg="該当データが取得できませんでした。"):
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
    <div class="scroll-hint">← 横にスクロールできます</div>
    <div class="table-scroll">
    <table class="movers-table" data-sortable="true">
      <thead><tr><th>コード</th><th>銘柄名</th><th>株価</th><th>前日比</th><th>出来高メモ</th><th>話題の背景</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


def technical_table(items, empty_msg="テクニカルデータが取得できませんでした。"):
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
                rsi_note = ' <span class="tag tag-warn">過熱感</span>'
            elif rsi_f <= 30:
                rsi_note = ' <span class="tag tag-warn">売られ過ぎ</span>'
        except (TypeError, ValueError):
            pass
        signal = it.get("signal", "中立")
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
    <div class="scroll-hint">← 横にスクロールできます</div>
    <div class="table-scroll">
    <table class="technical-table" data-sortable="true">
      <thead><tr><th>コード</th><th>銘柄名</th><th>株価</th><th>前日比</th><th>5日線乖離</th><th>25日線乖離</th><th>RSI(14)</th><th>シグナル</th><th>コメント</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


def parse_signal_counts(summary):
    """summary文字列から「中立X/売りY/買いZ」のシグナル内訳を抽出する。見つからなければNone。"""
    if not summary:
        return None
    m = re.search(r"中立\s*(\d+)\s*/\s*売り\s*(\d+)\s*/\s*買い\s*(\d+)", summary)
    if not m:
        return None
    neutral, sell, buy = (int(x) for x in m.groups())
    return {"neutral": neutral, "sell": sell, "buy": buy}


def rank_label(i):
    medals = ["🥇", "🥈", "🥉"]
    return medals[i] if i < len(medals) else f"{i + 1}位"


def bull_ranking_html(items, empty_msg="シグナルデータが取得できませんでした。"):
    """テクニカル指標の「買いシグナル数」を軸にした、過去データベースの機械的ランキング。
    将来の株価上昇を予想・保証するものではない。"""
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
    rows = []
    for i, (score, counts, it) in enumerate(ranked[:5]):
        code = esc(it.get("code", ""))
        name = esc(it.get("name", ""))
        chg = it.get("change_pct")
        rsi = it.get("rsi", "")
        detail = f"中立{counts['neutral']}/売り{counts['sell']}/買い{counts['buy']}"
        overheat = ""
        try:
            if float(rsi) >= 70:
                overheat = ' <span class="tag tag-warn">過熱感に注意</span>'
        except (TypeError, ValueError):
            pass
        rows.append(f"""
        <div class="rank-item">
          <div class="rank-num">{rank_label(i)}</div>
          <div class="rank-body">
            <div class="rank-head">
              <span class="mono">{code}</span> {name}
              <span class="mono {pct_class(chg)}">{fmt_pct(chg)}</span>
              <span class="score-tag">強気スコア {score:+d}</span>
            </div>
            <div class="rank-desc">シグナル判定: {esc(detail)} ・ RSI(14) {esc(rsi)}{overheat}</div>
          </div>
        </div>""")
    return "".join(rows)


def _technical_lookup(technical):
    """code -> technical指標dict のルックアップテーブルを作る。"""
    lookup = {}
    for t in technical or []:
        code = str(t.get("code", "")).strip()
        if code:
            lookup[code] = t
    return lookup


def _outlook_comment(code, tech_lookup):
    """直近のテクニカル指標(RSI・移動平均乖離・シグナル判定)から、その銘柄について
    端的な参考コメントを機械的に組み立てる。過去の値動き傾向に基づく参考情報であり、
    今後の株価変動を保証・予想するものではない。"""
    t = tech_lookup.get(str(code).strip())
    if not t:
        return "直近のテクニカルデータは今回取得できませんでした。値動きは各種株価情報サービスでご確認ください。"

    parts = []
    rsi = t.get("rsi")
    if isinstance(rsi, (int, float)):
        if rsi >= 70:
            parts.append(f"RSI(14)は{rsi:.1f}で買われすぎ水準にあり、短期的な過熱感に留意")
        elif rsi <= 30:
            parts.append(f"RSI(14)は{rsi:.1f}で売られすぎ水準")
        else:
            parts.append(f"RSI(14)は{rsi:.1f}で中立圏")

    ma25 = t.get("ma25_dev")
    if ma25:
        parts.append(f"25日線から{esc(ma25)}乖離")

    signal = t.get("signal")
    if signal:
        parts.append(f"シグナル判定は「{esc(signal)}」")

    if not parts:
        return "テクニカル指標の参考値が現時点で不足しています。"
    return "、".join(parts) + "。直近の値動き傾向に基づく機械的な参考情報であり、将来の株価変動を保証するものではありません。"



# 日本株(TDnet開示)の好材料カテゴリ定義:重み・強さラベル・具体的な好材料内容・
# 過去の類似開示に基づく想定インパクト(参考値)・好材料と判断する理由をまとめて保持する。
# 想定インパクトはあくまで過去の類似ケースの一般的な傾向を示す参考値であり、
# 株価が実際にその通り上昇することを確約・予想するものではない。
JP_CATALYST_INFO = {
    "最高益": {
        "weight": 5, "strength": "非常に強い好材料",
        "content": "過去最高の業績(純利益・営業利益など)を記録・更新したことを開示",
        "impact": "+5%〜+12%程度",
        "reason": "業績が市場の想定を上回るペースで伸びていることを示し、今後の増益期待から株価評価が見直されやすいため",
    },
    "増収増益": {
        "weight": 4, "strength": "強い好材料",
        "content": "売上・利益がいずれも前期比で増加したことを開示",
        "impact": "+3%〜+8%程度",
        "reason": "収益性と成長性の両方が改善していることが確認され、業績の質の高さが評価されやすいため",
    },
    "特別配当": {
        "weight": 4, "strength": "強い好材料",
        "content": "通常配当に加えて特別配当を実施することを開示",
        "impact": "+2%〜+6%程度",
        "reason": "会社の資金余力や株主還元姿勢の強さを示すシグナルとして受け止められやすいため",
    },
    "上方修正": {
        "weight": 4, "strength": "強い好材料",
        "content": "業績予想(売上・利益)を上方修正したことを開示",
        "impact": "+3%〜+8%程度",
        "reason": "会社自身が業績見通しを引き上げたことで、アナリスト予想や市場期待の上振れにつながりやすいため",
    },
    "業績上方修正": {
        "weight": 4, "strength": "強い好材料",
        "content": "業績予想(売上・利益)を上方修正したことを開示",
        "impact": "+3%〜+8%程度",
        "reason": "会社自身が業績見通しを引き上げたことで、アナリスト予想や市場期待の上振れにつながりやすいため",
    },
    "增配": {
        "weight": 3, "strength": "やや強い好材料",
        "content": "1株当たり配当を増額(増配)することを開示",
        "impact": "+2%〜+5%程度",
        "reason": "配当増額は経営陣が業績の先行きに自信を持っていることの表れとされ、株主還元強化への評価が高まりやすいため",
    },
    "増配": {
        "weight": 3, "strength": "やや強い好材料",
        "content": "1株当たり配当を増額(増配)することを開示",
        "impact": "+2%〜+5%程度",
        "reason": "配当増額は経営陣が業績の先行きに自信を持っていることの表れとされ、株主還元強化への評価が高まりやすいため",
    },
    "自己株買い": {
        "weight": 2, "strength": "やや強い好材料",
        "content": "自己株式の取得(株主還元策)を実施することを開示",
        "impact": "+1%〜+4%程度",
        "reason": "株式数の減少により1株当たり指標(EPSなど)が改善しやすく、需給面でも買い支え要因になりやすいため",
    },
    "株式分割": {
        "weight": 2, "strength": "軽めの好材料",
        "content": "株式分割を実施することを開示",
        "impact": "+1%〜+3%程度",
        "reason": "1株当たりの購入単価が下がり個人投資家が買いやすくなることで、需給が改善しやすいため",
    },
    "配当": {
        "weight": 1, "strength": "軽めの好材料",
        "content": "配当に関する開示",
        "impact": "+1%〜+3%程度",
        "reason": "株主還元に関するプラスの情報として受け止められやすいため",
    },
}
# 弱材料キーワード。含まれる開示は「好材料ランキング」の対象から除外する。
JP_NEGATIVE_KEYWORDS = ["下方修正", "減配", "特別損失", "業績悪化", "赤字"]

# 米国株の好材料カテゴリ定義(データ収集タスク側が headline/category 付きで収集した
# 好材料ニュースを対象とする。カテゴリごとの想定インパクトは、過去の類似ニュースに対する
# 一般的な株価反応傾向を示す参考値であり、確約・予想ではない)。
US_CATALYST_INFO = {
    "earnings_beat": {
        "weight": 5, "strength": "強い好材料",
        "content": "市場予想(アナリスト予想)を上回る決算(売上・EPSなど)を発表",
        "impact": "+3%〜+10%程度",
        "reason": "実績が事前のアナリスト予想を上回ったことで、業績への評価が上向きに見直されやすいため",
    },
    "guidance_raise": {
        "weight": 4, "strength": "強い好材料",
        "content": "次期以降の業績見通し(ガイダンス)を上方修正",
        "impact": "+3%〜+8%程度",
        "reason": "会社自身が先行きの成長期待を引き上げたことで、将来の増益期待が高まりやすいため",
    },
    "upgrade": {
        "weight": 3, "strength": "やや強い好材料",
        "content": "大手証券・アナリストが目標株価や評価(レーティング)を上方修正",
        "impact": "+1%〜+5%程度",
        "reason": "有力な第三者評価の改善は、他の投資家の見方にも影響を与えやすいため",
    },
    "buyback": {
        "weight": 2, "strength": "やや強い好材料",
        "content": "大規模な自社株買いプログラムを発表",
        "impact": "+1%〜+4%程度",
        "reason": "株式数減少によるEPS改善期待と、経営陣の自信表明として受け止められやすいため",
    },
    "dividend_hike": {
        "weight": 2, "strength": "やや強い好材料",
        "content": "増配を発表",
        "impact": "+1%〜+3%程度",
        "reason": "株主還元強化の姿勢が評価されやすいため",
    },
}


def _catalyst_rank_row(i, code, name, strength_label, content_text, impact_text, reason_text,
                        news_title, news_url, extra_note, outlook_html):
    """好材料ランキング1件分の行HTML。具体的な好材料内容・想定インパクト(参考値)・
    好材料と判断する理由をそれぞれ明記する。"""
    return f"""
        <div class="rank-item">
          <div class="rank-num">{rank_label(i)}</div>
          <div class="rank-body">
            <div class="rank-head">
              <span class="mono">{esc(code)}</span> {esc(name)}
              <span class="score-tag">{esc(strength_label)}</span>
            </div>
            <div class="rank-desc rank-content">📌 具体的な好材料: {esc(content_text)}</div>
            <div class="rank-desc rank-impact">📈 想定インパクト: {esc(impact_text)}<span class="tag">過去の類似ケースの一般的傾向・参考値(保証なし)</span></div>
            <div class="rank-desc rank-reason">💡 なぜ好材料か: {esc(reason_text)}</div>
            <div class="rank-desc rank-news">
              <a href="{esc(news_url) or '#'}" target="_blank" rel="noopener">{esc(news_title)}</a>{esc(extra_note)}
            </div>
            <div class="rank-desc rank-outlook">📊 {outlook_html}</div>
          </div>
        </div>"""


def good_news_ranking_html_jp(tdnet_morning, tdnet_afterclose, technical,
                               empty_msg="本日はTDnet開示に基づく明確な好材料データ(日本株)がありません。"):
    """本日のTDnet開示のうち、上方修正・増配・最高益など「明確な好材料」とみなせる開示のみを対象に、
    内容の強さ(好材料の質)でランキング化したもの。下方修正・減配など弱材料は対象外とし、
    件数や話題性(注目度)ではなく好材料としての質を重視する。
    各順位には「何が」「どれくらいの好材料か」「想定インパクト(参考値)」「なぜ好材料か」
    「直近テクニカル指標に基づく参考コメント」を併記する。株価上昇を確約・予想するものではない。"""
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
            continue  # 弱材料は好材料ランキングの対象外

        weight = 0
        keyword = None
        for k, info in JP_CATALYST_INFO.items():
            if k in combined and info["weight"] > weight:
                weight = info["weight"]
                keyword = k
        if weight == 0:
            continue  # 明確な好材料キーワードが無ければ対象外(単なる話題性では加点しない)

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
        extra = f" ほか{entry['count'] - 1}件" if entry["count"] > 1 else ""
        outlook = _outlook_comment(code, tech_lookup)
        info = JP_CATALYST_INFO.get(entry["keyword"], {})
        rows.append(_catalyst_rank_row(
            i, code, company, info.get("strength", "好材料"),
            info.get("content", title), info.get("impact", "算定不可"),
            info.get("reason", ""), title, url, extra, outlook,
        ))
    return "".join(rows)


def good_news_ranking_html_us(us_good_news,
                               empty_msg="本日は米国株の明確な好材料データがありません(データ取得は今後の更新に対応予定です)。"):
    """データ収集タスクが収集した米国株の好材料ニュース(ticker/company/headline/category/url)を
    対象に、カテゴリの強さでランキング化したもの。日本株と同様に「何が」「どれくらいの好材料か」
    「想定インパクト(参考値)」「なぜ好材料か」を明記する。株価上昇を確約・予想するものではない。
    米国株は日本のTDnetのような統一的な適時開示システムが無いため、テクニカル指標コメントは対象外。"""
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
            continue  # 未知のカテゴリ・好材料に該当しないものは対象外

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
        extra = f" ほか{entry['count'] - 1}件" if entry["count"] > 1 else ""
        info = US_CATALYST_INFO.get(entry["category"], {})
        content_text = headline or info.get("content", "")
        rows.append(_catalyst_rank_row(
            i, ticker, company, info.get("strength", "好材料"),
            content_text, info.get("impact", "算定不可"),
            info.get("reason", ""), headline, url, extra,
            "米国株のためテクニカル指標(移動平均・RSI等)は対象外です。個別の株価情報は各種株価情報サービスでご確認ください。",
        ))
    return "".join(rows)


def growth_candidates_html(items, empty_msg="現時点で好材料開示に基づく成長株候補は見つかりませんでした。"):
    """TDnet「業績予想の修正」開示のうち、上方修正・増配など明確な好材料キーワードを含む開示のみを
    機械的に抽出した「成長株候補」一覧。各候補には実際の開示PDFへの直リンクが付き、
    根拠(決算・好材料)を開示原文で確認できる。将来の株価上昇を保証するものではない。"""
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
          <div class="rank-num">🌱</div>
          <div class="rank-body">
            <div class="rank-head">
              {company}
              <span class="badge bull">{catalyst}</span>
            </div>
            <div class="rank-desc rank-news">
              <a href="{url}" target="_blank" rel="noopener">{title}</a>
            </div>
            <div class="rank-desc">{reason} ・ 開示日時: {asof}</div>
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

/* --- 背景写真: 画質を落とさずopacityのみでゆっくりクロスフェードするスライドショー --- */
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

/* --- ランキング(強気シグナル数 / TDnet好材料) --- */
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

/* --- PC(広い画面): 余白と最大幅を少し広げて読みやすくする --- */
@media (min-width: 1200px) {
  .wrap { max-width: 1240px; }
  body { font-size: 15.5px; }
  .idx-grid { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
  .topbar-inner { max-width: 1240px; }
}

/* --- スマホ(狭い画面): 余白・文字サイズを詰めてタップしやすくする --- */
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

/* ==================== 追加機能: ライトテーマ / お気に入り / 検索・ソート / ミニグラフ / アニメーション ==================== */

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
table[data-sortable] thead th::after { content: "⇕"; margin-left: 5px; font-size: 9px; opacity: 0.35; }
table[data-sortable] thead th[data-dir="asc"]::after { content: "▲"; opacity: 0.9; }
table[data-sortable] thead th[data-dir="desc"]::after { content: "▼"; opacity: 0.9; }

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
"""


JS_SCRIPT = r"""
<script>
(function () {
  "use strict";

  var reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  /* ---------- 背景スライドショー(画質を落とさずopacityのみでゆっくりクロスフェード) ---------- */
  (function () {
    var photos = document.querySelectorAll(".bg-photo-stack .bg-photo");
    var captionEl = document.getElementById("bgCaption");
    function updateCaption(photo) {
      if (!captionEl || !photo) { return; }
      var cap = photo.getAttribute("data-caption") || "";
      captionEl.textContent = "📍 東京・" + (cap || "東京");
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

  /* ---------- テーマ切替(ライト/ダーク) ---------- */
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

  /* ---------- お気に入り(★) ---------- */
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

  /* ---------- テーブル検索 ---------- */
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

  /* ---------- テーブルソート(見出しクリック) ---------- */
  function parseCell(text) {
    var t = text.replace(/[,円%★]/g, "").trim();
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

  /* ---------- スクロール時フェードイン ---------- */
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

  /* ---------- 指標カードの数値カウントアップ ---------- */
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

  /* ---------- 相対更新時刻 ---------- */
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
      if (diffMin < 1) { text = "たった今"; }
      else if (diffMin < 60) { text = "約" + diffMin + "分前"; }
      else if (diffMin < 60 * 24) { text = "約" + Math.round(diffMin / 60) + "時間前"; }
      else { text = "約" + Math.round(diffMin / 1440) + "日前"; }
      el.textContent = "(" + text + ")";
    })(relTimes[rtm]);
  }

  /* ---------- トップへ戻る ---------- */
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

    good_news_rank_html_jp = good_news_ranking_html_jp(
        data.get("tdnet_morning", []), data.get("tdnet_afterclose", []), data.get("technical", [])
    )
    good_news_rank_html_us = good_news_ranking_html_us(
        data.get("us_good_news", [])
    )

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
      <div class="card">
        <h3>TDnet開示 好材料ランキング(日本株 TOP5)</h3>
        <p class="rank-note">
          本日のTDnet開示のうち、上方修正・最高益・増配など<b>明確な好材料のみ</b>を対象に、内容の強さで機械的に順位付けしています
          (下方修正・減配など弱材料の開示は対象外)。各銘柄について、①具体的に何が開示されたか、②過去の類似開示に基づく想定インパクト(参考値)、
          ③好材料と判断する理由、④直近のテクニカル指標に基づく参考コメント、を明記しています。
          <b>想定インパクトは過去の類似ケースの一般的な傾向を示す参考値であり、株価が実際にその通り上昇することを確約・予想するものではありません。</b>
        </p>
        {good_news_rank_html_jp}
      </div>
      <div class="card">
        <h3>好材料ランキング(米国株 TOP5)</h3>
        <p class="rank-note">
          決算上振れ・ガイダンス上方修正・アナリスト評価引き上げなど<b>明確な好材料のみ</b>を対象に、内容の強さで機械的に順位付けしています。
          各銘柄について、①具体的に何が発表されたか、②過去の類似ニュースに基づく想定インパクト(参考値)、③好材料と判断する理由、を明記しています。
          <b>想定インパクトは過去の類似ケースの一般的な傾向を示す参考値であり、株価が実際にその通り上昇することを確約・予想するものではありません。</b>
        </p>
        {good_news_rank_html_us}
      </div>
    </section>"""

    bull_rank_html = bull_ranking_html(data.get("technical", []))

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
      <div class="card">
        <h3>強気シグナル数ランキング</h3>
        <p class="rank-note">
          移動平均線・RSIなど過去データに基づく機械的な「買いシグナル数」の傾向をランキング化したものです。
          <b>あくまで過去データに基づく傾向であり、将来の株価変動を保証するものではありません。</b>
        </p>
        {bull_rank_html}
      </div>
    </section>"""

    growth_html = f"""
    <section id="growth">
      <h2>🌱 成長株ウォッチ(決算・好材料ベース)</h2>
      <p class="section-desc">
        主力ウォッチリストは値位置が高めの銘柄も含むため、別枠として、TDnet「業績予想の修正」開示のうち
        <b>上方修正・増配など明確な好材料キーワードを含む開示のみ</b>を機械的に抽出した候補一覧です。
        各候補には実際の開示PDFへの直リンクを付けており、根拠は開示原文でご確認いただけます。
        <b>投資助言ではなく、将来の株価上昇を保証するものではありません。</b>
      </p>
      <div class="card">
        <h3>好材料開示に基づく成長株候補</h3>
        {growth_candidates_html(data.get("growth_candidates", []))}
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

    bg_url = pick_background_image(generated_at, run_type)
    page_css = CSS.replace("__BG_URL__", bg_url)

    # 背景スライドショー: 現在時刻/朝夜に応じた「本来の写真」を先頭(=最初に表示)にして、
    # 残りの写真をゆっくりクロスフェードで巡回させる。画質は元画像のまま(opacityのみで遷移)。
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
<title>日本株デイトレード情報ダッシュボード</title>
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
      <span class="eyebrow">TOKYO STOCK EXCHANGE ・ DAY TRADE INTELLIGENCE</span>
      <h1>日本株(東証)デイトレード情報ダッシュボード<span class="run-badge">{esc(run_label)}</span></h1>
      <div class="subtitle">最終更新: {esc(generated_at)} (JST)<span class="rel-time" data-generated="{esc(generated_at)}"></span> ・ 毎日 朝6:00 / 夜21:00 に自動更新</div>
    </div>
    <div class="top-controls">
      <nav class="tabs">
        <a href="#morning">🌅 寄り付き前</a>
        <a href="#evening">🌙 引け後</a>
        <a href="#technical">📊 株価診断</a>
        <a href="#growth">🌱 成長株</a>
      </nav>
      <button id="themeToggle" class="theme-toggle" type="button" aria-label="表示テーマを切り替え" title="ライト/ダークテーマ切替">🌗</button>
    </div>
  </div>
</header>
<div class="wrap">
  <div class="disclaimer">
    ⚠️ <b>本サイトは情報提供のみを目的とし、投資助言ではありません。</b> {disclaimer_text}
  </div>
  <label class="fav-filter"><input type="checkbox" id="favFilterToggle"> ★ お気に入りのみ表示(コード欄の★で登録)</label>

  {morning_html}
  {evening_html}
  {technical_html}
  {growth_html}

  <footer>
    <div class="disclaimer">
      ⚠️ 再掲: {disclaimer_text}
    </div>
    {sources_html}
  </footer>
</div>
<div class="bg-spacer" aria-hidden="true">
  <div class="bg-caption" id="bgCaption">📍 東京・{esc(rotation[0][1]) if rotation and rotation[0][1] else "東京"}</div>
</div>
<button id="backToTop" type="button" aria-label="ページ上部へ戻る" title="トップへ戻る">↑</button>
{JS_SCRIPT}
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
