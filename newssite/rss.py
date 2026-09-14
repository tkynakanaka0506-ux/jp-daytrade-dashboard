#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google News RSS の取得と正規化(標準ライブラリのみ)。"""
import hashlib
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from .config import JST, UA

try:  # certifi があれば使う(GitHub Actions 環境では通常不要)
    import certifi
    _CERTIFI = True
except Exception:  # pragma: no cover
    certifi = None
    _CERTIFI = False


def ssl_context():
    if _CERTIFI:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def log(msg):
    print(f"[rss] {msg}", flush=True)


def _parse_time(value):
    """RSS の pubDate を JST の datetime に変換する。失敗したら None。"""
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(JST)
    except Exception:
        return None


_SOURCE_SUFFIX = re.compile(r"\s*-\s*[^-]+$")


def _clean_title(title, source):
    """Google News の見出し末尾に付く「 - 媒体名」を取り除く。"""
    title = (title or "").strip()
    if source and title.endswith(f"- {source}"):
        return title[: -len(f"- {source}")].strip()
    if source and _SOURCE_SUFFIX.search(title):
        head = _SOURCE_SUFFIX.sub("", title).strip()
        if len(head) >= 8:
            return head
    return title


def news_id(title, url):
    key = (title or "") + "|" + (url or "")
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def fetch(query, category="market", base_weight=1, limit=12, hl="ja", gl="JP", ceid="JP:ja", timeout=20):
    """1クエリ分の記事リストを返す。失敗時は空リスト(パイプラインは止めない)。"""
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(query)
        + f"&hl={hl}&gl={gl}&ceid={ceid}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as res:
            raw = res.read()
        root = ET.fromstring(raw)
    except Exception as e:
        log(f"取得失敗 query={query!r}: {e}")
        return []

    items = []
    for node in root.findall("./channel/item")[:limit]:
        link = (node.findtext("link") or "").strip()
        src_el = node.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""
        title = _clean_title(node.findtext("title"), source)
        if not title or not link:
            continue
        published = _parse_time(node.findtext("pubDate"))
        items.append({
            "id": news_id(title, link),
            "title": title,
            "url": link,
            "source": source or "Google News",
            "published": published,
            "feed_query": query,
            "feed_category": category,
            "feed_weight": base_weight,
        })
    log(f"{len(items)}件 取得 query={query!r}")
    return items


def _normalize(title):
    """比較用に記号・空白を落とした文字列を作る。"""
    return re.sub(r"[\s　【】「」『』\[\]()()、。,\.\-—–:：/|・\"\'%％]", "", title)


def _bigrams(text):
    return {text[i:i + 2] for i in range(len(text) - 1)} or {text}


def _similarity(a, b):
    """文字bigramのJaccard係数。同じ出来事を別媒体が報じた見出しは高くなる。"""
    sa, sb = _bigrams(a), _bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# この値以上に似ている、または先頭がこの文字数だけ一致する見出しは
# 「同じ話題」として1件にまとめる
SIMILARITY_THRESHOLD = 0.42
COMMON_PREFIX_CHARS = 10


def _same_topic(a, b):
    if a[:COMMON_PREFIX_CHARS] and a[:COMMON_PREFIX_CHARS] == b[:COMMON_PREFIX_CHARS]:
        return True
    return _similarity(a, b) >= SIMILARITY_THRESHOLD


def collect(feeds, per_feed_limit=12, max_age_hours=48):
    """全フィードを取得し、同じ話題を束ねて1リストにする。

    同じ出来事が複数媒体で報じられている場合は related にまとめ、
    報道の広がり(related の数)を後段の重要度計算で使う。
    """
    now = datetime.now(JST)
    merged = []
    for query, category, weight in feeds:
        for item in fetch(query, category, weight, limit=per_feed_limit):
            if item["published"] and now - item["published"] > timedelta(hours=max_age_hours):
                continue
            norm = _normalize(item["title"])
            base = None
            for candidate in merged:
                if _same_topic(norm, candidate["_norm"]):
                    base = candidate
                    break
            if base is None:
                item["_norm"] = norm
                item["related"] = []
                item["feed_categories"] = [item["feed_category"]]
                merged.append(item)
                continue
            if item["url"] != base["url"] and all(r["url"] != item["url"] for r in base["related"]):
                base["related"].append({
                    "title": item["title"], "url": item["url"], "source": item["source"],
                })
            # 別カテゴリのフィードにも載った = 話題の広がりが大きい
            base["feed_weight"] = max(base["feed_weight"], item["feed_weight"])
            if item["feed_category"] not in base["feed_categories"]:
                base["feed_categories"].append(item["feed_category"])

    for item in merged:
        item.pop("_norm", None)
    return merged
