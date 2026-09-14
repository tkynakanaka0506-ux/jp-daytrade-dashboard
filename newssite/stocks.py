#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""銘柄マスタ(data/stocks.json)の読み込みと検索。

銘柄を増やしたいときは data/stocks.json に1件追加するだけでよい。
themes に付けたタグが data/rules.json の impacts[].themes と結びつく。
"""
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
STOCKS_PATH = DATA_DIR / "stocks.json"


class StockMaster:
    def __init__(self, stocks):
        self.stocks = stocks
        self.by_code = {s["code"]: s for s in stocks}
        self._by_theme = {}
        for s in stocks:
            for theme in s.get("themes", []):
                self._by_theme.setdefault(theme, []).append(s)
        # 社名・別名の長い順に並べた検索用リスト(部分一致の取りこぼしを減らす)
        names = []
        for s in stocks:
            for name in [s["name"]] + list(s.get("aliases", [])):
                if len(name) >= 2:
                    names.append((name, s))
        self._names = sorted(names, key=lambda x: -len(x[0]))

    def by_theme(self, theme):
        return list(self._by_theme.get(theme, []))

    def by_themes(self, themes, limit=None):
        """複数タグのいずれかに該当する銘柄を、重複を除いて返す。"""
        seen, out = set(), []
        for theme in themes:
            for s in self.by_theme(theme):
                if s["code"] in seen:
                    continue
                seen.add(s["code"])
                out.append(s)
        return out[:limit] if limit else out

    def find_in_text(self, text, limit=5):
        """見出しに直接登場する銘柄を返す(社名・別名・4桁コードの一致)。"""
        hits, seen = [], set()
        for name, stock in self._names:
            if stock["code"] in seen:
                continue
            if name in text:
                seen.add(stock["code"])
                hits.append(stock)
                if len(hits) >= limit:
                    return hits
        for code in re.findall(r"[<(【]?(\d{4})[>)】]?", text):
            stock = self.by_code.get(code)
            if stock and stock["code"] not in seen:
                seen.add(code)
                hits.append(stock)
                if len(hits) >= limit:
                    break
        return hits


def load(path=STOCKS_PATH):
    with open(path, encoding="utf-8") as f:
        return StockMaster(json.load(f))
