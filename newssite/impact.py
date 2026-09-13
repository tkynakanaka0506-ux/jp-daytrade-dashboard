#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""見出しテキストから「重要度・カテゴリ・影響銘柄」を判定するルールエンジン。

LLM を使わずここだけで完結して動くのが前提(APIキーが無くてもサイトは成立する)。
判定の中身を変えたいときは data/rules.json を編集する。
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
RULES_PATH = DATA_DIR / "rules.json"

DIRECTION_LABEL = {
    "positive": "追い風",
    "negative": "逆風",
    "watch": "注目",
}

STRENGTH_ORDER = {"大": 3, "中": 2, "小": 1}


class Rules:
    def __init__(self, raw):
        self.raw = raw
        self.themes = raw.get("themes", [])
        self.categories = raw.get("categories", [])
        self.category_label = {c["id"]: c["label"] for c in self.categories}
        self.category_emoji = {c["id"]: c.get("emoji", "📰") for c in self.categories}
        self.importance_keywords = raw.get("importance_keywords", [])
        self.noise_keywords = raw.get("noise_keywords", [])
        self.positive_words = raw.get("positive_words", [])
        self.negative_words = raw.get("negative_words", [])


def load(path=RULES_PATH):
    with open(path, encoding="utf-8") as f:
        return Rules(json.load(f))


def _keyword_hit(text, keyword):
    """キーワードは半角スペース区切りで AND 条件として扱う。"""
    parts = [p for p in keyword.split(" ") if p]
    return all(p in text for p in parts)


def match_themes(text, rules):
    """見出しに該当するテーマ定義を返す。"""
    hits = []
    for theme in rules.themes:
        if any(_keyword_hit(text, ex) for ex in theme.get("exclude", [])):
            continue
        if any(_keyword_hit(text, kw) for kw in theme.get("keywords", [])):
            hits.append(theme)
    return hits


def is_noise(text, rules):
    return any(w in text for w in rules.noise_keywords)


def headline_sentiment(text, rules):
    """見出し単体の方向感。戻り値は positive / negative / watch。"""
    pos = sum(1 for w in rules.positive_words if w in text)
    neg = sum(1 for w in rules.negative_words if w in text)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "watch"


def score_importance(item, matched_themes, rules):
    """重要度(1〜5)とその根拠テキストを返す。"""
    text = item["title"]
    score = float(item.get("feed_weight", 1))
    reasons = []

    for entry in rules.importance_keywords:
        hit = [w for w in entry["words"] if w in text]
        if hit:
            score += entry["score"]
            reasons.append(f"重要語「{hit[0]}」")
            break

    if matched_themes:
        best = max(t.get("weight", 1) for t in matched_themes)
        score += best
        reasons.append(f"影響テーマ「{matched_themes[0]['label']}」に該当")

    related = len(item.get("related", []))
    if related:
        score += min(related, 3)
        reasons.append(f"{related + 1}媒体が報道")

    feed_cats = len(item.get("feed_categories", []))
    if feed_cats > 1:
        score += 1
        reasons.append("複数分野にまたがる話題")

    # 5段階に写像する(しきい値は経験則。data/rules.json の weight で調整可)
    if score >= 10:
        stars = 5
    elif score >= 8:
        stars = 4
    elif score >= 6:
        stars = 3
    elif score >= 4:
        stars = 2
    else:
        stars = 1
    return stars, "・".join(reasons) if reasons else "一般的な市況ニュース"


def _impact_entry(stock, direction, strength, reason, origin, theme_label=""):
    return {
        "code": stock["code"],
        "name": stock["name"],
        "sector": stock.get("sector", ""),
        "direction": direction,
        "direction_label": DIRECTION_LABEL.get(direction, "注目"),
        "strength": strength,
        "reason": reason,
        "theme": theme_label,
        "origin": origin,
    }


def affected_stocks(item, matched_themes, rules, master, max_items=8):
    """ニュース1件に対する影響銘柄リストを作る。

    1) 見出しに社名・証券コードが直接出ている銘柄(当事者)
    2) 該当テーマから波及する銘柄(rules.json の impacts)
    の順で並べ、同じ銘柄が重複した場合は当事者側を優先する。
    """
    text = item["title"]
    results = {}

    direct_direction = headline_sentiment(text, rules)
    for stock in master.find_in_text(text, limit=4):
        reason = {
            "positive": "見出しで名指しされている当事者。内容は業績にプラスに働きうる材料",
            "negative": "見出しで名指しされている当事者。内容は業績にマイナスに働きうる材料",
            "watch": "見出しで名指しされている当事者。まず株価が反応しやすい",
        }[direct_direction]
        results[stock["code"]] = _impact_entry(
            stock, direct_direction, "大", reason, "direct", "当事者"
        )

    # ルールごとの候補を集め、ラウンドロビンで採用する。
    # (最初のルールだけで枠を使い切って「追い風の銘柄しか出ない」のを避けるため)
    buckets = []
    for theme in matched_themes:
        for rule in theme.get("impacts", []):
            targets = []
            for code in rule.get("codes", []):
                s = master.by_code.get(code)
                if s:
                    targets.append(s)
            targets += master.by_themes(rule.get("themes", []), limit=rule.get("limit", 4))
            bucket = [
                _impact_entry(
                    stock,
                    rule.get("direction", "watch"),
                    rule.get("strength", "中"),
                    rule.get("reason", ""),
                    "rule",
                    theme["label"],
                )
                for stock in targets[: rule.get("limit", 4)]
            ]
            if bucket:
                buckets.append(bucket)

    depth = 0
    while buckets and len(results) < max_items:
        progressed = False
        for bucket in buckets:
            if depth >= len(bucket):
                continue
            progressed = True
            entry = bucket[depth]
            if entry["code"] not in results and len(results) < max_items:
                results[entry["code"]] = entry
        if not progressed:
            break
        depth += 1

    ordered = sorted(
        results.values(),
        key=lambda r: (
            0 if r["origin"] == "direct" else 1,
            -STRENGTH_ORDER.get(r["strength"], 1),
        ),
    )
    return ordered[:max_items]


def pick_category(item, matched_themes, rules):
    """テーマが決まればそのカテゴリ、無ければフィード側のカテゴリを使う。"""
    if matched_themes:
        cat = matched_themes[0].get("category")
        if cat in rules.category_label:
            return cat
    cat = item.get("feed_category", "market")
    return cat if cat in rules.category_label else "market"
