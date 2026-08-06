#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data.json の内容から「本日の最注力銘柄」を1銘柄だけ選び、LINE Messaging API の
プッシュメッセージで通知するスクリプト。Main.java(データ収集) → news_analyzer.py(Gemini補完)
→ render_dashboard.py(HTML生成) のあとに実行する想定。

2026-08-06: 通知ロジックを「後追い型」から「先行シグナル型」に全面転換。
2026-08-06(同日・第2弾): 選定方式を「優先度カスケード(高い方から1つだけ採用)」から
「複合スコアリング(銘柄ごとに複数シグナルを合算)」に変更。

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

いずれのカテゴリでも、volume_surge(出来高急増)または gap_up(寄り付き窓開け)が
既についている銘柄は「すでに動いてしまった」とみなして候補から除外する
(先行シグナルの主旨に反するため)。

注意:
- LINE Notify は2025年3月末でサービス終了しているため、後継の LINE Messaging API
(チャネルアクセストークン + 送信先user/group ID)のプッシュメッセージを使う。
- LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が未設定、またはAPI呼び出しが失敗した場合は、
既存のパイプラインを止めないよう、ログを出すだけで正常終了する(exit code 0)。
- 同じ銘柄への通知が15分間隔の自動実行のたびに重複して飛ばないよう、data.json内の
line_notify_last(当日日付+銘柄コード)で簡易的な重複送信防止を行う。
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
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

# pre_earnings_watch のタイトルや EDINET の doc_description に含まれていたら、
# 「好材料」としては数えない(むしろ悪材料寄り)とみなすキーワード。
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


def _collect_signal_hits(root):
    """data.json から、銘柄コードごとの「先行シグナル」候補(カテゴリ単位)を集める。
    戻り値: {code: [hit, hit, ...]}。hitは
    {category, weight, name, reason, detail, url} の辞書。
    """
    technical = root.get("technical", []) or []
    pre_earnings = root.get("pre_earnings_watch", []) or []
    edinet = root.get("edinet_large_holdings", []) or []

    technical_by_code = {t.get("code"): t for t in technical if t.get("code")}
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

    return hits_by_code, technical_by_code


def _overheat_penalty(t):
    """既に短期的に上がりすぎている・52週高値に接近しすぎている・RSIが過熱域にある
    銘柄は、先行シグナルの旨みが薄い(市場が織り込み始めている)とみなして減点する。
    render_dashboard.py の4項目スコアリングにおける「期待値」軸と同じ考え方。
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


def score_candidates(root):
    """銘柄コードごとにシグナルを合算し、複合スコアの高い順に候補リストを返す。
    各候補: {code, name, technical, score, category_count, reasons, hits}
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

        t = technical_by_code.get(code)
        penalty, penalty_reasons = _overheat_penalty(t)

        score = base_score + confluence_bonus - penalty

        name = (t.get("name") if t else "") or next(
            (h["name"] for h in hits if h.get("name")), ""
        )

        candidates.append({
            "code": code,
            "name": name,
            "technical": t,
            "score": round(score, 1),
            "category_count": category_count,
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
    """複合スコアが最も高い1銘柄を選ぶ。候補が無ければNoneを返す。"""
    candidates = score_candidates(root)
    return candidates[0] if candidates else None


def build_message(pick):
    t = pick.get("technical") or {}
    name = pick["name"] or t.get("name") or ""
    code = pick["code"] or ""
    price = t.get("price", "")
    change_pct = t.get("change_pct")
    change_str = f"{change_pct:+.2f}%" if isinstance(change_pct, (int, float)) else "―"

    lines = [
        "📡 先行シグナル銘柄(仕込み検討用)",
        f"{name}({code})" if code else f"{name}",
    ]
    if price:
        lines.append(f"現在値: {price} ({change_str})")
    lines.append(f"総合スコア: {pick['score']:.0f}点(該当シグナル{pick['category_count']}種)")
    for r in pick["reasons"]:
        lines.append(f"・{r}")
    for d in pick["details"][:2]:
        lines.append(f"詳細: {d}")
    if pick["urls"]:
        lines.append(f"参照: {pick['urls'][0]}")
    if pick["penalty_reasons"]:
        lines.append("注意: " + "、".join(pick["penalty_reasons"]) + "(既に一部織り込み済みの可能性)")

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

    pick = pick_best_candidate(root)
    if not pick:
        log("先行シグナルの条件を満たす銘柄が無いため、通知はスキップします。")
        return

    dedup_key = pick["code"] or pick["name"]
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
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
