#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google News RSS の取得と正規化(標準ライブラリのみ)。"""
import concurrent.futures
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


def _parse_rdf_date(value):
    """RSS1.0(RDF)の dc:date (ISO8601) を JST datetime に変換する。"""
    if not value:
        return None
    try:
        v = value.strip()
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        return datetime.fromisoformat(v).astimezone(JST)
    except Exception:
        return None


def fetch_direct(url, source_label, category="japan", base_weight=2, limit=15, timeout=20):
    """省庁など一次情報のRSS/RDFフィードをURL指定で直接取得する。

    Google News 経由(報道機関が書き終えるまで待つ)より速く、
    発表そのものを最速で拾うための経路。RSS2.0とRSS1.0(RDF)の両方に対応する。
    失敗時は空リスト(パイプラインは止めない)。
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as res:
            raw = res.read()
        try:
            root = ET.fromstring(raw)
        except (ET.ParseError, ValueError):
            # Shift_JIS等、標準パーサーが直接扱えないエンコーディングで配信している
            # サイトがある(総務省など)。宣言されたエンコーディングで読み直す。
            m = re.search(rb'encoding=["\']([\w-]+)["\']', raw[:200])
            enc = m.group(1).decode("ascii", "ignore") if m else "shift_jis"
            text = raw.decode(enc, errors="replace")
            # 宣言されたエンコーディングのまま re-encode すると矛盾するので UTF-8 に書き換える
            text = re.sub(r'encoding=["\'][\w-]+["\']', 'encoding="UTF-8"', text, count=1)
            root = ET.fromstring(text.encode("utf-8"))
    except Exception as e:
        log(f"直接取得失敗 url={url!r}: {e}")
        return []

    RSS1 = "{http://purl.org/rss/1.0/}"
    DC = "{http://purl.org/dc/elements/1.1/}"
    ATOM = "{http://www.w3.org/2005/Atom}"
    nodes = root.findall("./channel/item")
    if not nodes:
        # RSS1.0/RDF は item が channel の外、ルート直下の兄弟要素になる
        nodes = root.findall(f"./{RSS1}item") or root.findall("./item")
    if not nodes:
        # Atom は entry が feed 直下の兄弟要素になる
        nodes = root.findall(f"./{ATOM}entry") or root.findall("./entry")

    def _atom_link(node):
        """Atomの<link href="...">はテキストでなく属性にURLが入る。"""
        candidates = node.findall(f"{ATOM}link") + node.findall("link")
        for el in candidates:
            if el.get("href") and el.get("rel", "alternate") == "alternate":
                return el.get("href").strip()
        for el in candidates:
            if el.get("href"):
                return el.get("href").strip()
        return ""

    items = []
    for node in nodes[:limit]:
        title = (
            node.findtext("title") or node.findtext(f"{RSS1}title") or node.findtext(f"{ATOM}title") or ""
        ).strip()
        link = (node.findtext("link") or node.findtext(f"{RSS1}link") or "").strip() or _atom_link(node)
        if not title or not link:
            continue
        published = (
            _parse_time(node.findtext("pubDate"))
            or _parse_rdf_date(node.findtext(f"{DC}date"))
            or _parse_rdf_date(node.findtext(f"{ATOM}updated"))
            or _parse_rdf_date(node.findtext(f"{ATOM}published"))
        )
        items.append({
            "id": news_id(title, link),
            "title": title,
            "url": link,
            "source": source_label,
            "published": published,
            "feed_query": source_label,
            "feed_category": category,
            "feed_weight": base_weight,
        })
    log(f"{len(items)}件 取得(直接) source={source_label!r}")
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


def collect(feeds, direct_feeds=None, per_feed_limit=12, max_age_hours=48, max_workers=8):
    """全フィードを取得し、同じ話題を束ねて1リストにする。

    feeds: Google News検索クエリ (query, category, weight) のリスト。
    direct_feeds: 省庁など一次情報のRSS/RDFを直接購読する (url, source_label, category, weight) のリスト。
                  一次情報を先にマージすることで、後から来る同一トピックの報道記事は
                  「related(関連報道)」側に回り、一次情報そのものが主表示になる。
    フィードごとの取得はネットワーク待ちが支配的なので、スレッドで並列に投げて
    合計の待ち時間を短縮する(件数・除外条件など結果自体は逐次実行と同じ)。
    """
    now = datetime.now(JST)
    feeds = list(feeds)
    direct_feeds = list(direct_feeds or [])
    results = [[] for _ in feeds]
    direct_results = [[] for _ in direct_feeds]
    total = len(feeds) + len(direct_feeds)
    if total:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(max_workers, total))) as pool:
            future_to_slot = {}
            for idx, (query, category, weight) in enumerate(feeds):
                fut = pool.submit(fetch, query, category, weight, per_feed_limit)
                future_to_slot[fut] = ("query", idx, query)
            for idx, (url, label, category, weight) in enumerate(direct_feeds):
                fut = pool.submit(fetch_direct, url, label, category, weight, per_feed_limit)
                future_to_slot[fut] = ("direct", idx, label)
            for future in concurrent.futures.as_completed(future_to_slot):
                kind, idx, name = future_to_slot[future]
                try:
                    result = future.result()
                except Exception as e:
                    log(f"取得失敗(並列) source={name!r}: {e}")
                    result = []
                if kind == "query":
                    results[idx] = result
                else:
                    direct_results[idx] = result

    merged = []

    def _merge_one(item):
        if item["published"] and now - item["published"] > timedelta(hours=max_age_hours):
            return
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
            return
        if item["url"] != base["url"] and all(r["url"] != item["url"] for r in base["related"]):
            base["related"].append({
                "title": item["title"], "url": item["url"], "source": item["source"],
            })
        # 別カテゴリのフィードにも載った = 話題の広がりが大きい
        base["feed_weight"] = max(base["feed_weight"], item["feed_weight"])
        if item["feed_category"] not in base["feed_categories"]:
            base["feed_categories"].append(item["feed_category"])

    # 一次情報(省庁RSS)を先にマージし、後続の同一トピック報道は related に回す
    for idx in range(len(direct_feeds)):
        for item in direct_results[idx]:
            _merge_one(item)
    for idx in range(len(feeds)):
        for item in results[idx]:
            _merge_one(item)

    for item in merged:
        item.pop("_norm", None)
    return merged
