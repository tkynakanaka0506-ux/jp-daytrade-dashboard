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
    ("https://images.unsplash.com/photo-1671247913568-050c0bb925f5?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "表参道イルミネーション"),
    ("https://images.unsplash.com/photo-1771385706304-19ab1fb5fd61?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "浅草・雷門"),
    ("https://images.unsplash.com/photo-1703702238930-237f139e8115?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "神楽坂の路地"),
    ("https://images.unsplash.com/photo-1764418366176-0f273a921fab?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "伏見稲荷大社(京都)"),
    ("https://images.unsplash.com/photo-1711006876033-8baac5dfa718?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "汐留イルミネーション"),
    ("https://images.unsplash.com/photo-1739614537933-11eed8f5d449?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "横浜みなとみらい"),
    ("https://images.unsplash.com/photo-1660292318896-0c684c801e3f?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "六本木ヒルズ展望台"),
    ("https://images.unsplash.com/photo-1764268845521-a115101cdde5?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "池袋"),
    ("https://images.unsplash.com/photo-1493515322954-4fa727e97985?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "上野の裏路地"),
    ("https://images.unsplash.com/photo-1601042879364-f3947d3f9c16?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "有楽町・銀座"),
    ("https://images.unsplash.com/photo-1617869884925-f8f0a51b2374?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "歌舞伎町"),
    ("https://images.unsplash.com/photo-1626846136629-aa437fcb29a8?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "西新宿の高層ビル群"),
    ("https://images.unsplash.com/photo-1734753050499-e766acbe80ce?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "品川・高層ビル街"),
    ("https://images.unsplash.com/photo-1781525981877-ce6d8d80bcf8?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "渋谷センター街"),
    ("https://images.unsplash.com/photo-1617870314635-fc819547ec11?auto=format&fit=crop&w=2400&q=90&sat=35&con=12&vib=22", "新宿・思い出横丁"),
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


# ------------------------------------------------------------------
# 文章(テクニカルコメント・話題の背景・資金フロー・好材料の理由など)中の
# 「客観的に見て明確に良い/悪い/注意すべき」数値・キーワードを、
# 色+背景色+文字サイズで視覚的に強調する。数字だけでは重要度が伝わりにくい
# という要望への対応であり、既存のsignal/RSI等の判定結果をなぞって
# 見た目を強調するだけで、新たな投資判断を追加するものではない。
# ------------------------------------------------------------------
HL_GOOD_STRONG_WORDS = [
    "最高益", "増収増益", "特別配当", "業績上方修正", "上方修正", "増配", "ストップ高", "急騰", "格上げ",
]
HL_GOOD_WORDS = [
    "自己株買い", "株式分割", "上昇", "反発", "好調", "上回る", "上振れ", "買われ", "増加", "買い優勢", "強気",
]
HL_BAD_STRONG_WORDS = [
    "下方修正", "減配", "特別損失", "業績悪化", "赤字", "ストップ安", "急落", "格下げ",
]
HL_BAD_WORDS = [
    "続落", "下落", "悪化", "下回る", "下振れ", "売り優勢", "弱気",
]
HL_WARN_WORDS = ["過熱感", "売られ過ぎ", "買われ過ぎ", "懸念", "リスク", "損切り", "矛盾"]


def _wrap_keywords(s, words, cls):
    if not words:
        return s
    pattern = "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))
    return re.sub(f"({pattern})", lambda m: f'<span class="{cls}">{m.group(1)}</span>', s)


def emphasize(text):
    """コメント・理由等の文章を、重要な数値/キーワードに強調マーカーを付けたHTMLへ変換する。
    引数は未エスケープの生テキストを渡すこと(この関数内でHTMLエスケープする)。"""
    if not text:
        return ""
    s = html_lib.escape(str(text))

    def pct_repl(m):
        sign, num_s = m.group(1), m.group(2)
        try:
            num = float(num_s)
        except ValueError:
            return m.group(0)
        signed = -num if sign == "-" else num
        if signed >= 8:
            cls = "hl-good-strong"
        elif signed >= 3:
            cls = "hl-good"
        elif signed <= -8:
            cls = "hl-bad-strong"
        elif signed <= -3:
            cls = "hl-bad"
        else:
            return m.group(0)
        return f'<span class="{cls}">{m.group(0)}</span>'

    s = re.sub(r"([+\-])(\d+(?:\.\d+)?)\s*%", pct_repl, s)
    s = _wrap_keywords(s, HL_GOOD_STRONG_WORDS, "hl-good-strong")
    s = _wrap_keywords(s, HL_GOOD_WORDS, "hl-good")
    s = _wrap_keywords(s, HL_BAD_STRONG_WORDS, "hl-bad-strong")
    s = _wrap_keywords(s, HL_BAD_WORDS, "hl-bad")
    s = _wrap_keywords(s, HL_WARN_WORDS, "hl-warn")
    return s


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

        # 投資関連分野・注目企業(データにあれば表示。無い場合は何も出さない=旧データとの後方互換)
        sector = esc((it.get("investment_sector") or "").strip())
        companies_raw = it.get("investment_companies") or ""
        if isinstance(companies_raw, list):
            companies = "、".join(esc(str(c)) for c in companies_raw if str(c).strip())
        else:
            companies = esc(str(companies_raw).strip())
        impact_html = ""
        if sector or companies:
            bits = []
            if sector:
                bits.append(f'<span class="impact-sector">関連分野: {sector}</span>')
            if companies:
                bits.append(f'<span class="impact-companies">注目企業: {companies}</span>')
            impact_html = f'<div class="news-impact">{"".join(bits)}</div>'

        # 資金フロー(地政学・世界情勢ニュース→今/これからどの分野にお金が向かっているか。データにあれば表示)
        flow_text = emphasize((it.get("money_flow") or "").strip())
        flow_type = (it.get("money_flow_type") or "").strip().lower()
        flow_html = ""
        if flow_text:
            if flow_type == "expected":
                flow_cls, flow_label = "flow-expected", "見込み"
            else:
                flow_cls, flow_label = "flow-current", "実況"
            flow_html = (
                f'<div class="news-flow {flow_cls}">'
                f'<span class="flow-badge">💰 {flow_label}</span>'
                f'<span class="flow-text">{flow_text}</span></div>'
            )

        rows.append(
            f'<li><a href="{url}" target="_blank" rel="noopener">{title}</a>'
            f'<span class="meta">{meta}</span>'
            f'{impact_html}{flow_html}</li>'
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
        title_raw = it.get("title", "") or ""
        title = esc(title_raw)
        url = esc(it.get("url", "")) or "#"
        tag_raw = it.get("tag", "") or ""
        tag = esc(tag_raw)
        tag_html = f'<span class="tag">{tag}</span>' if tag else ""
        sent_cls, sent_label = disclosure_sentiment(tag_raw, title_raw)
        sent_html = f'<span class="badge {sent_cls} sentiment-badge" title="タイトルのキーワードのみで機械的に判定した参考ラベルです">{sent_label}</span>'
        rows.append(f"""
        <tr>
          <td class="mono">{time_}</td>
          <td class="mono">{fav_btn_html(code)}{code_link(code)}</td>
          <td>{company}</td>
          <td>{sent_html}<a href="{url}" target="_blank" rel="noopener">{title}</a> {tag_html}</td>
        </tr>""")
    return f"""
    {table_tools_html("時刻・コード・会社名・タイトルで検索")}
    <p class="rank-note">💡 <b>ポジティブ/ネガティブ/中立</b>は開示タイトルのキーワード一致による機械的な参考判定です。AIによる詳細分析ではなく、投資助言でもありません。</p>
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
        vol_note = emphasize(it.get("volume_note", ""))
        reason = emphasize(it.get("reason", ""))
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
def supply_demand_cell_html(it):
    """需給・コンセンサス列: 信用倍率・材料出尽くし警戒・踏み上げ期待・みんかぶ参考リンクをまとめる。

    信用倍率(credit_ratio)・踏み上げ期待(squeeze_potential)はMain.java側でJPX公式の
    無料週次データから決定論的に算出。baked_in_warning/baked_in_reasonはnews_analyzer.py側で
    Geminiが「直近5日騰落率」「52週高値からの位置」を確認した結果の定性的な警告
    (数値算出自体はLLMを使わない)。minkabu_urlはスクレイピングではなく手動確認用の外部参考リンク。
    """
    parts = []

    ratio = it.get("credit_ratio")
    if isinstance(ratio, (int, float)):
        parts.append(f'<div class="mono sd-ratio">信用倍率 {ratio:.2f}倍</div>')

    # 出来高変化率(当日出来高 ÷ 直近5日平均出来高)。2倍以上を「出来高急増」として強調する。
    # Main.java の enrichWithPriceStats() が算出済み(無料・キー不要のYahoo Finance chart APIから)。
    vol_ratio = it.get("volume_ratio")
    if it.get("volume_surge"):
        ratio_str = f"({vol_ratio:.1f}倍)" if isinstance(vol_ratio, (int, float)) else ""
        parts.append(f'<span class="tag tag-good">🚀出来高急増{ratio_str}</span>')
    elif isinstance(vol_ratio, (int, float)):
        parts.append(f'<div class="mono sd-ratio">出来高 5日平均比 {vol_ratio:.2f}倍</div>')

    # 窓開け(ギャップ): (当日寄り付き価格 − 前日終値) ÷ 前日終値。±2%以上を強調する。
    gap_pct = it.get("gap_pct")
    if it.get("gap_up"):
        parts.append(f'<span class="tag tag-good">🔺窓開け上放れ {fmt_pct(gap_pct)}</span>')
    elif it.get("gap_down"):
        parts.append(f'<span class="tag tag-warn">🔻窓開け下放れ {fmt_pct(gap_pct)}</span>')

    # セクター(業種)平均比較・逆行高検知。SECTOR_MAPに基づくウォッチリスト内の簡易近似(Main.java側で算出)。
    sector = esc(it.get("sector", ""))
    if it.get("sector_contrarian"):
        sector_avg = it.get("sector_avg_change_pct")
        avg_str = fmt_pct(sector_avg) if isinstance(sector_avg, (int, float)) else "―"
        parts.append(
            f'<span class="tag tag-good" title="業種平均{avg_str}に対して単独で強い上昇(逆行高)">'
            f'💪逆行高({sector})</span>'
        )
    elif sector:
        parts.append(f'<span class="tag tag-info">業種: {sector}</span>')

    # 投資テーマ自動タグ(news_analyzer.py側でGeminiが定性判定。付与されない場合もある)
    theme = esc(it.get("theme", ""))
    if theme:
        note = esc(it.get("theme_trend_note", ""))
        title_attr = f' title="{note}"' if note else ""
        parts.append(f'<span class="tag tag-theme"{title_attr}>🏷 {theme}</span>')

    if it.get("baked_in_warning"):
        reason = esc(it.get("baked_in_reason", ""))
        title_attr = f' title="{reason}"' if reason else ""
        parts.append(f'<span class="tag tag-warn"{title_attr}>⚠️材料出尽くし警戒</span>')

    if it.get("squeeze_potential"):
        parts.append('<span class="tag tag-good">🚀需給良好(踏み上げ期待)</span>')

    code = it.get("code", "")
    minkabu_url = it.get("minkabu_url") or (f"https://minkabu.jp/stock/{code}/analyst_consensus" if code else "")
    if minkabu_url:
        parts.append(
            f'<a class="ext-link-btn" href="{esc(minkabu_url)}" target="_blank" rel="noopener">コンセンサス確認 ↗</a>'
        )

    if not parts:
        return '<span class="empty">―</span>'
    return "".join(parts)


SCORE_AXES = (
    ("catalyst", "材料"),
    ("technical", "テクニカル"),
    ("volume", "需給"),
    ("expectation", "期待値"),
)


def compute_stock_scores(it, growth_by_name):
    """4項目5段階スコアリング(材料・テクニカル・需給・期待値)をLLMを使わずルールベースで算出する。

    既にMain.java(決定論的スクレイピング)とnews_analyzer.py(Gemini定性判定)が算出済みの
    フィールドだけを使い、再現性のある単純なしきい値判定で1〜5点を付ける簡易スコアであり、
    厳密なファンダメンタルズ分析やテクニカル分析の代替ではない。
    """
    g = growth_by_name.get(it.get("name")) if growth_by_name else None

    # ① 材料(catalyst): 好材料の強さ。ダブルシグナル > 単独の好材料開示 > テーマ性のみ > 材料なし。
    if g and g.get("double_signal"):
        catalyst = 5
    elif g:
        catalyst = 4
    elif it.get("theme"):
        catalyst = 3
    elif it.get("baked_in_warning"):
        catalyst = 2
    else:
        catalyst = 1

    # ② テクニカル: 既存の「強気スコア」(買いシグナル数×2−売りシグナル数)をベースに5段階化する。
    counts = parse_signal_counts(it.get("summary", ""))
    if counts:
        bull_score = counts["buy"] * 2 - counts["sell"]
        if bull_score >= 4:
            technical = 5
        elif bull_score >= 2:
            technical = 4
        elif bull_score >= 0:
            technical = 3
        elif bull_score >= -2:
            technical = 2
        else:
            technical = 1
    else:
        technical = 3

    # ③ 需給: 出来高変化率(直近5日平均比)と信用倍率による踏み上げ期待を反映する。
    vol_ratio = it.get("volume_ratio")
    if isinstance(vol_ratio, (int, float)):
        if vol_ratio >= 3.0:
            volume = 5
        elif vol_ratio >= 2.0:
            volume = 4
        elif vol_ratio >= 1.5:
            volume = 3
        elif vol_ratio >= 1.0:
            volume = 2
        else:
            volume = 1
    else:
        volume = 3
    if it.get("squeeze_potential") and volume < 5:
        volume += 1

    # ④ 期待値: 好材料が「まだ織り込まれていないか」の目安。既に高値圏・急騰済みなら減点、
    # 売られ過ぎ(RSI低位)で反発余地があれば加点する(将来の値上がりを保証するものではない)。
    expectation = 3
    if it.get("baked_in_warning"):
        expectation -= 2
    high_dist = it.get("high_52w_dist_pct")
    if isinstance(high_dist, (int, float)) and high_dist <= 3.0:
        expectation -= 1
    ret5d = it.get("ret_5d_pct")
    if isinstance(ret5d, (int, float)) and ret5d >= 15.0:
        expectation -= 1
    rsi = it.get("rsi")
    try:
        rsi_f = float(rsi)
        if rsi_f >= 70:
            expectation -= 1
        elif rsi_f <= 30:
            expectation += 1
    except (TypeError, ValueError):
        pass
    expectation = max(1, min(5, expectation))

    catalyst = max(1, min(5, catalyst))
    technical = max(1, min(5, technical))
    volume = max(1, min(5, volume))

    overall = round((catalyst + technical + volume + expectation) / 4.0, 1)
    return {"catalyst": catalyst, "technical": technical, "volume": volume, "expectation": expectation, "overall": overall}


def score_badge_html(scores):
    """4軸スコアを、軸名の頭文字+ドット(●○)のミニ表示と総合スコアのバッジにまとめる。"""
    pips = []
    for key, label in SCORE_AXES:
        v = scores.get(key, 3)
        dots = "".join("●" if i < v else "○" for i in range(5))
        pips.append(
            f'<div class="score-row"><span class="score-axis">{label}</span>'
            f'<span class="score-dots" title="{label} {v}/5">{dots}</span></div>'
        )
    overall = scores.get("overall", 3.0)
    if overall >= 4.0:
        cls = "score-high"
    elif overall >= 2.5:
        cls = "score-mid"
    else:
        cls = "score-low"
    return (
        f'<div class="score-cell">'
        f'<div class="score-overall {cls}">総合 {overall:.1f}</div>'
        f'{"".join(pips)}'
        f'</div>'
    )


def technical_table(items, empty_msg="テクニカルデータが取得できませんでした。", growth=None):
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    growth_by_name = {g.get("company"): g for g in (growth or []) if g.get("company")}
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
        summary = emphasize(it.get("summary", ""))
        sd_html = supply_demand_cell_html(it)
        scores = compute_stock_scores(it, growth_by_name)
        score_html = score_badge_html(scores)
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
          <td>{sd_html}</td>
          <td>{score_html}</td>
          <td class="reason">{summary}</td>
        </tr>""")
    return f"""
    {table_tools_html()}
    <p class="rank-note">💡 <b>スコア(材料/テクニカル/需給/期待値)</b>は既存データからのルールベース簡易採点(1〜5)です。AIによる判定ではなく、投資助言でもありません。</p>
    <div class="scroll-hint">← 横にスクロールできます</div>
    <div class="table-scroll">
    <table class="technical-table" data-sortable="true">
      <thead><tr><th>コード</th><th>銘柄名</th><th>株価</th><th>前日比</th><th>5日線乖離</th><th>25日線乖離</th><th>RSI(14)</th><th>シグナル</th><th>需給・コンセンサス</th><th>スコア</th><th>コメント</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    </div>"""


def parse_signal_counts(summary):
    """summary文字列から「売りX/中立Y/買いZ」のシグナル内訳を抽出する。見つからなければNone。

    2026-08-02: Main.java側の実際の出力順序(売り→中立→買い、scrapeTechnical()参照)と
    このパターンの順序が一致していなかったため、常にマッチせずbull_ranking_html()や
    4項目スコアリングのテクニカル軸が機能していなかったバグを修正。
    """
    if not summary:
        return None
    m = re.search(r"売り\s*(\d+)\s*/\s*中立\s*(\d+)\s*/\s*買い\s*(\d+)", summary)
    if not m:
        return None
    sell, neutral, buy = (int(x) for x in m.groups())
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
        return emphasize("直近のテクニカルデータは今回取得できませんでした。値動きは各種株価情報サービスでご確認ください。")

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
        parts.append(f"25日線から{ma25}乖離")

    signal = t.get("signal")
    if signal:
        parts.append(f"シグナル判定は「{signal}」")

    if not parts:
        return emphasize("テクニカル指標の参考値が現時点で不足しています。")
    return emphasize("、".join(parts) + "。直近の値動き傾向に基づく機械的な参考情報であり、将来の株価変動を保証するものではありません。")


def _parse_pct_str(s):
    """'+18.5%' のような文字列表現の乖離率を float に変換する。変換できなければ None。"""
    if s is None:
        return None
    m = re.search(r"[+-]?\d+(\.\d+)?", str(s))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _jp_bakedin_warning(code, tech_lookup, rsi_threshold=75.0, dev_threshold=15.0):
    """好材料が出た銘柄について、RSI(14)の過熱・25日線からの上方乖離という
    無料で取得できるテクニカル指標だけから、既に株価に織り込まれ材料出尽くしで
    反落するリスクを機械的に注意喚起する簡易シグナル。決算前後の詳細な騰落率・
    ボリンジャーバンド・市場コンセンサスとの比較までは無料データでは再現できないため、
    あくまで参考情報であり投資助言ではない。"""
    t = tech_lookup.get(str(code).strip())
    if not t:
        return None
    reasons = []
    try:
        rsi = float(t.get("rsi"))
    except (TypeError, ValueError):
        rsi = None
    if rsi is not None and rsi >= rsi_threshold:
        reasons.append(f"RSI(14)が{rsi:.1f}で過熱水準({rsi_threshold:.0f}以上)")
    dev = _parse_pct_str(t.get("ma25_dev"))
    if dev is not None and dev >= dev_threshold:
        reasons.append(f"25日線から{t.get('ma25_dev')}の大幅な上方乖離")
    if not reasons:
        return None
    return ("、".join(reasons) + "。好材料が既に株価に織り込まれ済みで、"
            "利確売り・材料出尽くしによる反落リスクに注意してください。")


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


def disclosure_sentiment(tag, title):
    """TDnet開示1件のタイトル・タグ文字列から、既存のJP_NEGATIVE_KEYWORDS(弱材料)・
    JP_CATALYST_INFO(好材料)のキーワード一致だけで機械的にポジティブ/ネガティブ/中立を判定する。
    AIによる文脈理解ではなく単純なキーワード一致であり、投資助言ではない。
    戻り値: (バッジ用CSSクラス, 表示ラベル)"""
    combined = f"{tag or ''} {title or ''}"
    if any(k in combined for k in JP_NEGATIVE_KEYWORDS):
        return ("bear", "ネガティブ")
    if any(k in combined for k in JP_CATALYST_INFO):
        return ("bull", "ポジティブ")
    return ("neutral", "中立")


def _has_positive_jp_catalyst(tdnet_morning, tdnet_afterclose):
    """当日のTDnet開示(朝・引け後の両方)に、明確な好材料キーワードを含む開示が
    (弱材料を除いて)1件でもあるかどうかを判定する。"""
    items = list(tdnet_morning or []) + list(tdnet_afterclose or [])
    for it in items:
        combined = f"{it.get('tag', '') or ''} {it.get('title', '') or ''}"
        if any(k in combined for k in JP_NEGATIVE_KEYWORDS):
            continue
        if any(k in combined for k in JP_CATALYST_INFO):
            return True
    return False


def _has_negative_jp_news(tdnet_morning, tdnet_afterclose):
    """当日のTDnet開示に、下方修正・減配など明確な弱材料キーワードを含む開示が
    1件でもあるかどうかを判定する。"""
    items = list(tdnet_morning or []) + list(tdnet_afterclose or [])
    for it in items:
        combined = f"{it.get('tag', '') or ''} {it.get('title', '') or ''}"
        if any(k in combined for k in JP_NEGATIVE_KEYWORDS):
            return True
    return False


def _has_positive_us_catalyst(us_good_news):
    """収集済みの米国株好材料ニュースに、既知の好材料カテゴリが1件でもあるかを判定する。"""
    for it in us_good_news or []:
        if (it.get("category") or "") in US_CATALYST_INFO:
            return True
    return False


def market_mood_signal(data):
    """デイトレード初心者向けの直感的な「信号機」判定。
    米国3指数の平均前日比・国内TDnet開示の好材料/弱材料の有無・テクニカル指標の過熱感(RSI>=70)の
    3つだけを組み合わせた、あくまで機械的な簡易判定であり、AIによる高度な分析や投資助言ではない。
    実際の相場は個別要因が複雑に絡むため、最終判断は必ず自身の責任で行うこと。
    戻り値: {"level": "green"|"yellow"|"red", "icon": str, "label": str, "desc": str, "reasons": [str, ...]}"""
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
        reasons.append(f"米国3指数平均 {fmt_pct(us_avg)}")
    if has_good:
        reasons.append("好材料ニュース・開示あり")
    if has_bad_jp:
        reasons.append("国内に弱材料(下方修正等)の開示あり")
    if overheat_flag:
        reasons.append("RSI過熱(70以上)の銘柄が多い")

    if (us_avg is not None and us_avg <= -0.5) or (has_bad_jp and (us_avg is None or us_avg < 0)):
        level = "red"
        icon, label = "🔴", "見送りが無難な地合い"
        desc = "米国株安、または国内に弱材料の開示があります。新規の買いは慎重に検討しましょう。"
    elif has_good and overheat_flag:
        level = "yellow"
        icon, label = "🟡", "材料はあるが過熱感に注意"
        desc = "好材料はありますが、値上がりが大きく短期的な過熱感(RSI高め)があります。焦って追いかけず様子を見るのも一案です。"
    elif us_avg is not None and us_avg >= 0.3 and has_good and not overheat_flag:
        level = "green"
        icon, label = "🟢", "買いを検討しやすい地合い"
        desc = "米国株高・明確な好材料があり、過熱感も目立ちません。比較的仕込みやすい地合いと言えます。"
    else:
        level = "yellow"
        icon, label = "🟡", "様子見が無難な地合い"
        desc = "米国株や好材料の方向感が乏しく、無理に動く必要はありません。"

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
        <div class="mood-caveat">⚠️ 米国株の方向・好材料の有無・過熱感だけを組み合わせた機械的な簡易判定です。投資助言ではなく、最終判断は必ずご自身の責任で行ってください。</div>
      </div>
    </div>"""


def theme_summary_html(data, empty_msg="現時点で投資関連分野・注目企業のデータがありません。"):
    """時間外・引け後の各ニュースに付与された投資関連分野(investment_sector)と
    注目企業(investment_companies)を集約し、「本日の注目テーマ」として一覧化する。
    ニュース見出しから機械的に抽出した参考情報であり、投資助言ではない。"""
    all_news = list(data.get("overnight_news", []) or []) + list(data.get("afterclose_news", []) or [])
    themes = {}
    order = []
    for it in all_news:
        sector = (it.get("investment_sector") or "").strip()
        if not sector:
            continue
        companies_raw = it.get("investment_companies") or []
        if isinstance(companies_raw, str):
            companies_raw = [c.strip() for c in re.split(r"[、,]", companies_raw) if c.strip()]
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
            companies_html = '<span class="theme-company muted">個別銘柄は特定されていません</span>'
        news_titles = "、".join(esc(it.get("title", "")) for it in entry["news"][:2])
        cards.append(f"""
        <div class="theme-card">
          <div class="theme-head"><span class="theme-name">{esc(sector)}</span><span class="tag">関連ニュース{entry['count']}件</span></div>
          <div class="theme-companies">{companies_html}</div>
          <div class="theme-source">きっかけ: {news_titles}</div>
        </div>""")
    return f'<div class="theme-grid">{"".join(cards)}</div>'


def economic_calendar_html(items, empty_msg="経済カレンダーのデータは今回取得できませんでした。"):
    """雇用統計・CPI・日銀会合など、相場変動が起きやすいイベントを重要度(★1〜5)付きで一覧化する。
    重要度はイベントの一般的な市場インパクトの大きさを示す参考値であり、実際の変動を保証しない。"""
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
        stars = "★" * imp + "☆" * (5 - imp)
        note = emphasize(it.get("note", ""))
        note_html = f'<div class="note">{note}</div>' if note else ""
        rows.append(f"""
        <div class="calendar-item">
          <div class="calendar-date mono">{date_}</div>
          <div class="calendar-body">
            <div class="calendar-event">{event}</div>
            <div class="calendar-stars" aria-label="重要度{imp}/5" title="重要度{imp}/5">{stars}</div>
            {note_html}
          </div>
        </div>""")
    return f'<div class="calendar-list">{"".join(rows)}</div>'


def _catalyst_rank_row(i, code, name, strength_label, content_text, impact_text, reason_text,
                        news_title, news_url, extra_note, outlook_html, warning_text=None):
    """好材料ランキング1件分の行HTML。具体的な好材料内容・想定インパクト(参考値)・
    好材料と判断する理由をそれぞれ明記する。warning_textを渡した場合、
    「織り込み済み・材料出尽くし」の可能性がある旨の警告行を追加表示する。"""
    warning_html = (
        f'<div class="rank-desc rank-warn">⚠️ 織り込み済みの可能性あり: {emphasize(warning_text)}</div>'
        if warning_text else ""
    )
    return f"""
        <div class="rank-item">
          <div class="rank-num">{rank_label(i)}</div>
          <div class="rank-body">
            <div class="rank-head">
              <span class="mono">{esc(code)}</span> {esc(name)}
              <span class="score-tag">{esc(strength_label)}</span>
            </div>
            <div class="rank-desc rank-content">📌 具体的な好材料: {emphasize(content_text)}</div>
            <div class="rank-desc rank-impact">📈 想定インパクト: {emphasize(impact_text)}<span class="tag">過去の類似ケースの一般的傾向・参考値(保証なし)</span></div>
            <div class="rank-desc rank-reason">💡 なぜ好材料か: {emphasize(reason_text)}</div>
            <div class="rank-desc rank-news">
              <a href="{esc(news_url) or '#'}" target="_blank" rel="noopener">{esc(news_title)}</a>{esc(extra_note)}
            </div>
            <div class="rank-desc rank-outlook">📊 {outlook_html}</div>
            {warning_html}
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
        warning = _jp_bakedin_warning(code, tech_lookup)
        info = JP_CATALYST_INFO.get(entry["keyword"], {})
        rows.append(_catalyst_rank_row(
            i, code, company, info.get("strength", "好材料"),
            info.get("content", title), info.get("impact", "算定不可"),
            info.get("reason", ""), title, url, extra, outlook,
            warning_text=warning,
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
        warning = _us_bakedin_warning(latest)
        rows.append(_catalyst_rank_row(
            i, ticker, company, info.get("strength", "好材料"),
            content_text, info.get("impact", "算定不可"),
            info.get("reason", ""), headline, url, extra,
            "米国株のためテクニカル指標(移動平均・RSI等)は対象外です。個別の株価情報は各種株価情報サービスでご確認ください。",
            warning_text=warning,
        ))
    return "".join(rows)


def _us_bakedin_warning(item):
    """news_analyzer.py(Gemini)が付与した baked_in_verdict / baked_in_reason を
    もとに、米国株の好材料ランキングに織り込み済み警告文を組み立てる。
    Geminiによる見出しテキストだけからの推定であり、株価チャートを実際に
    参照した判定ではないため、あくまで参考情報。フィールドが無い場合はNone。"""
    verdict = (item.get("baked_in_verdict") or "").strip()
    reason = (item.get("baked_in_reason") or "").strip()
    if verdict in ("過熱・警戒", "材料出尽くし") and reason:
        prefix = "材料出尽くしの可能性が高い" if verdict == "材料出尽くし" else "過熱・警戒"
        return f"[AIによる推定: {prefix}] {reason}"
    return None


def growth_candidates_html(items, empty_msg="現時点で好材料開示に基づく成長株候補は見つかりませんでした。"):
    """TDnet「業績予想の修正」開示のうち、上方修正・増配など明確な好材料キーワードを含む開示のみを
    機械的に抽出した「成長株候補」一覧。各候補には実際の開示PDFへの直リンクが付き、
    根拠(決算・好材料)を開示原文で確認できる。将来の株価上昇を保証するものではない。

    double_signal=trueの場合、同日の決算開示も検知されている「ダブルシグナル」(四半期好決算+通期
    ガイダンス上方修正の同時発表)として、専用バッジを表示する。パナソニックHDのストップ高
    (2026年7月)の事後分析で見られたパターンに基づく、無料データのみでの機械的な近似判定。"""
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        company = esc(it.get("company", ""))
        title = esc(it.get("title", ""))
        url = esc(it.get("url", "")) or "#"
        catalyst = esc(it.get("catalyst", ""))
        reason = emphasize(it.get("reason", ""))
        asof = esc(it.get("asof", ""))
        double_badge = (
            '<span class="badge double">🔥 ダブルシグナル(決算+ガイダンス修正)</span>'
            if it.get("double_signal") else ""
        )
        rows.append(f"""
        <div class="rank-item">
          <div class="rank-num">🌱</div>
          <div class="rank-body">
            <div class="rank-head">
              {company}
              <span class="badge bull">{catalyst}</span>
              {double_badge}
            </div>
            <div class="rank-desc rank-news">
              <a href="{url}" target="_blank" rel="noopener">{title}</a>
            </div>
            <div class="rank-desc">{reason} ・ 開示日時: {asof}</div>
          </div>
        </div>""")
    return "".join(rows)


def pre_earnings_watch_html(items, empty_msg="現時点で該当する先行材料ニュースは見つかりませんでした。"):
    """決算発表を待たず、四半期の途中で出る「増産」「受注」「工場」「生産能力」「データセンター」等の
    断片ニュースをGoogle News RSSの見出しキーワード一致だけで機械的に抽出した一覧。
    LLMによる要約・意味解釈は行っていない単純なキーワードマッチであり、見出しが一致しただけでは
    好材料の大きさ・信頼性は判断できない。必ずリンク先の原文を確認すること。投資助言ではない。"""
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        company = esc(it.get("company", ""))
        code = esc(it.get("code", ""))
        title = esc(it.get("title", ""))
        url = esc(it.get("url", "")) or "#"
        keyword = esc(it.get("keyword", ""))
        asof = esc(it.get("asof", ""))
        rows.append(f"""
        <div class="rank-item">
          <div class="rank-num">🔭</div>
          <div class="rank-body">
            <div class="rank-head">
              {company}({code})
              <span class="badge neutral">{keyword}</span>
            </div>
            <div class="rank-desc rank-news">
              <a href="{url}" target="_blank" rel="noopener">{title}</a>
            </div>
            <div class="rank-desc">Google Newsの見出しキーワード一致 ・ 配信日時: {asof}</div>
          </div>
        </div>""")
    return "".join(rows)


def edinet_holdings_html(items, empty_msg="現時点で該当する大量保有報告書・変更報告書は見つかりませんでした(EDINET_API_KEY未設定の場合は常にこの表示になります)。"):
    """EDINET 大量保有報告書(5%ルール)の簡易チェック(プロトタイプ)。

    Main.java側でEDINET API(要利用登録・APIキー)から直近数日分の大量保有報告書
    (docTypeCode=350)・変更報告書(同351)を取得し、書類概要にウォッチリストの会社名が
    含まれるものだけを単純な文字列一致で抽出している。対象銘柄の証券コードが構造化
    フィールドとして安定して取れないための簡易実装であり、取りこぼし・表記ゆれによる
    ミスマッチが起こり得るプロトタイプ機能。必ずEDINET原文で内容を確認すること。"""
    if not items:
        return f'<p class="empty">{esc(empty_msg)}</p>'
    rows = []
    for it in items:
        name = esc(it.get("name", ""))
        code = esc(it.get("code", ""))
        filer = esc(it.get("filer_name", ""))
        doc_type = esc(it.get("doc_type", ""))
        desc = esc(it.get("doc_description", ""))
        submitted = esc(it.get("submit_datetime", ""))
        rows.append(f"""
        <div class="rank-item">
          <div class="rank-num">📑</div>
          <div class="rank-body">
            <div class="rank-head">
              {fav_btn_html(code)}{code_link(code)} {name}
              <span class="badge neutral">{doc_type}</span>
            </div>
            <div class="rank-desc">提出者: {filer}</div>
            <div class="rank-desc">{desc}</div>
            <div class="rank-desc">提出日時: {submitted}</div>
          </div>
        </div>""")
    return "".join(rows)



# ------------------------------------------------------------------
# 「本日の注目テーマと関連銘柄」(ニュース)と「株価診断」(テクニカル指標)を
# 機械的にクロス参照し、材料とテクニカルの方向感が銘柄ごとに「一致」しているか
# 「矛盾」しているか、あるいはテクニカル指標一覧(主力20銘柄)の対象外で
# 確認できないかを判定する。money_flowの有無・タイトルのキーワード・シグナル
# 文字列・RSIの組み合わせだけによる単純なルールベースの参考情報であり、
# AIによる高度な文脈分析や投資助言ではない。
# ------------------------------------------------------------------
THEME_NEGATIVE_HINT_WORDS = ["関税", "規制", "悪化", "下方修正", "懸念", "急落", "続落", "警戒", "混乱", "不安"]


def _extract_code_from_company(company_str):
    """'日本郵船(9101)' のような文字列から証券コードを取り出す。見つからなければNoneを返す。"""
    m = re.search(r"\((\d{3,5})\)", company_str or "")
    return m.group(1) if m else None


def _news_theme_direction(item):
    """個別ニュース1件が、関連テーマにとって追い風(positive)か逆風(negative)かを、
    money_flow(資金フロー)欄の有無とタイトル中のキーワードだけで機械的に推定する。"""
    if (item.get("money_flow") or "").strip():
        return "positive"
    title = item.get("title", "") or ""
    if any(w in title for w in THEME_NEGATIVE_HINT_WORDS):
        return "negative"
    return "neutral"


def _signal_direction(signal_text):
    s = signal_text or ""
    if "弱気" in s:
        return "bear"
    if "強気" in s:
        return "bull"
    return "neutral"


def _calendar_importance(it):
    try:
        return max(1, min(5, int(it.get("importance", 1))))
    except (TypeError, ValueError):
        return 1


def signal_alignment_rows(data):
    """テーマ別ニュースの関連銘柄ごとに、材料の方向感とテクニカルシグナルを重ね合わせた判定行のリストを返す。"""
    technical = data.get("technical", []) or []
    tech_lookup = _technical_lookup(technical)

    all_news = list(data.get("overnight_news", []) or []) + list(data.get("afterclose_news", []) or [])
    themes = {}
    order = []
    for it in all_news:
        sector = (it.get("investment_sector") or "").strip()
        if not sector:
            continue
        companies_raw = it.get("investment_companies") or []
        if isinstance(companies_raw, str):
            companies_raw = [c.strip() for c in re.split(r"[、,]", companies_raw) if c.strip()]
        entry = themes.setdefault(sector, {"companies": [], "directions": []})
        if sector not in order:
            order.append(sector)
        entry["directions"].append(_news_theme_direction(it))
        for c in companies_raw:
            c = str(c).strip()
            if c and c not in entry["companies"]:
                entry["companies"].append(c)

    rows = []
    for sector in order:
        entry = themes[sector]
        pos = entry["directions"].count("positive")
        neg = entry["directions"].count("negative")
        theme_dir = "positive" if pos > neg else ("negative" if neg > pos else "neutral")

        for company in entry["companies"]:
            code = _extract_code_from_company(company)
            fallback_name = re.sub(r"\(\d{3,5}\)", "", company).strip() or company

            if not code or code not in tech_lookup:
                rows.append({
                    "sector": sector, "theme_dir": theme_dir, "code": code, "name": fallback_name,
                    "signal": None, "rsi": None, "match": "unknown",
                })
                continue

            t = tech_lookup[code]
            sig_dir = _signal_direction(t.get("signal"))
            try:
                rsi = float(t.get("rsi"))
            except (TypeError, ValueError):
                rsi = None
            overheat = rsi is not None and rsi >= 70

            if theme_dir == "positive":
                if overheat:
                    match = "conflict_overheat"
                elif sig_dir == "bull":
                    match = "align_bull"
                elif sig_dir == "bear":
                    match = "conflict"
                else:
                    match = "theme_only"
            elif theme_dir == "negative":
                if sig_dir == "bear":
                    match = "align_bear"
                elif sig_dir == "bull":
                    match = "conflict"
                else:
                    match = "theme_only_negative"
            else:
                match = "neutral"

            rows.append({
                "sector": sector, "theme_dir": theme_dir, "code": code,
                "name": t.get("name") or fallback_name,
                "signal": t.get("signal"), "rsi": rsi, "overheat": overheat,
                "change_pct": t.get("change_pct"), "match": match,
            })
    return rows


def _alignment_badge(match):
    if match == "align_bull":
        return '<span class="badge bull">一致(強気材料×強気シグナル)</span>'
    if match == "align_bear":
        return '<span class="badge bear">一致(弱材料×弱気シグナル)</span>'
    if match == "conflict":
        return '<span class="tag tag-warn">矛盾(材料とテクニカルが逆方向)</span>'
    if match == "conflict_overheat":
        return '<span class="tag tag-warn">好材料はあるが過熱感に注意</span>'
    labels = {
        "theme_only": "材料優勢・テクニカルは中立",
        "theme_only_negative": "弱材料・テクニカルは中立",
        "neutral": "材料の方向感が乏しい",
        "unknown": "テクニカル指標一覧の対象外(未確認)",
    }
    return f'<span class="badge neutral">{esc(labels.get(match, "―"))}</span>'


def _alignment_row_text(row):
    sector = row["sector"]
    name = row["name"]
    signal = row.get("signal")
    rsi = row.get("rsi")
    match = row["match"]

    if match == "align_bull":
        return (f"{sector}に関する報道は資金流入が期待される追い風材料で、{name}のテクニカルシグナルも"
                f"「{signal}」と同じ強気方向を示しています。材料とテクニカルの両方が同じ方向を向いている参考ケースです。")
    if match == "align_bear":
        return (f"{sector}に関する報道は逆風材料ですが、{name}のテクニカルシグナルも「{signal}」で"
                f"同じ弱気方向を示しており、材料とテクニカルが一致しています。")
    if match == "conflict":
        if row["theme_dir"] == "positive":
            return (f"{sector}の報道は追い風材料ですが、{name}のテクニカルシグナルは「{signal}」で"
                    f"むしろ弱気方向です。材料とテクニカルの方向が矛盾しており、判断が難しい組み合わせです。")
        return (f"{sector}の報道は逆風材料ですが、{name}のテクニカルシグナルは「{signal}」で強気方向を"
                f"示しています。材料とテクニカルの方向が矛盾しています。")
    if match == "conflict_overheat":
        rsi_txt = f"{rsi:.1f}" if isinstance(rsi, (int, float)) else "70以上"
        return (f"{sector}には追い風材料が出ていますが、{name}のRSI(14)は{rsi_txt}で既に過熱感(70以上)の"
                f"水準にあります。好材料が出た後に短期的な過熱で反落するケースもあるため、飛びつきには注意が必要です。")
    if match == "theme_only":
        return f"{sector}には追い風材料がありますが、{name}のテクニカルシグナルは「{signal}」で中立です。まだ明確な方向感は出ていません。"
    if match == "theme_only_negative":
        return f"{sector}には逆風材料がありますが、{name}のテクニカルシグナルは「{signal}」で中立です。"
    if match == "neutral":
        return f"{sector}の報道は方向感が乏しく、{name}のテクニカルシグナルは「{signal}」です。材料面での裏付けは弱い状況です。"
    sector_label = sector if (sector.endswith("関連") or sector.endswith("株")) else f"{sector}関連"
    return f"{name}({sector_label})は、テクニカル指標一覧(主力20銘柄)の対象外のためテクニカル面での確認ができていません。個別に株価情報サービスでご確認ください。"


def signal_alignment_html(data):
    """
    「本日の注目テーマと関連銘柄」×「株価診断(テクニカル指標)」を機械的にクロス参照した分析セクションを
    ①端的な結論、②銘柄ごとの一致点・矛盾点の詳細、③投資初心者向けの一般的な対応の考え方、
    の3部構成でHTML化する。AIによる高度な分析や投資助言ではなく、money_flowの有無・
    タイトルのキーワード・シグナル文字列・RSIだけを組み合わせた単純なルールベースの参考情報。
    """
    rows = signal_alignment_rows(data)
    mood = market_mood_signal(data)
    calendar = data.get("economic_calendar", []) or []
    has_big_event = any(_calendar_importance(it) >= 4 for it in calendar)

    align_rows = [r for r in rows if r["match"] in ("align_bull", "align_bear")]
    conflict_rows = [r for r in rows if r["match"] in ("conflict", "conflict_overheat")]
    unclear_rows = [r for r in rows if r["match"] in ("theme_only", "theme_only_negative", "neutral", "unknown")]

    # --- ① 結論(端的なまとめ) ---
    if conflict_rows and not align_rows:
        headline = ("現時点では、ニュースの材料とテクニカル指標がきれいに一致する銘柄は見当たりません。"
                    "むしろ矛盾や過熱感が出ている銘柄が目立ち、新規で追いかけるより様子見が無難な状況です。")
    elif align_rows and not conflict_rows:
        headline = "一部の銘柄でニュースの材料とテクニカル指標の方向感が一致していますが、対象件数は限られており、過信は禁物です。"
    elif align_rows and conflict_rows:
        headline = "銘柄によって材料とテクニカルが一致するものと矛盾するものが混在しており、市場全体を一括りに強気・弱気と言える状況ではありません。"
    else:
        headline = "材料とテクニカル指標を重ね合わせても明確な方向感は出ておらず、今日時点では判断材料そのものが不足しています。"

    if has_big_event:
        headline += ("また今週は重要度の高い経済イベント(FOMC・日銀会合など)を控えており、"
                     "結果発表前後は相場が大きく振れやすい点にも注意してください。")

    tags = []
    if align_rows:
        tags.append(f'<span class="tag">一致 {len(align_rows)}件</span>')
    if conflict_rows:
        tags.append(f'<span class="tag tag-warn">矛盾・過熱感 {len(conflict_rows)}件</span>')
    if unclear_rows:
        tags.append(f'<span class="tag">判断材料不足 {len(unclear_rows)}件</span>')

    conclusion_html = f"""
    <div class="card alignment-conclusion mood-{mood['level']}">
      <h3>📝 結論(まとめ)</h3>
      <p class="conclusion-text">{emphasize(headline)}</p>
      <div class="mood-reasons">{''.join(tags)}</div>
    </div>"""

    # --- ② 詳細 ---
    def _rows_html(rs):
        items = []
        for i, r in enumerate(rs):
            code_html = f'{fav_btn_html(r["code"])}{code_link(r["code"])} ' if r.get("code") else ""
            chg = r.get("change_pct")
            chg_html = f'<span class="mono {pct_class(chg)}">{fmt_pct(chg)}</span>' if chg is not None else ""
            items.append(f"""
            <div class="rank-item">
              <div class="rank-num">{i + 1}</div>
              <div class="rank-body">
                <div class="rank-head">
                  <span class="tag">{esc(r['sector'])}</span>
                  {code_html}{esc(r['name'])} {chg_html}
                  {_alignment_badge(r['match'])}
                </div>
                <div class="rank-desc">{emphasize(_alignment_row_text(r))}</div>
              </div>
            </div>""")
        return "".join(items)

    detail_sections = []
    if align_rows:
        detail_sections.append(f'<h4 class="align-subhead">✅ 材料とテクニカルが一致している銘柄</h4>{_rows_html(align_rows)}')
    if conflict_rows:
        detail_sections.append(f'<h4 class="align-subhead">⚠️ 矛盾・過熱感が出ている銘柄</h4>{_rows_html(conflict_rows)}')
    if unclear_rows:
        detail_sections.append(f'<h4 class="align-subhead">❔ 材料はあるがテクニカル未確認・方向感が乏しい銘柄</h4>{_rows_html(unclear_rows)}')
    if not detail_sections:
        detail_sections.append('<p class="empty">本日は「注目テーマと関連銘柄」に該当するデータがなく、分析対象がありませんでした。</p>')

    detail_html = f"""
    <div class="card">
      <h3>🔎 詳細: 銘柄ごとの一致点・矛盾点</h3>
      <p class="rank-note">
        上の「本日の注目テーマと関連銘柄」に登場する各銘柄について、ニュースの資金フロー有無・キーワードから
        推定した材料の方向感と、テクニカル指標(株価診断)のシグナル・RSIを機械的に重ね合わせています。
        <b>AIによる高度な文脈分析ではなく単純なルールベースの参考情報であり、投資助言ではありません。</b>
      </p>
      {''.join(detail_sections)}
    </div>"""

    # --- ③ 初心者向け対応 ---
    tips = [
        "材料とテクニカルが一致している銘柄は、少なくとも情報同士が矛盾していない点で参考にしやすい一方、"
        "対象件数が少ない・データがやや古いケースもあるため、鵜呑みにせず自分でも最新のチャートを確認しましょう。",
        "材料とテクニカルが矛盾している、またはRSIが既に70以上で過熱感が出ている銘柄は、初心者ほど今から"
        "追いかけるのは避け、いったん様子を見るのが無難です。",
        "既にストップ高・急騰している銘柄を当日中に追加で買うのは初心者にはリスクが高い行為です。"
        "値動きが落ち着くのを待つか、見送るのも十分な選択肢です。",
    ]
    if has_big_event:
        tips.append(
            "今週はFOMCや日銀会合など相場が大きく動きやすいイベントを控えています。結果が出るまでは新規の"
            "大きなポジションを避け、いつもより小さい金額で試すか、いったん見送るのも有効な考え方です。"
        )
    tips.append(
        "どの銘柄を選ぶ場合でも、買う前に損切りラインを決めておく、1つの銘柄に資金を集中させず失っても"
        "生活に影響しない金額で試す、このページの情報だけで判断せず取引直前に最新の株価・ニュースを自分でも"
        "確認する、という3点は徹底しましょう。"
    )
    tips_html = "".join(f"<li>{emphasize(t)}</li>" for t in tips)

    beginner_html = f"""
    <div class="card beginner-card">
      <h3>🔰 初心者向け: 今後どう対応すればいいか</h3>
      <ul class="beginner-tips">{tips_html}</ul>
      <p class="mood-caveat">⚠️ 上記は一般的なリスク管理の考え方を示す参考情報であり、個別の投資助言ではありません。投資に関する最終判断・結果の責任は、必ずご自身で負ってください。</p>
    </div>"""

    return conclusion_html + detail_html + beginner_html



CSS = """
:root {
  --bg-deep: #000000; --bg-mid: #07060a; --bg-soft: #0a0908;
  --panel: linear-gradient(155deg, rgba(20,17,10,0.96), rgba(8,7,5,0.97));
  --panel2: rgba(255,255,255,0.08);
  --border: rgba(212,175,55,0.22); --border-soft: rgba(255,255,255,0.06);
  --text: #f7f4ec; --muted: #d3cfc2;
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
  font-size: 11px; color: var(--text); background: rgba(0,0,0,0.62);
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
  border: 1px solid var(--accent-line); color: var(--text);
  border-radius: var(--radius-sm); padding: 14px 16px; font-size: 13px; line-height: 1.7; margin: 16px 20px;
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
.disclaimer b { color: var(--accent-bright); }
nav.tabs {
  display: flex; gap: 10px; flex-wrap: wrap;
}
nav.tabs a {
  color: var(--text); text-decoration: none; font-size: 12px; letter-spacing: 0.8px;
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
  font-weight: 600; letter-spacing: 0.5px; color: var(--text);
  background: rgba(10,8,5,0.75); border-radius: 0 8px 8px 0; width: fit-content;
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
.section-desc {
  color: var(--muted); font-size: 12.5px; line-height: 1.6; margin: 6px 0 14px; padding: 5px 10px;
  background: rgba(10,8,5,0.68); border-radius: 8px; width: fit-content;
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
  font-size: 12px; margin: 0 0 12px; color: var(--text); font-weight: 600;
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
.idx-value { font-size: 18px; font-weight: 700; margin-top: 3px; letter-spacing: 0.3px; color: var(--text); }
.conclusion-section { margin-bottom: 22px; }
.conclusion-disclaimer {
  font-size: 12.5px; line-height: 1.7; color: var(--text); margin: 4px 0 14px; padding: 10px 12px;
  background: rgba(212,175,55,0.10); border: 1px solid var(--accent-line); border-radius: var(--radius-sm);
}
.pick-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.pick-card {
  background: var(--panel2); border: 1px solid var(--border-soft); border-top: 2px solid var(--accent);
  border-radius: var(--radius-sm); padding: 14px 16px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}
.pick-rank { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: var(--accent-bright); text-transform: uppercase; }
.pick-name { font-size: 16px; font-weight: 700; margin: 4px 0 2px; color: var(--text); }
.pick-code { font-weight: 400; color: var(--muted); font-size: 12.5px; }
.pick-score { font-size: 13px; font-weight: 600; color: var(--accent-bright); margin-bottom: 8px; }
.pick-summary { font-size: 12.5px; line-height: 1.6; color: var(--text); }
.pick-empty { font-size: 13px; color: var(--muted); }
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
  border: 1px solid var(--border-soft); color: var(--text); background: rgba(212,175,55,0.14);
  line-height: 1.5;
}
.news-impact .impact-companies { color: var(--text); background: rgba(255,255,255,0.09); }
.news-flow {
  display: flex; align-items: flex-start; gap: 7px; margin-top: 5px; padding: 5px 9px;
  border-radius: 8px; font-size: 12px; line-height: 1.55;
}
.news-flow .flow-badge {
  flex-shrink: 0; font-weight: 700; padding: 1px 7px; border-radius: 8px;
  font-size: 10.5px; letter-spacing: 0.2px; white-space: nowrap;
}
.news-flow .flow-text { color: var(--text); }
.news-flow.flow-current { background: rgba(255,107,122,0.08); border: 1px solid rgba(255,107,122,0.25); }
.news-flow.flow-current .flow-badge { background: rgba(255,107,122,0.22); color: var(--bull); }
.news-flow.flow-expected { background: rgba(212,175,55,0.08); border: 1px solid rgba(212,175,55,0.25); }
.news-flow.flow-expected .flow-badge { background: rgba(212,175,55,0.22); color: var(--accent-bright); }
.scroll-hint { display: none; color: var(--muted); font-size: 11px; margin: 0 0 4px; }
.table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; border-radius: 10px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
.tdnet-table { min-width: 560px; }
.movers-table { min-width: 680px; }
.technical-table { min-width: 820px; }
th, td { text-align: left; padding: 8px 8px; border-bottom: 1px solid var(--border-soft); }
th {
  color: var(--text); font-weight: 600; font-size: 11px; white-space: nowrap;
  letter-spacing: 0.8px; text-transform: uppercase; border-bottom: 1px solid var(--accent-line);
}
td.mono { font-family: "SF Mono", Menlo, monospace; white-space: nowrap; }
td.reason { color: var(--muted); }
tbody tr:nth-child(even) { background: rgba(212,175,55,0.02); }
tbody tr:hover { background: rgba(212,175,55,0.08); }
.badge { padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; letter-spacing: 0.3px; }
.badge.bull { background: linear-gradient(120deg, rgba(255,107,122,0.2), rgba(255,107,122,0.08)); color: var(--bull); border: 1px solid rgba(255,107,122,0.3); }
.badge.bear { background: linear-gradient(120deg, rgba(53,217,180,0.2), rgba(53,217,180,0.08)); color: var(--bear); border: 1px solid rgba(53,217,180,0.3); }
.badge.neutral { background: rgba(212,175,55,0.16); color: var(--muted); border: 1px solid var(--border-soft); }
.badge.double { background: linear-gradient(120deg, rgba(212,175,55,0.3), rgba(212,175,55,0.1)); color: var(--accent-bright); border: 1px solid rgba(212,175,55,0.5); }
.tag { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: rgba(255,255,255,0.1); color: var(--muted); margin-left: 4px; display: inline-block; margin-top: 2px; }
.tag-warn { background: rgba(255,184,77,0.18); color: var(--warn); }
.tag-good { background: rgba(255,107,122,0.16); color: var(--bull); }
.tag-info { background: rgba(255,255,255,0.12); color: var(--text); }
.tag-theme { background: rgba(212,175,55,0.22); color: var(--accent-bright); }
.empty { color: var(--muted); font-size: 13px; }

/* --- 4項目5段階スコアリング(材料・テクニカル・需給・期待値) --- */
.score-cell { display: flex; flex-direction: column; gap: 2px; min-width: 120px; }
.score-overall {
  font-size: 12px; font-weight: 700; padding: 1px 8px; border-radius: 10px;
  display: inline-block; margin-bottom: 2px; width: fit-content;
}
.score-overall.score-high { background: rgba(255,107,122,0.2); color: var(--bull); }
.score-overall.score-mid { background: rgba(212,175,55,0.2); color: var(--accent-bright); }
.score-overall.score-low { background: rgba(53,217,180,0.16); color: var(--bear); }
.score-row { display: flex; align-items: center; gap: 6px; font-size: 10px; color: var(--muted); white-space: nowrap; }
.score-axis { width: 52px; flex-shrink: 0; }
.score-dots { letter-spacing: 1px; color: var(--accent-bright); }

/* --- 需給・コンセンサス列(信用倍率・材料出尽くし警戒・みんかぶ参考リンク) --- */
.sd-ratio { font-size: 11px; color: var(--muted); margin-bottom: 2px; }
.ext-link-btn {
  display: inline-block; font-size: 10px; padding: 2px 8px; margin-top: 2px;
  border-radius: 10px; border: 1px solid var(--accent-line); color: var(--accent-bright);
  text-decoration: none; white-space: nowrap;
}
.ext-link-btn:hover { background: rgba(212,175,55,0.12); }

/* --- 文章中の重要な数値・キーワードの強調マーカー --- */
.hl-good { color: var(--bull); background: rgba(255,107,122,0.16); padding: 1px 5px; border-radius: 4px; font-weight: 700; }
.hl-good-strong { color: #1a0507; background: linear-gradient(120deg, var(--bull), var(--accent-bright)); padding: 2px 8px; border-radius: 5px; font-weight: 800; font-size: 1.14em; box-shadow: 0 0 0 1px rgba(255,107,122,0.5) inset; }
.hl-bad { color: var(--bear); background: rgba(53,217,180,0.14); padding: 1px 5px; border-radius: 4px; font-weight: 700; }
.hl-bad-strong { color: #04211b; background: linear-gradient(120deg, var(--bear), #8de9d2); padding: 2px 8px; border-radius: 5px; font-weight: 800; font-size: 1.14em; box-shadow: 0 0 0 1px rgba(53,217,180,0.5) inset; }
.hl-warn { color: var(--warn); background: rgba(255,184,77,0.22); padding: 1px 5px; border-radius: 4px; font-weight: 700; }
.sentiment-badge { margin-right: 6px; vertical-align: middle; cursor: help; }

/* --- 市場ムード信号機 --- */
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

/* --- 材料×テクニカル一致/矛盾分析 --- */
.alignment-conclusion.mood-green { border-color: rgba(63,196,116,0.45); box-shadow: var(--shadow), 0 0 20px rgba(63,196,116,0.12); }
.alignment-conclusion.mood-yellow { border-color: rgba(255,184,77,0.45); box-shadow: var(--shadow), 0 0 20px rgba(255,184,77,0.12); }
.alignment-conclusion.mood-red { border-color: rgba(255,90,90,0.45); box-shadow: var(--shadow), 0 0 20px rgba(255,90,90,0.12); }
.conclusion-text { font-size: 14.5px; line-height: 1.75; color: var(--text); margin: 0; }
.align-subhead {
  font-size: 12px; color: var(--text); font-weight: 700; letter-spacing: 0.4px;
  margin: 16px 0 6px; padding-top: 10px; border-top: 1px dashed var(--border-soft);
}
.card h4.align-subhead:first-child { margin-top: 0; padding-top: 0; border-top: none; }
.beginner-card { background: rgba(0,0,0,0.55); backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px); }
.beginner-tips { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 8px; }
.beginner-tips li { font-size: 13px; line-height: 1.7; color: var(--text); }

/* --- 経済カレンダー --- */
.calendar-list { display: flex; flex-direction: column; gap: 2px; }
.calendar-item { display: flex; gap: 12px; align-items: flex-start; padding: 8px 0; border-bottom: 1px solid var(--border-soft); }
.calendar-item:last-child { border-bottom: none; }
.calendar-date { width: 76px; flex-shrink: 0; font-size: 12px; color: var(--muted); padding-top: 1px; }
.calendar-body { flex: 1; min-width: 0; }
.calendar-event { font-size: 13.5px; color: var(--text); font-weight: 600; }
.calendar-stars { font-size: 13px; color: var(--accent-bright); letter-spacing: 1px; margin-top: 2px; }

/* --- 本日の注目テーマ --- */
.theme-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.theme-card {
  background: var(--panel2); border: 1px solid var(--border-soft); border-radius: var(--radius-sm);
  padding: 10px 12px;
}
.theme-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 13.5px; font-weight: 600; color: var(--text); flex-wrap: wrap; }
.theme-name { color: var(--text); font-weight: 700; }
.theme-companies { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.theme-company {
  font-size: 11px; padding: 2px 8px; border-radius: 10px; border: 1px solid var(--border-soft);
  background: rgba(255,255,255,0.1); color: var(--text);
}
.theme-company.muted { color: var(--muted); }
.theme-source { font-size: 11px; color: var(--muted); margin-top: 6px; }

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
.rank-impact { color: var(--text); font-weight: 600; }
.rank-impact .tag { margin-left: 6px; }
.rank-reason { opacity: 0.9; }
.rank-note { font-size: 11px; color: var(--muted); margin: 0 0 10px; }
.rank-warn { color: var(--warn); font-weight: 600; opacity: 1; background: rgba(255,184,77,0.1); border-left: 2px solid var(--warn); padding: 4px 8px; border-radius: 4px; }
.score-tag {
  font-size: 10.5px; padding: 2px 8px; border-radius: 10px;
  background: rgba(212,175,55,0.2); color: var(--accent-bright); border: 1px solid var(--border);
  white-space: nowrap;
}

footer {
  margin: 40px 20px 10px; color: var(--muted); font-size: 11.5px; line-height: 1.7;
  border-top: 1px solid var(--accent-line);
  background: rgba(10,8,5,0.72); border-radius: var(--radius-sm);
  padding: 16px 18px; border: 1px solid var(--border);
  backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
}
footer .disclaimer { margin: 0 0 12px; }
.sources { font-size: 11px; color: var(--muted); }
.run-badge {
  display:inline-block; font-size:11px; padding:2px 10px; border-radius:10px;
  background: rgba(0,0,0,0.62); border:1px solid var(--accent-line); color: var(--accent-bright); margin-left:8px;
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
  width: 100%; max-width: 280px; background: rgba(255,255,255,0.1); color: var(--text);
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


def conclusion_first_html(data):
    """結論ファースト: compute_stock_scores()の総合スコア上位2〜3銘柄を、根拠つきで先頭に表示する。

    既存の4項目スコアリング(compute_stock_scores)をそのまま再利用し、新たな判定ロジックは追加しない。
    あくまでルールベースの機械的な順位付けであり、投資助言ではない。
    """
    items = data.get("technical", []) or []
    growth = data.get("growth_candidates", []) or []
    growth_by_name = {g.get("company"): g for g in growth if g.get("company")}

    ranked = []
    for it in items:
        try:
            scores = compute_stock_scores(it, growth_by_name)
        except Exception:
            continue
        ranked.append((it, scores))
    ranked.sort(key=lambda pair: pair[1].get("overall", 0), reverse=True)
    top = [pair for pair in ranked if pair[1].get("overall", 0) >= 3.0][:3]
    if not top:
        top = ranked[:3]

    if not top:
        picks_html = '<p class="pick-empty">現時点でスコア算出可能な銘柄がありません。</p>'
    else:
        cards = []
        for i, (it, scores) in enumerate(top):
            summary = (it.get("summary") or "").strip()
            cards.append(f"""
                <div class="pick-card">
                  <div class="pick-rank">{esc(i + 1)}位</div>
                  <div class="pick-name">{esc(it.get("name", "―"))} <span class="pick-code">({esc(it.get("code", "―"))})</span></div>
                  <div class="pick-score">総合スコア {esc(scores.get("overall", "―"))} / 5.0
                    (材料{esc(scores.get("catalyst", "―"))}・テクニカル{esc(scores.get("technical", "―"))}・需給{esc(scores.get("volume", "―"))}・期待値{esc(scores.get("expectation", "―"))})</div>
                  <div class="pick-summary">{esc(summary) if summary else "―"}</div>
                </div>""")
        picks_html = "".join(cards)

    return f"""
            <section id="conclusion" class="conclusion-section">
              <h2>🎯 結論ファースト:現時点のスコア上位銘柄</h2>
              <p class="conclusion-disclaimer">
                <b>本セクションは「株価診断(テクニカル指標)」で算出済みの4項目スコア(材料・テクニカル・需給・期待値)を
                機械的に集計し、総合スコアが高い順に最大3銘柄を表示しているだけの参考情報です。
                AIによる推奨や将来の値上がりを保証するものではありません。投資に関する最終判断は、
                必ずご自身の責任で行ってください。</b>
              </p>
              <div class="card">
                <div class="pick-cards">{picks_html}</div>
              </div>
            </section>"""


def build_html(data: dict) -> str:
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    run_type = data.get("run_type", "")
    run_label = {"morning": "朝(寄り付き前)更新", "evening": "夜(引け後)更新"}.get(run_type, run_type)

    us = data.get("us_market", {})
    fx = data.get("fx", {})
    fut = data.get("nikkei_futures", {})

    idx_cards = ""
    for key, label in [("sp500", "S&P500"), ("dow", "NYダウ"), ("nasdaq", "ナスダック総合"), ("sox", "SOX指数(半導体)")]:
        d = us.get(key, {})
        idx_cards += section_index_row(label, d.get("value", "―"), d.get("change_pct"), d.get("asof"))
    idx_cards += section_index_row("USD/JPY", fx.get("value", "―"), fx.get("change_pct"), fx.get("asof"))
    idx_cards += section_index_row("日経225先物(CME/大阪)", fut.get("value", "―"), fut.get("change_pct"), fut.get("asof"))
    idx_cards += section_index_row("日経平均(現物・前回終値)", data.get("nikkei225", {}).get("value", "―"),
                                     data.get("nikkei225", {}).get("change_pct"), data.get("nikkei225", {}).get("asof"))

    conclusion_html = conclusion_first_html(data)
    mood_html = market_mood_html(data)
    theme_html = theme_summary_html(data)
    calendar_html = economic_calendar_html(data.get("economic_calendar", []))

    morning_html = f"""
    <section id="morning">
      <h2>🌅 寄り付き前セクション</h2>
      <p class="section-desc">前日の米国市場・為替・時間外ニュース・TDnet早朝までの開示・話題株をまとめています。当日の仕込み銘柄検討の参考情報です。</p>
      <div class="card">
        <h3>米国市場・為替・日経先物</h3>
        <div class="idx-grid">{idx_cards}</div>
      </div>
      <div class="card">
        <h3>📅 経済カレンダー(重要度)</h3>
        <p class="section-desc">雇用統計・CPI・日銀会合など、相場が動きやすいイベントを重要度(★)で示しています。<b>実際の相場変動を保証するものではありません。</b></p>
        {calendar_html}
      </div>
      <div class="card">
        <h3>🎯 本日の注目テーマと関連銘柄</h3>
        <p class="section-desc">ニュースの投資関連分野・注目企業タグを集約した参考情報です。<b>投資助言ではなく、実際に株価が動くことを保証するものではありません。</b></p>
        {theme_html}
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
          RSI(14)が75以上、または25日線から15%以上上方乖離している銘柄には
          「⚠️ 織り込み済みの可能性あり」の警告を表示します(好材料が既に株価に反映され、材料出尽くしで
          反落するリスクへの機械的な注意喚起であり、決算内容そのものの良し悪しを判定するものではありません)。
        </p>
        {good_news_rank_html_jp}
      </div>
      <div class="card">
        <h3>好材料ランキング(米国株 TOP5)</h3>
        <p class="rank-note">
          決算上振れ・ガイダンス上方修正・アナリスト評価引き上げなど<b>明確な好材料のみ</b>を対象に、内容の強さで機械的に順位付けしています。
          各銘柄について、①具体的に何が発表されたか、②過去の類似ニュースに基づく想定インパクト(参考値)、③好材料と判断する理由、を明記しています。
          <b>想定インパクトは過去の類似ケースの一般的な傾向を示す参考値であり、株価が実際にその通り上昇することを確約・予想するものではありません。</b>
          見出しの内容からAI(Gemini)が「既に株価に織り込まれている可能性」を推定できた場合のみ、
          「⚠️ 織り込み済みの可能性あり」の警告を表示します(見出しテキストのみからの推定であり、
          実際のチャートを参照した判定ではないため、必ず自身でも株価を確認してください)。
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
        {technical_table(data.get("technical", []), growth=data.get("growth_candidates", []))}
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

    alignment_body_html = signal_alignment_html(data)
    alignment_html = f"""
    <section id="alignment">
      <h2>🧭 材料×テクニカル 一致点・矛盾点分析</h2>
      <p class="section-desc">
        「本日の注目テーマと関連銘柄」のニュースと「株価診断(テクニカル指標)」を機械的にクロス参照し、
        材料とテクニカルが同じ方向を示しているか、逆方向で矛盾しているかを銘柄ごとに整理した参考情報です。
        <b>AIによる高度な分析ではなく単純なルールベースの判定であり、投資助言ではありません。</b>
      </p>
      {alignment_body_html}
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

    pre_earnings_html = f"""
    <section id="pre-earnings-watch">
      <h2>🔭 決算前 先行材料ウォッチ</h2>
      <p class="section-desc">
        好決算・ストップ高は決算発表の当日に突然出るのではなく、四半期の途中で
        「増産」「受注拡大」「工場増強」「データセンター」等の断片ニュースが先行することがあります
        (例: パナソニックHDのAIインフラ関連増産報道は、2026年7月の決算発表の1〜2か月前から出ていました)。
        ここではGoogle Newsの見出しに固定キーワードが含まれるかどうかだけを機械的に抽出しており、
        <b>LLMによる要約・意味解釈は行っていません</b>。見出しが一致しただけでは好材料の大きさ・
        信頼性は判断できないため、<b>必ずリンク先の原文をご確認ください。投資助言ではありません。</b>
      </p>
      <div class="card">
        <h3>ウォッチリスト銘柄の先行材料ニュース(直近14日・見出しキーワード一致)</h3>
        {pre_earnings_watch_html(data.get("pre_earnings_watch", []))}
      </div>
    </section>"""

    edinet_html = f"""
    <section id="edinet">
      <h2>📑 EDINET 大量保有報告書チェック(5%ルール・プロトタイプ)</h2>
      <p class="section-desc">
        金融庁EDINETに提出された大量保有報告書・変更報告書のうち、ウォッチリスト銘柄の会社名が
        書類概要に含まれるものを抽出しています。<b>EDINET APIの利用登録・APIキー設定
        (GitHub Secrets)が無い場合は常に「該当なし」表示になります。</b>
        対象銘柄の特定は構造化データではなく簡易文字列一致によるプロトタイプ実装のため、
        取りこぼしや誤検知が起こり得ます。<b>必ずEDINET原文でご確認ください。投資助言ではありません。</b>
      </p>
      <div class="card">
        <h3>直近の大量保有報告書・変更報告書</h3>
        {edinet_holdings_html(data.get("edinet_large_holdings", []))}
      </div>
    </section>"""

    disclaimer_text = (
        "本ページの情報は、Yahoo!ファイナンス・TDnet(適時開示情報閲覧サービス)・投資の森(テクニカル分析)・"
        "Google Newsなど無料で公開されている情報源をもとに自動的にまとめたものです。"
        "内容の正確性・完全性・最新性は保証されません。"
        "「強気/弱気シグナル」等の表示は移動平均線やRSIなど過去データに基づく機械的な診断であり、"
        "「先行材料ウォッチ」「ダブルシグナル」等の表示もニュース見出し・開示タグの単純なキーワード一致による"
        "機械的な抽出であり、AIによる分析ではありません。"
        "アナリストのコンセンサス予想(市場平均予想)は無料でリアルタイム取得できるソースがないため、本ページには含まれていません。"
        "<b>投資助言ではなく、将来の株価変動を保証するものでもありません。</b>"
        "投資に関する最終判断は、必ずご自身の責任で行ってください。"
    )

    sources_html = """
    <div class="sources">
      主な情報源: Yahoo!ファイナンス (finance.yahoo.co.jp) / TDnet 適時開示情報閲覧サービス
      (release.tdnet.info, 非公式API: webapi.yanoshin.jp) / 投資の森 テクニカル分析 (nikkeiyosoku.com) /
      Google News RSS (news.google.com、先行材料ウォッチの見出し抽出のみに使用)。
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
        <a href="#alignment">🧭 分析</a>
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
  {conclusion_html}
  {mood_html}
  <label class="fav-filter"><input type="checkbox" id="favFilterToggle"> ★ お気に入りのみ表示(コード欄の★で登録)</label>

  {morning_html}
  {evening_html}
  {technical_html}
  {alignment_html}
  {growth_html}
  {pre_earnings_html}
  {edinet_html}

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
