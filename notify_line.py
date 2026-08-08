#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data.json の内容から「本日の最注力銘柄」を1銘柄だけ選び、LINE Messaging API の
プッシュメッセージで通知するスクリプト。Main.java(データ収集) → news_analyzer.py(Gemini補完)
→ render_dashboard.py(HTML生成) のあとに実行する想定。

2026-08-06: 通知ロジックを「後追い型」から「先行シグナル型」に全面転換。
2026-08-06(同日・第2弾): 選定方式を「優先度カスケード(高い方から1つだけ採用)」から
「複合スコアリング(銘柄ごとに複数シグナルを合算)」に変更。
2026-08-06(同日・第3弾): technical(固定ウォッチリスト約20銘柄)に含まれない、
より小型・割安な銘柄も候補に入るよう growth_candidates(TDnet全銘柄対象の
増配・上方修正開示スキャン)をシグナルカテゴリとして追加。

--- 第1弾(先行シグナル型への転換)の経緯 ---
旧版は growth_candidates の double_signal(決算+上方修正の同時TDnet開示)や
technical の volume_surge(出来高急増)など、「すでに公開された好材料」を検知して
通知していた。これらは開示・急増が起きた瞬間に市場が即座に織り込むため、
開示が引け後〜翌朝寄り前に出た場合、通知を受け取った時点(=翌朝以降)には
寄り付きで既に株価が上がってしまっており、前日中に仕込む余地が無かった
(ユーザーからの報告: 「通知が来た当日に株価を見たら朝イチで既に上がっていた」)。

--- 第2弾(複合スコアリング化)の経緯 ---
第1弾では「優先度4→3→2→1→0の順で、最初に見つかった条件を満たす銘柄」を機械的に
1つ選んでいた。しかし優先度順の採用だと、例えば「pre_earnings_watchのニュースが1件
あるだけ」の銘柄が、「信用倍率+RSI+セクター逆行高が同時に揃っている」銘柄より
優先されてしまうケースがあり、必ずしも「最も上昇期待が高い銘柄」を選べていなかった。
そこで、シグナルの強さを点数化し、①複数シグナルが重なる銘柄ほど加点する
「コンフルエンス(重複確認)ボーナス」、②pre_earnings_watch/EDINETのテキストに
ネガティブな内容(下方修正・急落・保有株の減少等)が含まれる場合は好材料として
数えない「ネガティブ材料フィルタ」、③直近5日間で既に大きく上昇済み・52週高値に
接近しすぎている銘柄は「すでに市場が織り込み始めている」とみなして減点する
「過熱減点」、の3つを導入し、最もスコアの高い1銘柄を選ぶ方式に変更した。

--- 第3弾(growth_candidatesの追加)の経緯 ---
第2弾までのシグナル(EDINET/pre_earnings_watch/信用倍率/セクター逆行高)は、いずれも
technical配列に含まれる固定ウォッチリスト銘柄(トヨタ・ソニー・ファナック・任天堂・
ダイキン・ソフトバンクG等、時価総額の大きい有名企業が中心)にしか計算されておらず、
結果として通知される銘柄が毎回「有名かつ株価の高い大型株」に偏っていた
(ユーザーからの指摘: 「有名すぎるし株価高すぎる。手頃な株価の成長株が知りたい」)。
growth_candidatesはTDnetの適時開示をウォッチリストに限らず全銘柄横断でスキャンし、
増配・上方修正を検知したものなので、より小型・無名・割安な銘柄が拾える。ただし
これは「すでに開示された当日の情報」であり、第1弾の趣旨(先行シグナル=まだ市場に
出ていない情報)とは性質が異なるため、他カテゴリより基本点をやや低めに設定し、
通知文にもその旨(既に一部織り込まれている可能性がある)を明記する。
また growth_candidates には証券コード・株価データが含まれない(データ取得元の
株探TDnet開示一覧ページ自体にコードが載っていないため)。technicalの銘柄名と
完全一致した場合のみ価格等を補完し、一致しない場合は「価格帯要確認」の注記を付ける。
さらに、growth_candidatesを追加しただけでは、ファナック・任天堂・ダイキン等の
ウォッチリスト銘柄がpre_earnings_watchで先に強いシグナルを出した場合、結局
それらが選ばれてしまい「有名・値がさ株偏重」が解消されないままだった(実データで
検証したところ、ファナックのpre_earningsシグナル(スコア35)がgrowth_candidatesの
どの銘柄(最大21)よりも高く、結局ファナックが選ばれてしまうケースを確認)。
そこで、カテゴリを問わず一律で「株価が高いほど減点する」_price_penalty()を導入し、
株価データのある(=ウォッチリスト内の)銘柄が値がさであるほどスコアを下げることで、
「手頃な株価の銘柄を優先する」というユーザーの意向をスコアリング自体に組み込んだ。
株価データが無い(growth_candidatesのウォッチリスト外銘柄)場合は判定不能のため
減点なしとする。

シグナルカテゴリ(1カテゴリにつき1回だけ加点。同一カテゴリ内の複数シグナルは
ボーナスのみ小さく加算):
・EDINET大量保有報告書(新規, docTypeCode=350) … 大口投資家の新規5%保有は、市場の
  一般的な注目が集まる前に開示されることが多い先行指標。
・EDINET変更報告書(docTypeCode=351)で「増加」とみられるもの … 上と同様だが、
  「減少」(=売却)方向とみられる場合はネガティブ材料フィルタで除外する。
・pre_earnings_watch(決算に先行する断片ニュース: 増産・受注拡大・工場増強等) …
  タイトルに下方修正・急落・懸念等のネガティブ語が含まれる場合は除外する。
・信用倍率(squeeze_potential: 買残/売残<1倍=踏み上げ余地)+ RSI30台以下(売られ過ぎ)。
・セクター逆行高(sector_contrarian) … 同業種が軟調な中で単独で強い銘柄。
・信用倍率(squeeze_potential)のみ。
・growth_candidates(TDnet全銘柄横断の増配・上方修正開示) … ウォッチリスト外の
  小型・割安銘柄を拾うための補助シグナル。既に開示済みの当日情報である点に注意。

いずれのカテゴリでも、volume_surge(出来高急増)または gap_up(寄り付き窓開け)が
既についている銘柄は「すでに動いてしまった」とみなして候補から除外する
(先行シグナルの主旨に反するため)。growth_candidatesはtechnicalデータが無い
(=ウォッチリスト外の)銘柄が大半のため、この判定はtechnicalに一致した場合のみ働く。

注意:
- LINE Notify は2025年3月末でサービス終了しているため、後継の LINE Messaging API
(チャネルアクセストークン + 送信先user/group ID)のプッシュメッセージを使う。
- LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が未設定、またはAPI呼び出しが失敗した場合は、
既存のパイプラインを止めないよう、ログを出すだけで正常終了する(exit code 0)。
- 同じ銘柄への通知が15分間隔の自動実行のたびに重複して飛ばないよう、data.json内の
line_notify_last(当日日付+銘柄コードまたは銘柄名)で簡易的な重複送信防止を行う。
- 本ロジックはあくまで機械的な条件抽出・スコアリングであり、翌日の株価上昇を保証する
ものではない(それが可能なら誰でも儲かってしまう)。あくまで「まだ十分に織り込まれて
いない可能性が相対的に高い」候補を絞り込むものであり、最終的な投資判断は必ず開示原文・
チャートを自分の目で確認したうえで自己責任で行うこと。

使い方: python3 notify_line.py <data.jsonのパス>
"""
import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

# LINEは「材料が出た」ことを知らせるだけではなく、通知した時点でもまだ
# エントリーを検討できる位置にある銘柄だけを送る。値は保守的な初期値であり、
# 実績を見ながら環境変数で調整できる。
MAX_DATA_AGE_MINUTES = int(os.environ.get("LINE_MAX_DATA_AGE_MINUTES", "30"))
MAX_DAY_CHANGE_PCT = float(os.environ.get("LINE_MAX_DAY_CHANGE_PCT", "2.5"))
MAX_OPEN_GAP_PCT = float(os.environ.get("LINE_MAX_OPEN_GAP_PCT", "1.5"))
MAX_FROM_DAY_LOW_PCT = float(os.environ.get("LINE_MAX_FROM_DAY_LOW_PCT", "2.0"))
MAX_FROM_DAY_HIGH_PCT = float(os.environ.get("LINE_MAX_FROM_DAY_HIGH_PCT", "1.0"))

# 取引開始直後の値動きが落ち着かない時間帯と、引け間際を避ける。GitHub Actionsの
# 開始遅延があっても、前日終値のまま通知することを防ぐため、立会時間外は送信しない。
MARKET_OPEN_MINUTE = 9 * 60 + 5
MARKET_CLOSE_MINUTE = 15 * 60 + 15

# pre_earnings_watch/growth_candidates のタイトルや EDINET の doc_description に
# 含まれていたら、「好材料」としては数えない(むしろ悪材料寄り)とみなすキーワード。
# 例: 「AI投資」というキーワードでヒットしても、タイトルが「AI投資回収の懸念で急落」
# のような下落記事であれば、先行シグナルとしては逆効果なので除外する。
NEGATIVE_KEYWORDS = (
    "下方修正", "減益", "赤字", "特別損失", "特損", "損失", "急落", "急落安",
    "反落", "下落", "懸念", "売り優勢", "引き下げ", "格下げ", "上場廃止",
    "破産", "民事再生", "解散", "減配", "無配", "業績悪化", "不正", "訴訟",
    "リコール", "疑い", "流出", "延期", "中止", "撤回", "自主回収",
)

# EDINETの変更報告書(docTypeCode=351)が「保有株式の増加」方向かどうかの簡易判定用。
EDINET_INCREASE_HINTS = ("増加", "取得")
EDINET_DECREASE_HINTS = ("減少", "売却")

# growth_candidatesのcatalyst種別ごとの重み補正。上方修正は業績そのものの上振れであり、
# 増配(配当という資本政策上の意思決定)よりもやや事業実態に近い変化とみなし、わずかに
# 加点する。
GROWTH_CATALYST_BONUS = {
    "上方修正": 3.0,
    "増配": 0.0,
}


def log(msg):
    print(f"[notify_line] {msg}", file=sys.stderr)


def _already_moved(t):
    """volume_surge(出来高急増)またはgap_up(寄り付き窓開け)が付いている銘柄は、
    先行シグナルの主旨に反する(既に動いてしまった)ため除外する。"""
    if not t:
        return False
    return bool(t.get("volume_surge")) or bool(t.get("gap_up"))


def _has_negative_keyword(text):
    if not text:
        return False
    return any(k in text for k in NEGATIVE_KEYWORDS)


def _fmt_num(v, suffix=""):
    if isinstance(v, (int, float)):
        return f"{v}{suffix}"
    return "―"


def _jst_now():
    return datetime.now(JST)


def _is_regular_session(now=None):
    """東証の通常立会時間中かを判定する(祝日は価格データ検証でも弾かれる)。"""
    now = now or _jst_now()
    if now.weekday() >= 5:
        return False
    minute = now.hour * 60 + now.minute
    return MARKET_OPEN_MINUTE <= minute <= MARKET_CLOSE_MINUTE


def _data_is_fresh(root, now=None):
    """パイプライン全体が遅れた場合に、古いdata.jsonでLINEを送らない。"""
    generated_at = (root.get("generated_at") or "").strip()
    if not generated_at:
        return False, "更新時刻がありません"
    try:
        generated = datetime.strptime(generated_at, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
    except ValueError:
        return False, f"更新時刻の形式が不正です({generated_at})"
    age_minutes = ((now or _jst_now()) - generated).total_seconds() / 60
    # 時計ずれで未来になるケースは小さな誤差だけ許容する。
    if age_minutes < -5 or age_minutes > MAX_DATA_AGE_MINUTES:
        return False, f"データが{age_minutes:.0f}分前で新鮮ではありません"
    return True, None


def _fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "jp-daytrade-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def _resolve_yahoo_symbol(name, code=None):
    """証券コードがないTDnet銘柄も、Yahoo検索で東証コードを特定する。

    完全一致で確認できない曖昧な社名は、誤通知を防ぐため候補から外す。
    """
    if code and str(code).isdigit():
        return f"{code}.T", str(code)
    query = urllib.parse.quote(name)
    payload = _fetch_json(
        f"https://query1.finance.yahoo.com/v1/finance/search?q={query}&quotesCount=10&newsCount=0"
    )
    normalized = (name or "").replace(" ", "").replace("　", "")
    matches = []
    for quote in payload.get("quotes", []):
        symbol = quote.get("symbol", "")
        quote_name = (quote.get("shortname") or quote.get("longname") or "").replace(" ", "").replace("　", "")
        if not symbol.endswith(".T") or quote.get("quoteType") != "EQUITY":
            continue
        if quote_name == normalized:
            matches.append((symbol, symbol[:-2]))
    if len(matches) == 1:
        return matches[0]
    return None, None


def _fetch_live_quote(symbol):
    """Yahoo Financeの1分足から、通知時点の価格・寄り付き・当日高安を取得する。"""
    encoded = urllib.parse.quote(symbol, safe="^=.-")
    payload = _fetch_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1m&range=1d&includePrePost=false"
    )
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return None
    meta = result.get("meta") or {}
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    opens = [x for x in quote.get("open", []) if isinstance(x, (int, float))]
    highs = [x for x in quote.get("high", []) if isinstance(x, (int, float))]
    lows = [x for x in quote.get("low", []) if isinstance(x, (int, float))]
    closes = [x for x in quote.get("close", []) if isinstance(x, (int, float))]
    price = meta.get("regularMarketPrice")
    prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
    if not isinstance(price, (int, float)) or not isinstance(prev_close, (int, float)) or prev_close <= 0:
        return None
    if not opens or not highs or not lows or not closes:
        return None
    return {
        "price": float(price),
        "previous_close": float(prev_close),
        "open": float(opens[0]),
        "day_high": float(max(highs)),
        "day_low": float(min(lows)),
        "market_state": meta.get("marketState", ""),
        "regular_market_time": meta.get("regularMarketTime"),
    }


def _pct(current, base):
    return (current - base) / base * 100.0 if base else None


def _entry_check(candidate):
    """候補を通知直前の値動きで再判定する。

    Trueの場合だけLINEに送る。データが取得できない場合も通知しないことで、
    "上がり切ったか不明な銘柄"を買い候補として誤って送らない。
    """
    try:
        symbol, resolved_code = _resolve_yahoo_symbol(candidate["name"], candidate.get("code"))
        if not symbol:
            return False, "東証コードを一意に特定できません", None
        quote = _fetch_live_quote(symbol)
        if not quote:
            return False, "リアルタイム株価を取得できません", None
    except Exception as e:
        log(f"リアルタイム価格の取得失敗({candidate['name']}): {e}")
        return False, "リアルタイム株価の取得に失敗しました", None

    price = quote["price"]
    day_change = _pct(price, quote["previous_close"])
    open_gap = _pct(quote["open"], quote["previous_close"])
    from_low = _pct(price, quote["day_low"])
    from_high = _pct(quote["day_high"], price)
    failures = []
    if day_change is None or day_change > MAX_DAY_CHANGE_PCT:
        failures.append(f"前日終値比{_fmt_num(day_change, '%')}で上昇済み")
    if open_gap is None or open_gap > MAX_OPEN_GAP_PCT:
        failures.append(f"寄り付きギャップ{_fmt_num(open_gap, '%')}が大きい")
    if from_low is None or from_low > MAX_FROM_DAY_LOW_PCT:
        failures.append(f"当日安値から{_fmt_num(from_low, '%')}上昇済み")
    if from_high is None or from_high > MAX_FROM_DAY_HIGH_PCT:
        failures.append(f"高値から{_fmt_num(from_high, '%')}下落している")
    if failures:
        return False, "、".join(failures), None

    quote["symbol"] = symbol
    quote["code"] = resolved_code
    quote["day_change_pct"] = round(day_change, 2)
    quote["open_gap_pct"] = round(open_gap, 2)
    quote["from_day_low_pct"] = round(from_low, 2)
    quote["from_day_high_pct"] = round(from_high, 2)
    return True, None, quote


def _collect_signal_hits(root):
    """data.json から、銘柄コード(または銘柄名)ごとの「先行シグナル」候補
    (カテゴリ単位)を集める。
    戻り値: {key: [hit, hit, ...]}, technical_by_code。
    keyは銘柄コード(technicalに存在する場合)、無ければ "NAME:会社名"。
    hitは {category, weight, name, reason, detail, url} の辞書。
    """
    technical = root.get("technical", []) or []
    pre_earnings = root.get("pre_earnings_watch", []) or []
    edinet = root.get("edinet_large_holdings", []) or []
    growth_candidates = root.get("growth_candidates", []) or []

    technical_by_code = {t.get("code"): t for t in technical if t.get("code")}
    technical_by_name = {t.get("name"): t for t in technical if t.get("name")}
    hits_by_code = {}

    def add_hit(code, hit):
        if not code:
            return
        hits_by_code.setdefault(code, []).append(hit)

    # EDINET大量保有報告書・変更報告書
    for e in edinet:
        code = e.get("code")
        t = technical_by_code.get(code)
        if _already_moved(t):
            continue
        doc_type = e.get("doc_type", "大量保有報告書")
        desc = e.get("doc_description", "") or ""
        if doc_type == "変更報告書":
            is_decrease = any(k in desc for k in EDINET_DECREASE_HINTS) and not any(
                k in desc for k in EDINET_INCREASE_HINTS
            )
            if is_decrease:
                # 保有株式の「減少」(売却方向)とみられるため、先行シグナルとしては使わない。
                continue
            weight = 30
        else:
            weight = 40  # 新規の5%大量保有はより強い先行指標として重めに評価する
        add_hit(code, {
            "category": "edinet",
            "weight": weight,
            "name": e.get("name", ""),
            "reason": f"EDINET{doc_type}を検知(提出者: {e.get('filer_name', '―')})",
            "detail": e.get("doc_description"),
            "url": None,
        })

    # 決算に先行する断片ニュース(pre_earnings_watch)
    for p in pre_earnings:
        code = p.get("code")
        t = technical_by_code.get(code)
        if _already_moved(t):
            continue
        title = p.get("title", "") or ""
        if _has_negative_keyword(title):
            # キーワードは拾えているが、内容自体はネガティブ(下方修正・急落等)なので
            # 好材料としては数えない。
            continue
        add_hit(code, {
            "category": "pre_earnings",
            "weight": 30,
            "name": p.get("company", ""),
            "reason": f"決算に先行する材料ニュース「{p.get('keyword', '')}」を検知",
            "detail": p.get("title"),
            "url": p.get("url"),
        })

    # 信用倍率(踏み上げ余地)+ RSI売られ過ぎ / 信用倍率のみ
    for t in technical:
        if not t.get("squeeze_potential"):
            continue
        if _already_moved(t):
            continue
        code = t.get("code")
        credit_ratio = t.get("credit_ratio")
        rsi = t.get("rsi")
        credit_bonus = 0.0
        if isinstance(credit_ratio, (int, float)):
            credit_bonus = max(0.0, (1.0 - credit_ratio)) * 10.0
        if isinstance(rsi, (int, float)) and rsi <= 35:
            rsi_bonus = max(0.0, (35.0 - rsi)) * 0.5
            add_hit(code, {
                "category": "squeeze_rsi",
                "weight": 25 + credit_bonus + rsi_bonus,
                "name": t.get("name", ""),
                "reason": f"信用倍率{_fmt_num(credit_ratio, '倍')}(踏み上げ余地)+RSI{_fmt_num(rsi)}(売られ過ぎ)",
                "detail": None,
                "url": None,
            })
        else:
            add_hit(code, {
                "category": "squeeze_only",
                "weight": 12 + credit_bonus,
                "name": t.get("name", ""),
                "reason": f"信用倍率{_fmt_num(credit_ratio, '倍')}(踏み上げ余地)",
                "detail": None,
                "url": None,
            })

    # セクター逆行高
    for t in technical:
        if not t.get("sector_contrarian"):
            continue
        if _already_moved(t):
            continue
        code = t.get("code")
        sector_avg = t.get("sector_avg_change_pct")
        own = t.get("change_pct")
        gap = (own - sector_avg) if isinstance(own, (int, float)) and isinstance(sector_avg, (int, float)) else 0.0
        add_hit(code, {
            "category": "sector_contrarian",
            "weight": 20 + max(0.0, gap) * 2.0,
            "name": t.get("name", ""),
            "reason": f"{t.get('sector', '同業種')}が軟調な中で逆行高(セクター平均{_fmt_num(sector_avg, '%')}に対し{_fmt_num(own, '%')})",
            "detail": None,
            "url": None,
        })

    # growth_candidates(TDnet全銘柄横断の増配・上方修正開示。ウォッチリスト外の
    # 小型・割安銘柄を拾うための補助シグナル)
    for g in growth_candidates:
        company = (g.get("company") or "").strip()
        if not company:
            continue
        title = (g.get("title") or "").strip()
        catalyst = (g.get("catalyst") or "").strip()
        if _has_negative_keyword(title) or _has_negative_keyword(catalyst):
            continue
        t = technical_by_name.get(company)
        if _already_moved(t):
            continue
        code = (t.get("code") if t else None) or f"NAME:{company}"
        weight = 18.0 + GROWTH_CATALYST_BONUS.get(catalyst, 0.0)
        if g.get("double_signal"):
            weight += 12.0
        reason = f"TDnet適時開示「{catalyst}」を検知(ウォッチリスト外・当日開示情報)"
        if g.get("double_signal"):
            reason += "(業績・配当の両修正で複合シグナル)"
        add_hit(code, {
            "category": "growth_candidate",
            "weight": weight,
            "name": company,
            "reason": reason,
            "detail": title,
            "url": g.get("url"),
        })

    return hits_by_code, technical_by_code


def _overheat_penalty(t):
    """既に短期的に上がりすぎている・52週高値に接近しすぎている・RSIが過熱域にある
    銘柄は、先行シグナルの旨みが薄い(市場が織り込み始めている)とみなして減点する。
    render_dashboard.py の4項目スコアリングにおける「期待値」軸と同じ考え方。
    technicalデータが無い銘柄(ウォッチリスト外)は判定できないため減点なし。
    戻り値: (penalty(0以上の数値), reasons(list[str]))
    """
    if not t:
        return 0.0, []
    penalty = 0.0
    reasons = []

    rsi = t.get("rsi")
    if isinstance(rsi, (int, float)) and rsi >= 70:
        penalty += 15.0
        reasons.append(f"RSI{_fmt_num(rsi)}で過熱気味")

    ret5d = t.get("ret_5d_pct")
    if isinstance(ret5d, (int, float)) and ret5d >= 15.0:
        penalty += 10.0
        reasons.append(f"直近5日で既に{_fmt_num(ret5d, '%')}上昇済み")

    high_dist = t.get("high_52w_dist_pct")
    if isinstance(high_dist, (int, float)) and high_dist <= 3.0:
        penalty += 10.0
        reasons.append("52週高値に接近済み")

    return penalty, reasons


def _parse_price(price):
    """technical[].price はJSON上「6,430.0」のようなカンマ区切り文字列、または
    寄り付き前などデータ未取得時は「―」というプレースホルダー文字列で入っている。
    数値化できた場合のみfloatを返し、それ以外はNoneを返す。"""
    if isinstance(price, (int, float)):
        return float(price)
    if isinstance(price, str):
        cleaned = price.replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _price_penalty(t):
    """カテゴリを問わず一律で、株価が高いほど減点する。「有名だが値がさ株ばかり
    通知される」問題に対し、特定カテゴリだけを優遇するのではなく、株価そのものを
    スコアに反映させることで「手頃な株価の銘柄を優先する」方針を実現する。
    growth_candidatesのウォッチリスト外銘柄など、株価データが無い場合は判定不能
    のため減点なし(=相対的に不利にならない)。
    戻り値: (penalty(0以上の数値), reasons(list[str]))
    """
    if not t:
        return 0.0, []
    price = _parse_price(t.get("price"))
    if price is None:
        # technical(固定ウォッチリスト)に載っている時点で、寄り付き前などで株価
        # データが未取得でも、トヨタ・ソニー・ファナック・任天堂級の有名大型株で
        # あることに変わりはない。株価を判定できないからといって無条件扱いに
        # すると値がさ株が抜け道になってしまうため、既定のペナルティを一律で
        # かけておく(手頃な株価の銘柄を優先する方針)。
        return 15.0, ["株価データ未取得ですがウォッチリスト内の有名大型株のため一定減点"]
    if price <= 2000:
        return 0.0, []
    if price <= 5000:
        penalty = (price - 2000) / 1000.0 * 3.0
    else:
        penalty = 9.0 + min((price - 5000) / 1000.0, 4.2) * 5.0
    penalty = min(penalty, 30.0)
    return penalty, [f"株価{price:,.0f}円で値がさ(手頃な株価の銘柄を優先する方針のため減点)"]


def score_candidates(root):
    """銘柄コード(または銘柄名)ごとにシグナルを合算し、複合スコアの高い順に
    候補リストを返す。
    各候補: {code, name, technical, score, category_count, categories, reasons, hits}
    """
    hits_by_code, technical_by_code = _collect_signal_hits(root)
    if not hits_by_code:
        return []

    candidates = []
    for code, hits in hits_by_code.items():
        # カテゴリごとに最良の1件だけを基本点として採用し、同カテゴリ内の追加ヒットは
        # ごく小さいボーナス(+5、最大+10)のみ加算する(単なる水増しを防ぐため)。
        by_category = {}
        for h in hits:
            by_category.setdefault(h["category"], []).append(h)

        base_score = 0.0
        used_hits = []
        for cat, cat_hits in by_category.items():
            cat_hits.sort(key=lambda h: h["weight"], reverse=True)
            best = cat_hits[0]
            base_score += best["weight"]
            used_hits.append(best)
            extra = min(2, len(cat_hits) - 1)
            base_score += extra * 5.0

        category_count = len(by_category)
        confluence_bonus = 15.0 * (category_count - 1) if category_count >= 2 else 0.0
        confluence_bonus = min(confluence_bonus, 45.0)

        # technicalデータは実際の証券コードにのみ紐づく("NAME:"キーは無し)。
        real_code = code if not code.startswith("NAME:") else None
        t = technical_by_code.get(real_code)
        overheat_pen, overheat_reasons = _overheat_penalty(t)
        price_pen, price_reasons = _price_penalty(t)
        penalty = overheat_pen + price_pen
        penalty_reasons = overheat_reasons + price_reasons

        score = base_score + confluence_bonus - penalty

        name = (t.get("name") if t else "") or next(
            (h["name"] for h in hits if h.get("name")), ""
        )

        candidates.append({
            "code": real_code,
            "display_name": name,
            "name": name,
            "technical": t,
            "score": round(score, 1),
            "category_count": category_count,
            "categories": list(by_category.keys()),
            "confluence_bonus": confluence_bonus,
            "penalty": penalty,
            "penalty_reasons": penalty_reasons,
            "reasons": [h["reason"] for h in used_hits],
            "details": [h["detail"] for h in used_hits if h.get("detail")],
            "urls": [h["url"] for h in used_hits if h.get("url")],
        })

    candidates.sort(key=lambda c: (c["score"], c["category_count"]), reverse=True)
    return candidates


def pick_best_candidate(root):
    """スコア上位から、通知時点でも上がり切っていない銘柄を選ぶ。

    材料だけで選ばず、全候補にリアルタイム再判定を行う。最上位が急騰済みでも
    次点を検討でき、全候補が不適格なら無理にLINEを送らない。
    """
    rejected = []
    for candidate in score_candidates(root):
        eligible, reason, quote = _entry_check(candidate)
        if not eligible:
            rejected.append(f"{candidate['name']}: {reason}")
            continue
        candidate["live_quote"] = quote
        if quote.get("code"):
            candidate["code"] = quote["code"]
        return candidate, rejected
    return None, rejected


def build_message(pick):
    t = pick.get("technical") or {}
    live = pick.get("live_quote") or {}
    name = pick["name"] or t.get("name") or ""
    code = pick["code"] or ""
    price = live.get("price") or t.get("price", "")
    change_pct = live.get("day_change_pct")
    if change_pct is None:
        change_pct = t.get("change_pct")
    change_str = f"{change_pct:+.2f}%" if isinstance(change_pct, (int, float)) else "―"

    lines = [
        "📡 先行シグナル銘柄(仕込み検討用)",
        f"{name}({code})" if code else f"{name}",
    ]
    if price:
        price_str = f"{price:,.0f}円" if isinstance(price, (int, float)) else str(price)
        lines.append(f"現在値: {price_str} ({change_str})")
    elif not t:
        lines.append("現在値: ―(ウォッチリスト外銘柄のため株価データなし。ご自身でチャート確認をお願いします)")
    lines.append(f"総合スコア: {pick['score']:.0f}点(該当シグナル{pick['category_count']}種)")
    for r in pick["reasons"]:
        lines.append(f"・{r}")
    for d in pick["details"][:2]:
        lines.append(f"詳細: {d}")
    if pick["urls"]:
        lines.append(f"参照: {pick['urls'][0]}")
    if pick["penalty_reasons"]:
        lines.append("注意: " + "、".join(pick["penalty_reasons"]) + "(既に一部織り込み済みの可能性)")
    if live:
        lines.append(
            "値動き確認: "
            f"寄り付き比{live['open_gap_pct']:+.2f}% / "
            f"安値から{live['from_day_low_pct']:+.2f}% / "
            f"高値から{live['from_day_high_pct']:+.2f}%"
        )
        lines.append(
            f"検討価格帯: {live['day_low']:,.0f}〜{live['price']:,.0f}円 "
            "(この範囲を上回って追いかけない)"
        )
    if "growth_candidate" in pick.get("categories", []):
        lines.append(
            "※本銘柄はTDnet適時開示ベースの当日公開情報を含みます。"
            "先行シグナル(未公開情報)とは性質が異なり、既に一部織り込まれている可能性があります。"
        )

    lines.append(
        "※本通知は複数の先行シグナルを機械的にスコア化して抽出したものであり、"
        "翌日の上昇を保証するものではありません。"
        "必ずご自身でチャート・開示原文を確認のうえ、自己責任でご判断ください。"
    )
    return "\n".join(lines)


def send_line_push(token, user_id, message_text):
    url = "https://api.line.me/v2/bot/message/push"
    body = {
        "to": user_id,
        "messages": [{"type": "text", "text": message_text}],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.status


def main():
    data_path = sys.argv[1] if len(sys.argv) > 1 else "data.json"

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("LINE_USER_ID", "").strip()
    if not token or not user_id:
        log("LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が未設定のため、通知をスキップします。")
        return

    with open(data_path, encoding="utf-8") as f:
        root = json.load(f)

    now = _jst_now()
    if not _is_regular_session(now):
        log("立会時間外または開始直後のため、前日価格ベースのLINE通知をスキップします。")
        return

    fresh, fresh_reason = _data_is_fresh(root, now)
    if not fresh:
        log(f"{fresh_reason}。古い候補での通知をスキップします。")
        return

    pick, rejected = pick_best_candidate(root)
    if not pick:
        summary = " / ".join(rejected[:5]) if rejected else "先行シグナルの候補なし"
        log(f"エントリー可能な候補が無いため、通知はスキップします。除外理由: {summary}")
        return

    dedup_key = pick["code"] or pick["name"]
    today_str = now.strftime("%Y-%m-%d")
    last = root.get("line_notify_last") or {}
    if last.get("date") == today_str and last.get("code") == dedup_key:
        log(f"本日は既に{dedup_key}を通知済みのため、重複通知をスキップします。")
        return

    message = build_message(pick)
    try:
        status = send_line_push(token, user_id, message)
        log(f"LINE通知を送信しました(HTTP {status}): {pick['name']}(スコア{pick['score']:.0f}, カテゴリ{pick['category_count']}種)")
    except Exception as e:
        log(f"LINE通知の送信に失敗しました(パイプラインは継続します): {e}")
        return

    root["line_notify_last"] = {"date": today_str, "code": dedup_key}
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(root, f, ensure_ascii=False, indent=2)
    log("data.json に通知済み状態を書き戻しました。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"予期しないエラー(パイプラインは継続します): {e}")
        sys.exit(0)
