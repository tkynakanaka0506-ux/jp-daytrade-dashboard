#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data.json の内容から「本日の最注力銘柄」を1銘柄だけ機械的に選び、LINE Messaging API の
プッシュメッセージで通知するスクリプト。Main.java(データ収集) → news_analyzer.py(Gemini補完)
→ render_dashboard.py(HTML生成) のあとに実行する想定。

2026-08-06: 通知ロジックを「後追い型」から「先行シグナル型」に全面転換。

旧ロジック(廃止)の問題点:
旧版は growth_candidates の double_signal(決算+上方修正の同時TDnet開示)や
technical の volume_surge(出来高急増)など、「すでに公開された好材料」を検知して
通知していた。これらは開示・急増が起きた瞬間に市場が即座に織り込むため、
開示が引け後〜翌朝寄り前に出た場合、通知を受け取った時点(=翌朝以降)には
寄り付きで既に株価が上がってしまっており、前日中に仕込む余地が無かった
(ユーザーからの報告: 「通知が来た当日に株価を見たら朝イチで既に上がっていた」)。

新ロジック:
「まだ市場が十分に織り込んでいない可能性がある、先回り的なシグナル」だけを対象にする。
市場時間中(8:30〜15:30 JST)は15分おきにパイプラインが回るため、当日の取引時間内
(15:30まで)に検知できたシグナルはその日のうちに通知される。

優先度順(高い方から1つだけ選ぶ):
4) EDINET大量保有報告書(5%ルール) … 大口投資家の保有異動は市場の一般的な注目が
   集まる前に開示されることが多い先行指標(EDINET_API_KEY未設定時はデータ自体が無い)。
3) pre_earnings_watch(決算に先行する断片ニュース: 増産・受注拡大・工場増強等) …
   決算発表そのものではなく、その手前の関連ニュースの段階で拾う設計(Main.java参照)。
2) 信用倍率(squeeze_potential: 買残/売残<1倍=踏み上げ余地)+ RSI30台以下(売られ過ぎ)の
   組み合わせ … 需給が良く、かつ売られ過ぎで反発余地がある状態。
1) セクター逆行高(sector_contrarian) … 同業種が軟調な中で単独で強い銘柄は、
   他の同業種銘柄への物色波及や見直し買いが後から入る余地がある。
0) 信用倍率(squeeze_potential)のみ。

いずれの優先度でも、volume_surge(出来高急増)または gap_up(寄り付き窓開け)が
既についている銘柄は「すでに動いてしまった」とみなして候補から除外する
(先行シグナルの主旨に反するため)。

注意:
- LINE Notify は2025年3月末でサービス終了しているため、後継の LINE Messaging API
(チャネルアクセストークン + 送信先user/group ID)のプッシュメッセージを使う。
- LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が未設定、またはAPI呼び出しが失敗した場合は、
既存のパイプラインを止めないよう、ログを出すだけで正常終了する(exit code 0)。
- 同じ銘柄への通知が15分間隔の自動実行のたびに重複して飛ばないよう、data.json内の
line_notify_last(当日日付+銘柄コード)で簡易的な重複送信防止を行う。
- 本ロジックはあくまで機械的な条件抽出であり、翌日の株価上昇を保証するものではない
(それが可能なら誰でも儲かってしまう)。あくまで「まだ十分に織り込まれていない可能性が
相対的に高い」候補を絞り込むものであり、最終的な投資判断は必ず開示原文・チャートを
自分の目で確認したうえで自己責任で行うこと。

使い方: python3 notify_line.py <data.jsonのパス>
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))


def log(msg):
    print(f"[notify_line] {msg}", file=sys.stderr)


def _already_moved(t):
    """volume_surge(出来高急増)またはgap_up(寄り付き窓開け)が付いている銘柄は、
    先行シグナルの主旨に反する(既に動いてしまった)ため除外する。"""
    if not t:
        return False
    return bool(t.get("volume_surge")) or bool(t.get("gap_up"))


def _fmt_num(v, suffix=""):
    if isinstance(v, (int, float)):
        return f"{v}{suffix}"
    return "―"


def pick_leading_signal_stock(root):
    """「先行シグナル型」の最注力銘柄を1つだけ選ぶ。候補が無ければNoneを返す。"""
    technical = root.get("technical", []) or []
    pre_earnings = root.get("pre_earnings_watch", []) or []
    edinet = root.get("edinet_large_holdings", []) or []

    technical_by_code = {t.get("code"): t for t in technical if t.get("code")}

    candidates = []

    # 優先度4: EDINET大量保有報告書(5%ルール)
    for e in edinet:
        code = e.get("code")
        t = technical_by_code.get(code)
        if _already_moved(t):
            continue
        candidates.append({
            "priority": 4,
            "code": code,
            "name": e.get("name") or (t.get("name") if t else "") or "",
            "technical": t,
            "reason": f"EDINET{e.get('doc_type', '大量保有報告書')}を検知(提出者: {e.get('filer_name', '―')})",
            "detail": e.get("doc_description"),
            "url": None,
            "tiebreak": 0.0,
        })

    # 優先度3: 決算に先行する断片ニュース(pre_earnings_watch)
    for p in pre_earnings:
        code = p.get("code")
        t = technical_by_code.get(code)
        if _already_moved(t):
            continue
        candidates.append({
            "priority": 3,
            "code": code,
            "name": p.get("company", ""),
            "technical": t,
            "reason": f"決算に先行する材料ニュース「{p.get('keyword', '')}」を検知",
            "detail": p.get("title"),
            "url": p.get("url"),
            "tiebreak": 0.0,
        })

    # 優先度2: 信用倍率(踏み上げ余地)+ RSI売られ過ぎ
    for t in technical:
        if not t.get("squeeze_potential"):
            continue
        if _already_moved(t):
            continue
        rsi = t.get("rsi")
        if not (isinstance(rsi, (int, float)) and rsi <= 35):
            continue
        candidates.append({
            "priority": 2,
            "code": t.get("code"),
            "name": t.get("name", ""),
            "technical": t,
            "reason": f"信用倍率{_fmt_num(t.get('credit_ratio'), '倍')}(踏み上げ余地)+RSI{_fmt_num(rsi)}(売られ過ぎ)",
            "detail": None,
            "url": None,
            "tiebreak": rsi,  # 低いほど優先
        })

    # 優先度1: セクター逆行高
    for t in technical:
        if not t.get("sector_contrarian"):
            continue
        if _already_moved(t):
            continue
        sector_avg = t.get("sector_avg_change_pct")
        own = t.get("change_pct")
        gap = (own - sector_avg) if isinstance(own, (int, float)) and isinstance(sector_avg, (int, float)) else 0.0
        candidates.append({
            "priority": 1,
            "code": t.get("code"),
            "name": t.get("name", ""),
            "technical": t,
            "reason": f"{t.get('sector', '同業種')}が軟調な中で逆行高(セクター平均{_fmt_num(sector_avg, '%')}に対し{_fmt_num(own, '%')})",
            "detail": None,
            "url": None,
            "tiebreak": -gap,  # 乖離が大きいほど優先
        })

    # 優先度0: 信用倍率(踏み上げ余地)のみ
    for t in technical:
        if not t.get("squeeze_potential"):
            continue
        if _already_moved(t):
            continue
        candidates.append({
            "priority": 0,
            "code": t.get("code"),
            "name": t.get("name", ""),
            "technical": t,
            "reason": f"信用倍率{_fmt_num(t.get('credit_ratio'), '倍')}(踏み上げ余地)",
            "detail": None,
            "url": None,
            "tiebreak": t.get("credit_ratio") if isinstance(t.get("credit_ratio"), (int, float)) else 999.0,
        })

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c["priority"], -c["tiebreak"]), reverse=True)
    return candidates[0]


def build_message(pick):
    t = pick["technical"] or {}
    name = pick["name"] or t.get("name") or ""
    code = pick["code"] or t.get("code") or ""
    price = t.get("price", "")
    change_pct = t.get("change_pct")
    change_str = f"{change_pct:+.2f}%" if isinstance(change_pct, (int, float)) else "―"

    lines = [
        "📡 先行シグナル銘柄(仕込み検討用)",
        f"{name}({code})" if code else f"{name}",
    ]
    if price:
        lines.append(f"現在値: {price} ({change_str})")
    lines.append(f"シグナル: {pick['reason']}")
    if pick.get("detail"):
        lines.append(f"詳細: {pick['detail']}")
    if pick.get("url"):
        lines.append(f"参照: {pick['url']}")

    lines.append(
        "※本通知は「市場がまだ十分に織り込んでいない可能性が相対的に高い」条件を"
        "機械的に抽出したものであり、翌日の上昇を保証するものではありません。"
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

    pick = pick_leading_signal_stock(root)
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
        log(f"LINE通知を送信しました(HTTP {status}): {pick['name']}(優先度{pick['priority']})")
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
