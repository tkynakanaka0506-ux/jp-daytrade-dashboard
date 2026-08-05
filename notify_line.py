#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data.json の内容から「本日の最注力銘柄」を1銘柄だけ機械的に選び、LINE Messaging API の
プッシュメッセージで通知するスクリプト。Main.java(データ収集) → news_analyzer.py(Gemini補完)
→ render_dashboard.py(HTML生成) のあとに実行する想定。

選定条件(いずれかを満たす銘柄を候補とする):
A) ダブルシグナル: growth_candidates 側で double_signal=true になっている銘柄
(「業績予想の上方修正」と「決算」の開示が同一社で重なっているケース)。
B) 出来高急増+好材料: technical 側の volume_ratio が5日平均の2倍以上(volume_surge=true)、
かつ同じ銘柄が growth_candidates(好材料のみを抽出したTDnet開示)にも登場している。

候補が複数ある場合は、以下の優先順位で1銘柄だけに絞る:
1) 条件A・B両方を満たす銘柄
2) 条件A(ダブルシグナル)のみ
3) 条件B(出来高急増+好材料)のみ
同順位内では technical.change_pct(値上がり率)が大きい銘柄を優先する。

注意:
- LINE Notify は2025年3月末でサービス終了しているため、後継の LINE Messaging API
(チャネルアクセストークン + 送信先user/group ID)のプッシュメッセージを使う。
- LINE_CHANNEL_ACCESS_TOKEN / LINE_USER_ID が未設定、またはAPI呼び出しが失敗した場合は、
既存のパイプラインを止めないよう、ログを出すだけで正常終了する(exit code 0)。
- 同じ銘柄への通知が15分間隔の自動実行のたびに重複して飛ばないよう、data.json内の
line_notify_last(当日日付+銘柄コード)で簡易的な重複送信防止を行う。

2026-08-05: 不具合修正。technical(固定20銘柄の主力ウォッッリスト)を起点に
growth_candidates(TDnetの好材料開示から機械的に抽出した、ウォッチリストとは別の
中小型株中心の銘柄群)を突き合わせていたため、条件A(ダブルシグナル)ですら
「growth_candidates側でdouble_signal=trueだが、たまたまウォッチリスト20銘柄には
含まれない銘柄」を一切拾えず、実質的に通知条件を満たす銘柄が現れない状態になっていた
(data.json の line_notify_last が一度も設定されたことがなかったことで判明)。
起点を growth_candidates 側に変え、technicalとの一致は「あれば価格等を補完情報として使う」
任意情報に変更した。

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

def pick_most_important_stock(root):
    technical = root.get("technical", [])
    growth = root.get("growth_candidates", [])
    technical_by_name = {t.get("name"): t for t in technical if t.get("name")}

    candidates = []
    for g in growth:
        name = g.get("company")
        if not name:
            continue
        # ウォッチリスト20銘柄に同じ会社があれば、価格・出来高等の補完情報として使う
        # (無ければ None のままでよい。条件A自体はgrowth_candidatesだけで判定できる)。
        t = technical_by_name.get(name)
        has_double_signal = bool(g.get("double_signal"))
        has_volume_surge_and_news = bool(t and t.get("volume_surge"))

        if not (has_double_signal or has_volume_surge_and_news):
            continue

        # 優先度: 両条件を満たす(2) > ダブルシグナルのみ(1) > 出来高急増+好材料のみ(0)
        if has_double_signal and has_volume_surge_and_news:
            priority = 2
        elif has_double_signal:
            priority = 1
        else:
            priority = 0

        change_pct = t.get("change_pct") if t else None
        if not isinstance(change_pct, (int, float)):
            change_pct = -999.0

        candidates.append({
            "priority": priority,
            "change_pct": change_pct,
            "technical": t,
            "growth": g,
            "has_double_signal": has_double_signal,
            "has_volume_surge_and_news": has_volume_surge_and_news,
        })

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c["priority"], c["change_pct"]), reverse=True)
    return candidates[0]

def build_message(pick):
    t = pick["technical"] or {}
    g = pick["growth"]
    name = t.get("name") or g.get("company", "")
    code = t.get("code", "")
    price = t.get("price", "")
    change_pct = t.get("change_pct")
    change_str = f"{change_pct:+.2f}%" if isinstance(change_pct, (int, float)) else "―"

    reasons = []
    if pick["has_double_signal"]:
        reasons.append("ダブルシグナル(決算+業績上方修正が重複)")
    if pick["has_volume_surge_and_news"]:
        ratio = t.get("volume_ratio")
        ratio_str = f"(出来高{ratio:.1f}倍)" if isinstance(ratio, (int, float)) else ""
        reasons.append(f"出来高急増{ratio_str}+好材料")
    reason_line = "・".join(reasons)

    lines = [
        "📌 本日の最注力銘柄",
        f"{name}({code})" if code else f"{name}",
    ]
    if price:
        lines.append(f"株価: {price} ({change_str})")
    lines.append(f"理由: {reason_line}")
    if g and g.get("title"):
        lines.append(f"材料: {g['title']}")
    theme = t.get("theme")
    if theme:
        lines.append(f"関連テーマ: {theme}")

    lines.append("※本通知は機械的な条件抽出であり、投資判断は自己責任でお願いします。")
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

    pick = pick_most_important_stock(root)
    if not pick:
        log("最注力銘柄の条件を満たす銘柄が無いため、通知はスキップします。")
        return

    t = pick["technical"]
    g = pick["growth"]
    # 重複送信防止キー: ウォッチリストの証券コードがあればそれを、無ければ会社名を使う。
    dedup_key = (t.get("code") if t else None) or g.get("company", "")
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
    last = root.get("line_notify_last") or {}
    if last.get("date") == today_str and last.get("code") == dedup_key:
        log(f"本日は既に{dedup_key}を通知済みのため、重複通知をスキップします。")
        return

    message = build_message(pick)
    try:
        status = send_line_push(token, user_id, message)
        sent_name = (t.get("name") if t else None) or g.get("company", "")
        log(f"LINE通知を送信しました(HTTP {status}): {sent_name}")
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
