#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重要ニュース × 影響銘柄サイトのビルドスクリプト(このリポジトリのメイン処理)。

  python3 build_news_site.py                 # ニュース収集 → news.json → index.html
  python3 build_news_site.py --no-llm        # 生成AIの補強を使わない(ルール判定のみ)
  python3 build_news_site.py --render-only   # 既存の news.json から index.html だけ作り直す
  python3 build_news_site.py --sample        # ネット接続なしでサンプルデータを使って確認する

環境変数(任意):
  GEMINI_API_KEY / GROQ_API_KEY … あれば見出しの要約・波及コメント・追加銘柄を補強する。
                                   無くてもキーワードルールだけでサイトは生成される。
"""
import argparse
import json
import sys
from pathlib import Path

from newssite import analyze, render

BASE_DIR = Path(__file__).resolve().parent


def parse_args(argv):
    p = argparse.ArgumentParser(description="重要ニュース×影響銘柄サイトを生成する")
    p.add_argument("--news-json", default=str(BASE_DIR / "news.json"), help="ニュースデータの入出力先")
    p.add_argument("--out", default=str(BASE_DIR / "index.html"), help="生成するHTMLの出力先")
    p.add_argument("--data-json", default=str(BASE_DIR / "data.json"), help="市況ヘッダーに使う既存data.json")
    p.add_argument("--no-llm", action="store_true", help="生成AIによる補強を使わない")
    p.add_argument("--render-only", action="store_true", help="収集せず既存news.jsonからHTMLだけ作る")
    p.add_argument("--sample", action="store_true", help="サンプルデータで生成する(ネット接続不要)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    news_json = Path(args.news_json)
    out_html = Path(args.out)

    if args.render_only:
        if not news_json.exists():
            print(f"[ERROR] {news_json} がありません。先に収集を実行してください。", file=sys.stderr)
            return 1
        render.load_and_render(news_json, out_html)
        print(f"[OK] {out_html} を再生成しました。")
        return 0

    if args.sample:
        from newssite.sample import sample_data
        data = sample_data()
    else:
        data = analyze.build(data_json_path=args.data_json, use_llm=not args.no_llm)

    with open(news_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    render.render_to_file(data, out_html)

    print(f"[OK] ニュース {data['counts']['news']}件 / 影響銘柄 {data['counts']['stocks']}銘柄")
    print(f"[OK] {news_json} と {out_html} を生成しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
