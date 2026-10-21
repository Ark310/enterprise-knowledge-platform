# REST API Docs Scraper: Design

Date: 2026-10-21
Status: draft for approval

## Intent

The KB scraper (`kbscraper`, help.contoso.example) produced a complete local library of the knowledge base.
The user now wants the same thing for the Contoso REST API developer docs at
https://apidocs.contoso.example (start page `/getting-started-1`). The scrape should reach
every page that has documentation. It must capture the code snippets and the "Try it" (API Explorer)
content, so that nothing on the site is lost.

## Decisions made by the user

| Topic | Decision |
|---|---|
| Try it / API Explorer | **Capture only.** Record what the panel shows: base URL, header, path, query and body fields with their default or example values, the code view, the generated snippet, and a screenshot. **Never send a request to the live or sandbox API.** |
| Code snippets | **Every language** in the snippet dropdown, each saved as its own file. |
| Output conventions | **Same as the KB scraper**: a folder tree mirroring the site menu, one JSON per page, plus Markdown and HTML, full-page screenshots with expandable parts opened, a full re-scrape on every run, and a `.bat` launcher. |
| Location | **Inside this project.** Output goes to `KB Site Scraper\REST API\`. The code is added to this project with its own `Run REST API Scraper.bat` and shares the existing venv. |

## Site facts (from recon on 2026-10-21)

- The site runs on **Theneo** (Next.js). Each page's `<script id="__NEXT_DATA__">` contains:
  - `documents.data.documentMenu.items`: the full menu tree (sections with `subItems`, `slug`, `method`,
    `isHeader` and `externalPageLink`). `documentMenu.slugs` has 859 entries.
  - `documents.data.transformedSection`: the structured data for the current section. That includes,
    for each endpoint, `endpoints` (method and path), `request.query/body/header`, `responses`,
    `statusCodes`, `errorCodes` and `description` (HTML).
  - `projectVersions`: only **v1** exists. `tabs` is empty.
- The site has 25 top-level sections (Authorization, Account, Admin, Approval, Bank, Beneficiary, ... User)
  and about 830 endpoint pages. Most endpoints come in "via web user" and "via td user" variants.
- `/llms.txt` lists **832** pages. Each page has a Markdown export at `<url>.md`, which holds the
  description plus the endpoint JSON. There is no `sitemap.xml`.
- **Code snippets are generated in the browser**: the page source doesn't contain them. The language
  dropdown (`.request-widget-language-switcher-dropdown`, also shown as a language box) offers
  **cURL, Ruby, Python, PHP, Java, Node.js, Go and .NET**.
- An endpoint URL renders **several endpoints of its section on one long page**. The
  `/authorization/login-via-web-user` page also shows the td-user variant.
- Response examples sit behind status tabs (`200`, `400`, ...) and are truncated until **Show more**
  or **Expand all** is clicked.
- **Try in API Explorer** opens a separate page:
  `/api-runner/contoso/contoso-rest-api-1/<slug>`. It shows header and body
  forms, a Code view / Form view toggle, a snippet box with a language dropdown, and a **Run** button.
  Requests from it go to the sandbox `https://apisandbox.contoso.example`.
- **Headless Chrome is refused with 403.** The site blocks the `HeadlessChrome` user agent. A normal
  Chrome user agent works. Plain HTTP fetches with a browser user agent also work.
- The page also loads analytics (Google). Blocking it does no harm.

## Goals

1. Discover every documented page from the menu tree. Cross-check against `llms.txt` and `slugs`,
   and report any page found in one source but missing from another.
2. For every page, save:
   - the raw structured data (the page's entry from `transformedSection`, exactly as served)
   - the Theneo Markdown export (`.md`)
   - the rendered content: description text, tables, callouts and lists, plus the images in it
     (downloaded)
   - for each endpoint: method, path, full URL, and the header, path, query and body parameters with
     name, type, required flag, description and example, including nested objects and arrays
   - every response example for every status tab, fully expanded
   - the **code snippet in all 8 languages**, one file per language
   - the **Try-it capture**: base URL, every form field with its default value, the body's code
     view, the snippet as the explorer shows it, and a screenshot
   - a full-page screenshot of the endpoint, with every expandable part opened
3. Build a root index (`index.json` and `index.md`) grouped by section.
4. Verify each page: compare what the structured data says should exist with what was captured.
   Mark shortfalls as warnings, as the KB scraper does.
5. Use the same run behaviour as the KB scraper: fresh full scrape per run, Resume, Retry problems,
   Pause/Stop, Audit, a journaled run state, logs, and a GUI launched from a `.bat`.

## Non-goals

- Sending any API request (no Run, no Send, no login to the sandbox).
- Scraping other Theneo projects or versions (only v1 exists).
- Following external links off the docs site. They are recorded as links only.
- Incremental "only changed pages" scraping. The user wants a full re-scrape every time.

## Anti-goals (would be a failure even if it "works")

- **Any request reaching `apisandbox.contoso.example` or any other Contoso API host.** This must be
  impossible by construction, not just avoided by never clicking Run. See Safety.
- A page reported as OK when snippets, response tabs, parameters or Try-it fields are missing.
- Endpoints silently skipped because they share a long section page with other endpoints.
- Breaking or changing the behaviour of the existing KB scraper.

## Output layout

```
REST API/
  index.json, index.md                 every page, grouped by section, with status and counts
  _site/
    menu.json                          raw documentMenu (items + slugs)
    llms.txt                           copy of the site's llms.txt
    discovery_report.json              menu vs llms.txt vs slugs cross-check
  01 Getting Started/                  sections numbered in menu order
    page.json, page.md, page.html, screenshot.png, images/
  02 Authorization/
    _section.json                      section overview (description, child list)
    page.json, page.md, page.html, screenshot.png
    Login (via web user)/
      page.json                        structured data (see below)
      page.md                          readable Markdown: description, parameter tables, responses, snippets
      source.md                        Theneo's own .md export, verbatim
      page.html                        rendered HTML of this endpoint's block
      screenshot.png                   this endpoint's block, all parts expanded (partNN if very long)
      images/
      snippets/
        curl.sh  ruby.rb  python.py  php.php  java.java  nodejs.js  go.go  dotnet.cs
      responses/
        200.json  400.json             fully expanded example bodies (.txt if not JSON)
      tryit/
        tryit.json                     base URL, fields with defaults, code view, snippet language
        tryit.png                      full-page screenshot of the explorer page
        snippets/                      the explorer's own snippets, all languages
    Login (via td user)/
      ...
```

`page.json` holds: slug, URL, section and breadcrumb, name, method, path, full URL, section ids and
`updatedAt`. Under `content` it has the description (HTML, Markdown and text), tables, callouts and links.
Under `request` it has the headers, path, query and body parameters, normalized and nested. Under
`responses` it has the per-status description, schema and example. `snippets` lists each language with
its file and code. `tryit` holds the explorer capture. `raw` is the untouched `transformedSection`
entry. `media` lists the images. `verification` gives expected vs captured counts, issues and notes.

## How it works

1. **Discovery** (HTTP, no browser): fetch the start page, parse `__NEXT_DATA__`, and walk
   `documentMenu.items` into a page list with menu order and parent chain. Fetch `llms.txt` and
   cross-check. Save `_site/`. Headers (`isHeader`) become folders only. External links are recorded and
   not scraped.
2. **Per page** (one Chrome instance per worker, as the KB scraper learned):
   1. Fetch the page's `__NEXT_DATA__` over HTTP and take its own entry from `transformedSection`.
      This gives the expected counts: parameters, response statuses and images.
   2. Fetch `<url>.md` and save it as `source.md`.
   3. Open the page in Chrome. Locate **this endpoint's block** among the endpoints rendered on the
      page. Click Expand all and Show more, then read each status tab. For each of the 8 languages,
      select the language and read the snippet's code text. Save the block's HTML, the images and a
      screenshot of the block.
   4. Open the endpoint's `/api-runner/...` page. Read every form field (label, type, required flag,
      value), switch to Code view and read the body, read the snippets in all languages, and take the
      screenshot. **Run is never clicked.**
   5. Verify, write the files atomically, and journal the status.
3. **Finish**: write `index.json`/`index.md` and run the audit.

## Safety: no live requests

- Every browser context installs a **request allowlist**. Only `apidocs.contoso.example`
  and the static asset hosts the pages need (identified during build, e.g. Theneo's CDN and fonts)
  are allowed. **Everything else is aborted**: `apisandbox.contoso.example`, any other `*.contoso.*` API
  host, analytics, and XHR/fetch to unknown hosts.
- Every aborted request is logged. Any attempt to reach an API host is also recorded in the run's
  issues, so an accidental click would be visible.
- The scraper never clicks Run or Send buttons or anything that submits the explorer.
- No credentials are ever entered. The form keeps its documented defaults.
- An extra layer (Claude's call): even on allowed hosts, any POST, PUT, PATCH or DELETE request, and
  any request to a Theneo "run" or "proxy" path, is aborted. If this blocking stops the explorer page
  from loading fully, **safety wins**. The missing Try-it data is reported as a warning, never worked
  around.

## Reuse from `kbscraper`

Reuse where it fits, without changing KB behaviour: `state.RunState` (the journal), `paths`
(safe names), the settings pattern, the screenshot slot / one-Chrome-per-worker approach, the GUI layout
(item tree with checkboxes, pages table, Issues tab, the same buttons) and the logging setup. Anything
Confluence-specific stays in `kbscraper`.

## Calls made by Claude (not decided by the user; easy to change)

- The new package is `restscraper/`, next to `kbscraper/`. Settings and state go in
  `state/rest/`, so they don't mix with the KB run state.
- The GUI mirrors the KB scraper's window, with sections in place of spaces.
- Sections get a two-digit prefix so folders sort in menu order. Endpoint folders use the menu name.
- Example values in the docs (such as the sample `access_token` strings in response examples) are
  saved verbatim, because they are published documentation content. The scraper never enters or
  stores real credentials.
- The endpoint screenshot crops to that endpoint's own block, not the whole multi-endpoint page. The
  Try-it page is screenshotted in full.
- Default of 3 workers, with a short delay between page loads to be gentle on the site.

## Left to the builder

The exact DOM selectors. Recon found `.th-language-module`, `.request-widget-language-switcher-dropdown`,
`.try-api-explorer-btn`, the "Expand all" and "Show more" buttons and the `role=tab` status tabs; the
builder confirms them on several pages. Also left to the builder: how to find an endpoint's block on a
multi-endpoint page, file-extension mapping, the Markdown rendering of parameter tables, and timeouts.
