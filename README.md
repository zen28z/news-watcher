# news-watcher

日本の各ニュースサイトのRSS/RDFフィードを巡回し、指定キーワードを含む記事だけを
抽出してHTMLページとして公開する、GitHub Actions製の自動更新ツールです。

## 仕組み

1. `config.json` に登録したRSS/RDF/AtomフィードURLを `scripts/fetch_news.py` が巡回
2. タイトル・本文にキーワードが含まれる記事だけを抽出
3. 過去に拾った記事は `data/articles.json` に蓄積(フィードが古い記事を落としても消えない)
4. `docs/index.html` を生成
5. GitHub Actionsが10分おきに1〜4を自動実行し、変更があればcommit & push
6. GitHub Pagesで `docs/` フォルダを公開するとURLが発行される

## セットアップ

1. このリポジトリをGitHubに作成してpush
2. リポジトリの Settings → Pages で
   - Source: `Deploy from a branch`
   - Branch: `main` / フォルダ: `/docs`
   に設定 → 数分後に公開URLが発行されます
3. Settings → Actions → General → Workflow permissions で
   `Read and write permissions` にチェック(自動commitに必要)
4. `config.json` を編集して、フィードとキーワードを登録

```json
{
  "feeds": [
    { "name": "NHKニュース 主要", "url": "https://www.nhk.or.jp/rss/news/cat0.xml" },
    { "name": "○○新聞 RDF", "url": "https://example.com/rss.rdf" }
  ],
  "keywords": ["キーワード1", "キーワード2"],
  "options": {
    "match_target": "title_and_summary",
    "case_sensitive": false,
    "max_articles": 200,
    "max_age_days": 14
  }
}
```

- `match_target`: `title_and_summary` / `title_only` / `summary_only`
- RSS 2.0でもRDF(RSS 1.0)でもAtomでも、URLを登録するだけで自動判別されます
  (`feedparser` が形式を吸収するため、RDFかRSSかを区別するコードは不要です)

5. commit & push すると `push` トリガーで即座に1回実行されます
6. 手動で今すぐ試したい場合は Actions タブ → `Update news watcher` →
   `Run workflow` から手動実行できます

## ローカルでのテスト

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
open docs/index.html   # or ブラウザで直接開く
```

## 注意点

- GitHub Actionsの `schedule` は正確に10分おきとは限らず、負荷状況により
  数分〜十数分遅延することがあります(GitHub側の仕様上の制約です)
- 各ニュースサイトの利用規約・robots.txtの範囲内でご利用ください
- 記事本文の全文転載は著作権上問題になり得るため、本ツールはタイトルと
  要約(フィードのsummary)のみを表示する設計にしています
