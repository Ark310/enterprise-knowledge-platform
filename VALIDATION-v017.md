# v0.17 validation — 3 November 2026

- .NET SDK 10.0.403 Release build: PASS, zero warnings/errors.
- Python offline suite: 65 checks PASS. Original handoff/profile/UTF-8/category/frame rules retained; new grouping, oversized cues, bad timing, cache corruption and comparison helpers covered.
- Host/process suite: 25 checks PASS on Linux, including subprocess encoding/transport, isolated Codex environment, role activity and validation-repair behaviour. Codex transport fixtures are simulated, not live model runs.
- Disposable PostgreSQL integration: 23 checks PASS using PostgreSQL 16.15 and compiled pgvector 0.8.1, 2560-dimensional deterministic synthetic vectors. Tests include repeatable additive migration; original cue ID retention; grouping and DERIVED_FROM links; actual filename/duration pairing; no duplicate retry; valid halfvec source/finding indexes; query-plan proof of HNSW use; explicit exact baseline; three-mode report export; incomplete-build fallback; blocking a misleading comparison with no ready grouped transcript; real FFmpeg frame extraction/cache reuse/corruption recovery; persistent frame evidence; role filtering; superseded-revision exclusion.

The disposable Linux fixture used an isolated test-only execution shim because the container has only one mapped UID. Its initial fresh-schema installer version guard was lowered in memory solely for the PostgreSQL 16 fixture. The distributed fresh installer remains unchanged at PostgreSQL 17+. No test infrastructure shim is shipped in this release and no operator database was accessed.

Independent read-only review found five issues; fixed before packaging: portable cached-frame exports; grouped readiness visibility/comparison gating; matching HNSW queries for saved findings; cache shape validation; persistent video/transcript pairing with duration bounds. A failing integration exposed FFmpeg lookahead logging; output frames now map to the first corresponding logged timestamps while missing timestamps still fail. Regression test added.

Not verified here: live Windows CMD/PowerShell execution, the operator's PostgreSQL 17.11/pgvector 0.8.7 build, actual Qwen GPU performance, real Codex semantic responses, actual corpus recall/latency, and end-to-end User Master outcomes. Run START-HERE.md on the target machine. Passing synthetic checks does not predeclare the results of T02/T04/T05 or /review.

Normal POC limits remain: supplied SRT accuracy is not independently established; selected frames can miss brief actions; no exhaustive visual indexing/OCR; bounded retrieval cannot prove company-wide absence; no new production privacy/tenant/publication implementation. Cache media must remain available while cited. Do not manually delete the frame cache after a run you need to export.

Text files under docs/verification-v017 contain actual successful final outputs. Files named *red.txt record expected pre-fix failures, not release acceptance failures.
