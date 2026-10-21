# REST API Docs Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `restscraper` package and `.bat` launcher in this project. It scrapes every page of
https://apidocs.contoso.example into `REST API\`: structured data, the Markdown export,
the rendered content, the 8-language code snippets, the fully expanded response examples, a
capture-only "Try it" record, and screenshots.

**Architecture:** Discovery is HTTP-only: it parses Theneo's `__NEXT_DATA__` menu. Each page is
captured in one dedicated Chrome per worker. Every browser context goes through an allowlist request
guard, so nothing can reach an API host. The engine, run journal, run control and GUI follow
`kbscraper`. `state.RunState`, `control.RunControl`, `paths`, `gui.theme` and `gui.log_pane` are
reused unchanged. The window, model and threads are adapted copies, so the KB scraper's files are not
modified.

**Tech Stack:** Python 3.11+, Playwright (Chrome channel), httpx, BeautifulSoup/lxml, PySide6, pytest.
These are already in `requirements.txt`.

**Spec:** `docs/superpowers/specs/2026-10-21-rest-api-scraper-design.md`

## Global Constraints

- Base URL is `https://apidocs.contoso.example`. Output defaults to `<project>\REST API`.
  State goes in `<project>\state\rest\` (runs, logs, settings.json, sitemap.json).
- Snippet languages, in this order: cURL, Ruby, Python, PHP, Java, Node.js, Go, .NET. The files are
  `curl.sh ruby.rb python.py php.php java.java nodejs.js go.go dotnet.cs`.
- Allowed requests are **GET only**, to `apidocs.contoso.example`, `theneo-prod-public.s3*.amazonaws.com`,
  `fonts.googleapis.com` and `fonts.gstatic.com`. Everything else is aborted and counted. A hit on
  any `*.contoso.example` host, or any non-docs `contoso` host, is recorded as a safety issue on the page.
- Never click Run, Send or Try buttons in the explorer. The explorer page is opened by direct URL:
  `/api-runner/contoso/contoso-rest-api-1/<slug>`.
- The browser user agent replaces `HeadlessChrome` with `Chrome`. Without this, the site returns 403.
- The site rate-limits by IP. A 403 page or response means "blocked". The run **cools down**: it
  pauses all workers and probes `/llms.txt` until it gets a 200, without spending attempts. It is
  not a failure. All page navigations go through one shared minimum interval
  (`Settings.min_interval_s`, default 2.0).
- Per page files: `page.json page.md source.md page.html screenshot.png images/ snippets/ responses/ tryit/`.
  Group pages (sections) also write `_section.json`.
- Example values are saved verbatim. The scraper never enters or stores credentials.

## Review Focus

1. **Rate-limit block mid-run**: workers must not burn retries or mark pages failed while the site
   returns 403. Expect a cooldown and an automatic continue. Covered by `test_engine_cooldown_on_blocked`.
2. **Page not in the first render** (the virtualized list): the target block may still be a 44 px
   placeholder. Expect scroll-into-view and a wait for the request card, and a warning if it never
   renders. Covered by the live smoke test in Task 7.
3. **Duplicate endpoint names in a section**, such as "Reset Password (via web user)" twice: folders
   must not collide. Covered by `test_folders_unique_for_duplicate_names`.
4. **llms.txt slugs that differ from the menu** (renamed pages): these must not be reported as
   missing when the old slug maps to the same section id in `documentMenu.slugs`. Covered by
   `test_crosscheck_uses_slug_aliases`.
5. **Endpoints with no responses or no body**: expect no false warnings. Expected counts come from
   the page's own data. Covered by `test_verify_counts_no_responses`.

---

### Task 1: Settings, Theneo data parsing, request guard

**Files:**
- Create: `restscraper/__init__.py` (`__version__ = "1.0.0"`), `restscraper/settings.py`, `restscraper/theneo.py`, `restscraper/guard.py`
- Test: `tests/rest/test_theneo.py`, `tests/rest/test_guard.py`, fixture `tests/rest/fixtures/page.html` (trimmed real page, sample tokens replaced)

**Interfaces (produces):**
- `settings.Settings(output_dir, workers=3, screenshots=True, headless=True, page_timeout_s=300, max_attempts=3, min_interval_s=2.0)` with `load()`, `save()` and `output_path`. Also the constants `BASE_URL, APP_DIR, STATE_DIR, RUNS_DIR, LOG_DIR, SETTINGS_FILE, SITEMAP_FILE, DEFAULT_OUTPUT, RUNNER_PREFIX, LANGUAGES` (a list of (label, key, ext)).
- `theneo.next_data(html: str) -> dict` returns pageProps and raises `ValueError` if missing.
- `theneo.menu_items(pp) -> list[dict]`, `theneo.slug_aliases(pp) -> dict[str, str]` and `theneo.section_entry(pp, section_id) -> dict | None`.
- `theneo.normalize_params(items: list) -> list[dict]`. Each param is `{name, type, required, description, example, children}`, recursing through `items` and `complexItems`.
- `theneo.endpoint_info(entry) -> dict` gives `{method, path, headers, path_params, query, body, responses:[{status, description, content_type, example}]}`. The example is rebuilt from the response body params (value fields) as JSON.
- `theneo.expected_counts(entry) -> dict` gives `{params, responses, images}`, where images counts `<img` in the description.
- `theneo.parse_llms(text) -> list[str]` returns slugs.
- `guard.classify(method, url) -> "allow" | "block" | "api"`. "api" means a Contoso API host. `guard.install(context, sink: list)` is an async route installer that appends blocked entries to sink.

- [ ] Write the tests:
  - `next_data` extracts `documents.data.documentMenu`.
  - `menu_items` gives 2 sections in the fixture.
  - `normalize_params` on nested `items` gives children.
  - `endpoint_info` for login has method `POST`, path `token`, 4 body params and statuses `[200, 400]`.
  - `classify("GET","https://apisandbox.contoso.example/token") == "api"`.
  - `classify("POST","https://apidocs.contoso.example/x") == "block"`.
  - `classify("GET","https://theneo-prod-public.s3.us-east-1.amazonaws.com/a.png") == "allow"`.
  - `classify("GET","https://www.googletagmanager.com/gtag/js") == "block"`.
  - `test_verify_counts_no_responses`: an entry with no responses has `expected_counts()["responses"] == 0`.
- [ ] Run `venv\Scripts\python -m pytest tests/rest -q` and confirm it FAILS (module missing).
- [ ] Implement.
- [ ] Run the tests and confirm they PASS.

### Task 2: HTTP client with throttle and block detection

**Files:** Create `restscraper/http.py`. Test `tests/rest/test_http.py`, using an httpx MockTransport.

**Interfaces:**
- `class Blocked(Exception)`, `class NotFound(Exception)`.
- `class Throttle(min_interval_s)` with `async wait()`, shared by HTTP and the browsers.
- `class DocsClient(throttle, transport=None)` with `async get_text(path_or_url) -> str`. It raises
  `Blocked` on 403 or a "403 Forbidden" body, `NotFound` on 404, and retries 5xx and network errors
  3 times with backoff. It also has `async probe() -> bool` (GET `/llms.txt` == 200) and `async close()`.

- [ ] Tests: 403 raises `Blocked`, 404 raises `NotFound`, a 500 followed by a 200 returns the text,
  and two `Throttle(0.2)` waits are at least 0.2 s apart.
- [ ] Implement, then run the tests and confirm they PASS.

### Task 3: Discovery, folders, cross-check

**Files:** Create `restscraper/discovery.py`. Test `tests/rest/test_discovery.py`.

**Interfaces:**
- `@dataclass PageInfo(page_id (=sectionId), slug (full path), title, section_key, section_name, url, kind ("section"|"endpoint"), order, folder="", parent_id="")`.
- `@dataclass SectionInfo(key, name, page_id, order, folder)`.
- `SiteMap(sections, pages, discovered_at, report)` with `save()`, `load()`, `page(pid)` and
  `records(section_keys=None, page_ids=None) -> list[dict]`. Records carry the keys the GUI uses:
  page_id, title, space_key=section_key, space_name=section_name, folder, url, slug, kind.
- `build_sitemap(pp, llms_slugs) -> SiteMap` (pure). Section folders are `NN Name`. An endpoint
  folder is `safe_segment(name)`, made unique case-insensitively with `paths.unique_name(..., suffix=slug)`.
  The names `images snippets responses tryit` are reserved.
- `crosscheck(pp, llms_slugs) -> dict` gives `{menu, llms, missing_from_llms, missing_from_menu}`.
  An llms slug counts as present when its last segment maps through `slug_aliases` to a menu sectionId.
- `async discover(client, log) -> SiteMap` fetches the start page and llms.txt, then calls `build_sitemap`.

- [ ] Tests:
  - `test_folders_unique_for_duplicate_names`: two "Reset Password (via web user)" items get distinct folders.
  - Section folders are `01 Getting Started` and `02 Authorization`.
  - `test_crosscheck_uses_slug_aliases`.
  - A records() round trip.
- [ ] Implement, then run the tests and confirm they PASS.

### Task 4: Browser capture (endpoint block and explorer)

**Files:** Create `restscraper/browser.py`.

**Interfaces:**
- `class BrowserPool(size, headless, throttle, log)` with `start()`, `close()` and
  `async with pool.slot() as ctx`. The context is guarded through `guard.install`, uses the
  UA-fixed user agent and a 1600x1000 viewport, and is relaunched if the browser dies.
- `async capture_block(ctx, url, section_id, folder, kind) -> dict` returns `{next_data (pageProps), html, text, snippets:{lang: code}, responses:{status: text}, images:[src], screenshots:[names], blocked:[...]}`.
  - The block is `section.th-content_section-item:has([id="<sid>"])`. Scroll it into view and wait
    up to 20 s for content.
  - Read `__NEXT_DATA__` from the DOM. Click every "Expand all" and "Show more" inside the block.
  - For each language, open `.request-widget-language-switcher-dropdown` inside the block, click the
    matching `li`, then read `.snippet-right-card-body code` with line-number nodes removed.
  - Click each `[role=tab]` and read `pre.response-code-block` the same way.
  - Raise `Blocked` if the document is 403 or titled "403 Forbidden".
  - Take an element screenshot, split into parts if it is taller than 12000 px.
- `async capture_tryit(ctx, slug, folder) -> dict` returns `{url, base_url, method, path, fields:[{group, name, type, required, value}], body_code, snippets:{lang: code}, screenshots, blocked}`.
  Body code comes from switching to "Code view". **There is no Run click.**

- [ ] Live check (no unit test, since it needs the site). Run
  `venv\Scripts\python -m restscraper.cli --only authorization/login-via-web-user --out <scratch>`
  after Task 6, and inspect the output.

### Task 5: Page writer, Markdown and verification

**Files:** Create `restscraper/render.py` and `restscraper/page.py`. Test `tests/rest/test_page.py`.

**Interfaces:**
- `render.html_to_md(html) -> str` handles headings, paragraphs, lists, tables, code, links and images.
- `render.page_markdown(doc: dict) -> str` produces the title, method and URL, description,
  parameter tables (nested names dotted, e.g. `detail.client.id`), responses, snippets per language
  and a Try-it summary.
- `page.verify(expected, found) -> (issues, notes)` compares:
  - all 8 snippets present and non-empty
  - response tabs ≥ expected responses
  - Try-it fields ≥ header + query + path + top-level body params, when the explorer is captured
  - images downloaded == images found
  - screenshots present when they are enabled
  - any "api" guard hit is an issue
- `async scrape_page(rec, client, pool, output_dir, settings, log) -> dict` writes every file
  atomically and returns the same result keys the KB engine expects: status, issues, notes, found,
  expected, files, files_expected and screenshots. Section pages skip snippets and Try-it.

- [ ] Tests:
  - `verify` flags a missing snippet language and fewer response tabs.
  - `test_verify_counts_no_responses` produces no issue.
  - `page_markdown` contains a `| detail.client.id |` row for a nested param.
  - `html_to_md` renders a table.
- [ ] Implement, then run the tests and confirm they PASS.

### Task 6: Engine, index/audit, CLI

**Files:** Create `restscraper/engine.py`, `restscraper/library_index.py` and `restscraper/cli.py`.
Test `tests/rest/test_engine.py`.

**Interfaces:**
- `async run_scrape(state, page_ids, settings, control, events, sitemap=None, *, client=None, pool=None, scrape=scrape_page) -> dict`.
  This is the KB engine's worker, retry and breaker logic, plus `Blocked` handling. On `Blocked`:
  requeue the page (attempt not counted), set a shared cooldown flag, have one worker probe every
  60 s up to 60 min, and keep the other workers waiting. On success, continue. On timeout, pause
  with an alert.
- `library_index.write_indexes(output_dir, sitemap)` and `audit(output_dir, sitemap) -> dict`, with
  the same keys as KB: live_articles, on_disk, missing, warnings, stale, unreadable.
- `cli.main(argv)` takes `--sections a,b`, `--only slug1,slug2`, `--out DIR`, `--resume` and `--retry`.

- [ ] Test `test_engine_cooldown_on_blocked`: a fake scrape raises `Blocked` once and then succeeds,
  while the fake client's probe returns False and then True. The page ends DONE with attempts == 1.
- [ ] Implement, then run the tests and confirm they PASS.
- [ ] Live smoke: run the CLI with `--only` on login-via-web-user, a Deal endpoint with nested body,
  and the Getting Started page. Inspect the folders and screenshots by eye.

### Task 7: GUI and launcher

**Files:** Create `restscraper/__main__.py`, `restscraper/gui/{__init__,main_window,models,workers}.py` and
`Run REST API Scraper.bat`. Modify `README.md` to add a REST API section.

- Copy and adapt the KB window. Sections replace products and spaces in the tree. The columns are
  Status, Section, Title, Snippets, Responses, Try-it, Images, Tries, Time and Problem. The header
  reads "REST API Scraper — apidocs.contoso.example". A "Cooling down (site rate limit)"
  state shows in the counts line.
- The logger is "restscraper", writing to `state/rest/logs`.
- [ ] Launch with `venv\Scripts\python -m restscraper` and check that the window opens, the site map
  loads and the tree lists 25 sections.
- [ ] Full run, then check the audit for 0 missing.
