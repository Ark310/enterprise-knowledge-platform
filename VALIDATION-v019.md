# v0.19 validation

## Passed
- Release solution build: .NET10.0.100, 0 warnings/errors, six projects.
- Python unittest discovery: 86 tests (74 v018 +12 source-investigation checks).
- Host checks: 25 inherited process/gap checks +19 QA checks =44.
- Disposable PostgreSQL:23 v017 +11 v018 +14 v019 checks =48.

The v019 database tests exercise real halfvec HNSW using deterministic synthetic2560-dimensional vectors. A synthetic bank topic, NOT the claimed Woodgrove answer, verifies catalogue exclusion, actual body retrieval, release numeric order, partial-extraction scope, source reads/date provenance, source-version read allowlist, citation ID stability, max-one expansion, missing-vector diagnostics, and a short unembedded target surviving a 200-plus-chunk article. Existing Gap search defaults remain unchanged.

Host fixtures use actual Python contract/citation gates and controlled model outputs. They verify that an insufficient draft and even an empty search reach the Verifier, allow one further investigation, and never publish an unchecked answer. Model factual accuracy is not established by these fixtures.

## Review and regressions
Independent whole-change review found two important issues: empty-hit early refusal and keyword candidate crowding before the diversity cap. Each was reproduced by a failing regression, then fixed and passed. A further unit regression ensures a clear latest-version request cannot silently skip chronology when the optional planner flag is omitted. Logs prefixed RED are expected pre-fix failures, not current failing tests.

## Boundaries
No live Windows CMD/PowerShell/Visual Studio, user PostgreSQL17.11/pgvector0.8.7, real Codex or real Ollama execution was performed here. No original Woodgrove release-note body was available in the supplied failed-run export, so the previously claimed Woodgrove answer is NOT asserted or hardcoded. Retest the same source revisions on the user's server; /diagnose distinguishes imported usable text and existing profile vectors.

Fixture environment: Linux Python3.12, PostgreSQL16.15/pgvector0.8.1 and actual FFmpeg. A test-only first-call UID shim was necessary in the UID0-only container; installer17 guard was lowered to16 in fixture memory only. No shim or changed production installer is shipped. User database never contacted.

## Resource/coverage limits
Focused lexical search caps3 chunks per article family BEFORE the global200 candidates. Semantic search uses existing HNSW and full-vector reranking; no corpus re-embedding. Up to3 searches/round; final diverse32 initial candidates plus bounded source reads. Up to8 source-version reads/round,12 usable units each. Evidence budget initially70000 characters, cumulative100000/80 records. Max3 saved reviews only when requested. Catalogue files remain stored but excluded from QA factual search. Chronology inventories up to1000 physical active release-note files, deduplicates article families, and reports missing/partial text and truncation. Keywords do not prove synonym-complete absence. Complete usable-text reads do not imply image/media coverage or source freshness beyond pinned stored revisions. All substantive claim checks remain AI checks, not SME approval.
