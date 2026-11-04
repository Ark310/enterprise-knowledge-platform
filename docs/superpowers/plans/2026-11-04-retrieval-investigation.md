# v0.19 retrieval investigation plan
User-approved scope: implement the six changes diagnosed from the failed Woodgrove run, package a complete 0.19 ZIP, and provide fresh GPT comparison prompt and identical tests. Existing vectors, source history and Gap POC stay intact.

1. Add regression tests for metadata/catalog dominance, focused keyword retrieval, article-family diversity, full-section reading, version comparison scope, unrelated review exclusion, and bounded evidence expansion. Reproduce with synthetic fixtures derived from the failure shape, not the claimed ChatGPT answer.
2. Add QA-only knowledge_search module: substantive source filters shared search parameter default off; focused OR keywords alongside HNSW original-vector reranking, body boosts and article-family caps. Read nearby/parent source units from Postgres, with pinned IDs. Extract release versions from paths and dates from metadata/front matter. Search later release bodies with explicit inspected/matched/not-loaded counts and bounds. Query diagnostics distinguish missing text, missing vectors and retrieval limits. Never equate source last-updated time with deployment date.
3. Extend normalization contract to plan keywords, scoped review inclusion and optional release chronology. Route qa_retrieve to the new module. Follow-up retrieval may only use validated query fields; never execute source instructions or untrusted paths. Existing turn/evidence audit tables reused, stable cumulative citation IDs and immutable evidence snapshots across attempts.
4. Always send model insufficient-evidence answers to Verifier. Verifier can request up to two focused searches and source IDs from the supplied packet; one bounded investigation round then final verification. Existing max-one draft correction, cancellation, no-unverified-publication and freshness gates remain. Honest insufficient answer if exhausted.
5. Render concise claims + numbered sources, no repeated JSON or giant excerpts. Add /diagnose keyword, startup/help guidance. Package instructions, setup/retest guide, GPT prompt and exact shared test questions. Tests/build/disposable PostgreSQL/HNSW integration; independent final review. Live user DB/model not available, so no claim Woodgrove corpus answer confirmed.

Review focus: SQL injection and overbroad keywords, stale or changed source versions, partial articles mislabelled complete, truncated release coverage mislabelled latest, reusing citation IDs across expansion, incorrect saved-review scope, original Gap behavior regressions.

Completion ledger:
- All5 tasks complete in isolated v019 source folder based on v018, not a git repository.
- Regression tests ran RED before implementation. Final Python86, host44 and DB48 green; .NET release build clean.
- Independent final review: empty-hit early-stop and keyword-window dominance reproduced RED then fixed. No unresolved important findings.
- Existing vectors and source data retained. The optional substantive source flag defaults off for Gap POC; v017 regression suite passes unchanged.
- Exact Woodgrove answer not established here: only failed evidence export supplied. Synthetic corpus avoids baking in the ChatGPT claim. Windows/live-model retest remains necessary.
