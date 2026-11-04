# v0.19 — source investigation for Knowledge Retrieval POC

Confirmed v0.18 failure: two Woodgrove searches returned 12 catalogue passages, one release landing page and10 unrelated saved reviews; zero evidence mentioning Woodgrove Bank. The answering agent correctly declined but had no further investigation step.

Changes:
- QA-only article-body search excludes index.json/index.md/_space.json as factual evidence. These files and all old vectors remain in PostgreSQL; the Gap POC keeps its existing search defaults.
- Focused escaped keyword searches alongside existing HNSW; titles/body relevance and article-family diversity; Markdown/JSON export deduplication.
- Read additional original source units from PostgreSQL, with explicit read/packet limits and original IDs. Never load or execute arbitrary file paths from model output.
- Latest-release inventory: numeric path-derived versions, keyword matches, later notes, missing/partial usable text and bounded coverage. Dates are source-note updates, not deployment dates. This is not a hardcoded Woodgrove answer.
- Saved review findings are included only when requested by the normalization plan, max3; they remain proposals unless confirmed.
- Verifier checks an insufficient draft and may request one follow-up investigation. A final unsupported answer stays withheld. All attempts, supplied passages and checks remain exportable.
- Clean numbered sources in console; full locators/quotes remain in audit JSON. /diagnose keyword checks imported usable text and vectors directly.
- Uses existing v0.18 audit schema: no new production-schema redesign, data reset, model replacement or full re-embedding.
