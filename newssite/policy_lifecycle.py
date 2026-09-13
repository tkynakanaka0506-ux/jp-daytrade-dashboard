#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同じ政策の続報(9/1発表→9/3補助金対象→9/8正式決定)に、安定した
policy_event_id を割り当てる(政策ライフサイクル管理)。

[FACTUAL LAYER] policy_event_id は「これは同じ政策インスタンスの更新か、
別の政策か」という識別情報でしかない。ここでの判定結果を理由に
score/direction/primary_theme を書き換えたり、更新回数ぶんスコアを
加算したりしない(束ねることと強く評価することは別処理のまま)。

継続(=同じ policy_event_id)とみなす条件(両方満たす必要がある):
  - 直近の更新から LIFECYCLE_WINDOW_DAYS 日以内
  - 政策成熟度(policy_maturity)が退行していない(検討→パブコメ→法案成立…
    と進む方向のみ。どちらかがNone=成熟度キーワード不一致なら、判定材料が
    無いだけなので継続を妨げない)
どちらか崩れれば「別の政策」とみなし、新しい policy_event_id を発行する。

既知の限界: 同じテーマ・同じキーワードで、成熟度が退行せず、かつ
LIFECYCLE_WINDOW_DAYS 以内に発生した「本当に別の政策」はキーワードだけの
判定エンジンでは区別できない。誤って束ねる可能性が残ることは認識した上で、
少なくとも「日付が離れている」「話が後戻りしている」という明確な別物の
シグナルがあるケースだけは確実に分離する、という保守的な設計にしている。
"""
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
REGISTRY_PATH = DATA_DIR / "policy_event_registry.json"

LIFECYCLE_WINDOW_DAYS = 30


def _load_registry(path=REGISTRY_PATH):
    if not path.exists():
        return {"active": {}, "_seq": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"active": {}, "_seq": {}}
    data.setdefault("active", {})
    data.setdefault("_seq", {})
    return data


def _save_registry(registry, path=REGISTRY_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=1)


def _days_between(day_a, day_b):
    fmt = "%Y-%m-%d"
    return abs((datetime.strptime(day_b, fmt) - datetime.strptime(day_a, fmt)).days)


def _mint_id(theme_id, day, seq):
    return f"{theme_id}-{day.replace('-', '')}-{seq:02d}"


def resolve_policy_event_id(registry, theme_id, matched_keyword, maturity_score, title, day):
    """1件のニュース(の代表テーマ)に対して policy_event_id を解決する。

    registry はこの関数が破壊的に更新する(呼び出し側は同じ registry を
    使い回すこと)。戻り値は (policy_event_id, is_update, first_seen)。
    """
    active = registry.setdefault("active", {})
    key = f"{theme_id}||{matched_keyword or ''}"
    entry = active.get(key)

    if entry:
        gap_days = _days_between(entry["last_seen"], day)
        regressed = (
            maturity_score is not None
            and entry.get("max_maturity") is not None
            and maturity_score < entry["max_maturity"]
        )
        if gap_days <= LIFECYCLE_WINDOW_DAYS and not regressed:
            entry["last_seen"] = day
            entry["update_count"] = entry.get("update_count", 1) + 1
            if maturity_score is not None:
                entry["max_maturity"] = max(entry.get("max_maturity") or 0, maturity_score)
            entry.setdefault("titles", []).append(title)
            entry["titles"] = entry["titles"][-10:]
            return entry["policy_event_id"], True, entry["first_seen"]

    seq = registry.setdefault("_seq", {})
    n = seq.get(theme_id, 0) + 1
    seq[theme_id] = n
    new_entry = {
        "policy_event_id": _mint_id(theme_id, day, n),
        "first_seen": day,
        "last_seen": day,
        "max_maturity": maturity_score,
        "update_count": 1,
        "titles": [title],
    }
    active[key] = new_entry
    return new_entry["policy_event_id"], False, new_entry["first_seen"]
