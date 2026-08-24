#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.json に書かれたRSS/RDFフィードを巡回し、
指定キーワードを含む記事だけを抽出してHTMLを生成するスクリプト。

- RSS 2.0 / RDF(RSS1.0) / Atom はすべて feedparser が自動判別する
- 既存の articles.json に追記していく形でデータを蓄積する(サイト側の
  フィードがローテーションで過去記事を落としても、一度拾った記事は残る)
- max_age_days を超えた古い記事は自動的に間引く
"""

import json
import hashlib
import datetime
import pathlib
import sys

import feedparser
from jinja2 import Environment, FileSystemLoader

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
DATA_PATH = ROOT / "data" / "articles.json"
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_PATH = ROOT / "docs" / "index.html"


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_existing_articles():
    if DATA_PATH.exists():
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_articles(articles):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def article_id(link, title):
    """記事の重複判定用ID(リンクがあればリンク優先)"""
    key = link or title
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def parse_published(entry):
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None)
        if val:
            return datetime.datetime(*val[:6], tzinfo=datetime.timezone.utc)
    return datetime.datetime.now(datetime.timezone.utc)


def matches_keywords(text, keywords, case_sensitive):
    if not case_sensitive:
        text = text.lower()
    for kw in keywords:
        target_kw = kw if case_sensitive else kw.lower()
        if target_kw in text:
            return True
    return False


def which_keywords(text, keywords, case_sensitive):
    hay = text if case_sensitive else text.lower()
    hits = []
    for kw in keywords:
        target_kw = kw if case_sensitive else kw.lower()
        if target_kw in hay:
            hits.append(kw)
    return hits


def fetch_feed(feed_conf, keywords, options):
    name = feed_conf["name"]
    url = feed_conf["url"]
    match_target = options.get("match_target", "title_and_summary")
    case_sensitive = options.get("case_sensitive", False)

    print(f"[fetch] {name}: {url}", file=sys.stderr)
    parsed = feedparser.parse(url)

    if parsed.bozo and not parsed.entries:
        print(f"  -> 取得/解析に失敗しました: {parsed.bozo_exception}", file=sys.stderr)
        return []

    results = []
    for entry in parsed.entries:
        title = getattr(entry, "title", "") or ""
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        link = getattr(entry, "link", "") or ""

        if match_target == "title_only":
            text = title
        elif match_target == "summary_only":
            text = summary
        else:
            text = f"{title} {summary}"

        if not matches_keywords(text, keywords, case_sensitive):
            continue

        results.append({
            "id": article_id(link, title),
            "source": name,
            "title": title.strip(),
            "summary": summary.strip(),
            "link": link,
            "published": parse_published(entry).isoformat(),
            "matched_keywords": which_keywords(text, keywords, case_sensitive),
        })

    print(f"  -> {len(results)}件がキーワードに一致", file=sys.stderr)
    return results


def merge_articles(existing, new_articles, max_age_days):
    by_id = {a["id"]: a for a in existing}
    for a in new_articles:
        by_id[a["id"]] = a  # 新しい情報で上書き(同じ記事の再取得に対応)

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=max_age_days)
    merged = [
        a for a in by_id.values()
        if datetime.datetime.fromisoformat(a["published"]) >= cutoff
    ]
    merged.sort(key=lambda a: a["published"], reverse=True)
    return merged


def render_html(articles, feeds, keywords, max_articles):
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("index_template.html")

    now = datetime.datetime.now(datetime.timezone.utc)
    html = template.render(
        articles=articles[:max_articles],
        total_count=len(articles),
        feeds=feeds,
        keywords=keywords,
        generated_at_utc=now.strftime("%Y-%m-%d %H:%M UTC"),
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[write] {OUTPUT_PATH}", file=sys.stderr)


def main():
    config = load_config()
    feeds = config.get("feeds", [])
    keywords = config.get("keywords", [])
    options = config.get("options", {})
    max_age_days = options.get("max_age_days", 14)
    max_articles = options.get("max_articles", 200)

    if not keywords:
        print("config.json の keywords が空です。1件以上指定してください。", file=sys.stderr)

    existing = load_existing_articles()

    all_new = []
    for feed_conf in feeds:
        try:
            all_new.extend(fetch_feed(feed_conf, keywords, options))
        except Exception as e:  # 1フィードの失敗で全体を止めない
            print(f"[error] {feed_conf.get('name')}: {e}", file=sys.stderr)

    merged = merge_articles(existing, all_new, max_age_days)
    save_articles(merged)
    render_html(merged, feeds, keywords, max_articles)


if __name__ == "__main__":
    main()
