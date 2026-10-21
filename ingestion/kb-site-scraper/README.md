# Contoso KB Site Scraper

Scrapes every article on https://help.contoso.example (Confluence) into a local library:
text, dropdown (expand) sections, tables, code samples, images, videos, attached files,
and a full-page screenshot with every dropdown opened.

Rebuilt from the KB part of `C:\Knowledge Base\scraper` (v4.0.4). The ticket scrapers were not copied.

## Run

Double-click **`Run KB Scraper.bat`**. Requires Python 3.11+ and Google Chrome (Edge is used as a fallback).

1. Tick the spaces to scrape in the left panel (all are ticked by default).
2. Press **Start scrape**. The site is re-checked first, so new articles and spaces are picked up.
3. Watch the **Articles** table. Every article shows its status, the files, dropdowns,
   code blocks and images captured against what the page source contains, and any problem.
   The **Issues** tab lists every failure, warning and audit finding.

| Button | What it does |
|---|---|
| Start scrape | New run: re-discover the site, then scrape every article of the ticked spaces (always a fresh copy). |
| Resume last run | Continue an interrupted run (Stop, crash, closed window, power loss). |
| Retry problems | Re-scrape the last run's failed and warning articles. |
| Pause / Stop | Pause between articles / stop now (in-progress articles go back to pending). |
| Audit library | Compare the live site with the disk: missing articles, warnings, stale folders. |

Right-click an article to open its folder, the Markdown, or the live page, or to retry it.

## Output layout

```
library/
  index.json, index.md                    every article, grouped product > space > tree
  tradedesk/finance/_space.json            the space's article list
  tradedesk/finance/Finance Home/          one folder per article, mirroring the page tree
      article.json                        structured data (see below)
      article.md                          readable Markdown with local image links
      screenshot.png                      (or screenshot_partNN.png for very long pages)
      images/                             every image attachment + images shown from other pages
      attachments/                        videos (mp4), csv, xlsx, ...
      Bank Master/                        child article folders
```

`article.json` has the page id, URL, breadcrumb, version, last-updated date and labels. Under
`content` it holds the markdown, plain text, headings, dropdowns (title + body), code blocks
(title, language, code), tables (headers, rows, records), panels and links. Under `media` it
lists images, videos, files and embeds with their local paths, plus `attachments` and
`verification` (expected vs captured counts, issues, notes).

## How completeness is checked

* **Discovery** lists every space and every page/blog post through the REST API, so nothing
  depends on site navigation.
* **Per article**, the counts of dropdowns, code blocks, images and videos captured are compared
  with the page's source (Confluence storage format). Any shortfall, failed download or
  failed screenshot marks the article as a **Warning** with the reason.
* Downloads are written atomically and checked against the server's Content-Length.
* Each article gets 3 attempts. If many articles fail in a row, the run pauses with an
  alert rather than burning through the queue.
* Every status change is journaled to `state/runs/<run id>/`, so a crash loses nothing.

## Files

* `state/settings.json`: workers, screenshots, output folder
* `state/sitemap.json`: last discovered site map
* `state/runs/`: run journals
* `state/logs/`: full logs

Command line (optional): `venv\Scripts\python -m kbscraper.cli --spaces Functions,SA` (`--resume`, `--retry`).
Tests: `venv\Scripts\python -m pytest tests`.

---

# Contoso REST API Scraper

Scrapes every page of the REST API developer docs at https://apidocs.contoso.example
(hosted on Theneo) into `REST API\`. For each endpoint it captures the description, every
header, path, query and body parameter, every response example (fully expanded), the code
snippet in all 8 languages, the "Try it" API Explorer (capture only), and screenshots.

## Run

Double-click **`Run REST API Scraper.bat`**. The window and its buttons work the same way as the
KB scraper's, with the site's 25 **sections** in place of spaces.

**Safety:** the scraper never sends an API request. Every browser it drives only lets through
GET requests to the docs site and the static files those pages need. Everything else is blocked,
including anything aimed at `apisandbox.contoso.example` or any other Contoso API host, and the
explorer's Run button is never clicked. If a page ever tries to reach an API host, that page is
flagged with a `SAFETY:` issue.

**Rate limit:** the site briefly refuses a computer that loads pages too fast (HTTP 403 for a few
minutes). The scraper keeps at least `min_interval_s` (2 s) between page loads, and caches the
site's static files in memory. When the site refuses anyway, the counts line shows
**COOLING DOWN**: every worker waits, the site is re-checked every 30 s, and the run continues
on its own. Pages caught by the limit are queued again without using up an attempt.

## Output layout

```
REST API/
  index.json, index.md                every page grouped by section, with status
  _site/menu.json, llms.txt, discovery_report.json
  13 Deal/                            sections numbered in menu order
    page.json, page.md, _section.json, screenshot.png
    Create Web Deal (with payments and settlements)/
      page.json        structured data: endpoint, parameters (nested), responses, snippets,
                       tryit, raw Theneo data, verification (expected vs found, issues)
      page.md          readable Markdown: description, parameter tables, responses, snippets
      source.md        Theneo's own Markdown export
      page.html        the endpoint's rendered HTML
      screenshot.png   the endpoint with everything expanded (_partNN for very tall ones)
      snippets/        curl.sh ruby.rb python.py php.php java.java nodejs.js go.go dotnet.cs
      responses/       200.json, 400.json, ...
      tryit/           tryit.json (fields + defaults), request_body.json, snippets/,
                       tryit.png (form view), tryit_code.png (code view)
      images/
```

## Completeness checks

A page is marked **Warning** when any of these fall short of what the page's own data says
exists: snippets in all 8 languages, one example per documented response status, the Try-it
page with every header field and the request body, downloaded images, or screenshots. An
audit after every run compares the live menu with the files on disk.

Settings, run journals and logs are kept in `state\rest\`. Command line:
`venv\Scripts\python -m restscraper.cli --sections deal,bank` (or `--only <slug>`, `--resume`,
`--retry`, `--out DIR`). Tests: `venv\Scripts\python -m pytest tests`.
