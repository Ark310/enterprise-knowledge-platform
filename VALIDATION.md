# TD POC 0.11 validation

Verified during package development:

- Release build: .NET SDK 10.0.403, four projects (three application projects plus a console host-test project), zero warnings/errors.
- 21 offline Python tests: safe folder scope, link exclusion, missing roots, SRT times/range validation, chunk preservation, unsupported binary status, approved contract requests, malformed payloads, citation source/level correspondence, exact text locators/excerpts, unsupplied frames and local endpoint restrictions.
- 6 .NET host assertions on Linux: subprocess invocation, DB secret removal from Codex environment, stdin prompt transport, explicit shell disable flag, omission of ambient user configuration and final JSON capture. The Codex executable in this test is a deterministic fixture, not a real reasoning model.
- One synthetic integration scenario through the real PostgreSQL wire protocol (psycopg to isolated PGlite PostgreSQL 18.6 + pgvector 0.8.7): apply migration twice, local-file shape rejection, register/extract/embed, repeat import without duplicates/vectors, changed-file supersession, nested API storage, raw status 2011 with null numeric HTTP status, hybrid source-role filtering, DOCX text extraction/embedding, all 16 representative emitted-category inputs accepted by final DB constraints, and malformed agent output retained as INVALID with validation report. A local fixture embedding endpoint returns deterministic 3-dimensional vectors; this verifies plumbing, not Qwen accuracy/performance. PGlite is not native Windows PostgreSQL.
- Approved A/B instruction bytes retained exactly. Original td-doc-review-2.0 contract bytes retained exactly. Local adapter explicitly documented separately.
- Diagram inventory: all 29 tables, 301 fields and 55 FK relationships from the approved catalog.

Not yet verified:

- Native Windows CMD/PowerShell execution, DPAPI round-trip and this installed Codex 0.163.0 exec flag compatibility.
- Live Codex agent reasoning, real Qwen 4B GPU execution, model digest/dimensions and corpus throughput.
- Actual TD tests, visual/transcript interpretation, all document parser formats on the target corpus, or semantic accuracy.
- Full-corpus extraction: image OCR, SNAG/legacy DOC conversion and unsupplied transcripts remain pending by design. Unsupported files are inventoried/blocked, not silently called searchable.

Startup/first-time scripts provide target-machine readiness checks. Keep the first target logs and run a pilot before the full import. A structurally valid handoff is not an independently verified finding.

Review: a separate code reviewer identified eight important issues; fixes cover citation enforcement, malformed-output retention, pre-frame revision pinning, current-state scope, blocked embedding status, B finding summaries, restricted Codex tool invocation and accurate processing summaries. The tests above cover relevant mechanisms; no live-Windows security boundary is claimed. Same-user DPAPI access remains within the Windows account trust boundary.

## 0.11 regression evidence
The three new source-category checks failed on the v0.10 mapping (WORD_DOCUMENT/PDF), then passed with DOCUMENT. The synthetic DB scenario now includes a DOCX transcript, repeat-import no-new-vector checks, and inserts the emitted categories under the actual final sources_source_type_check inside a rolled-back test transaction. Native target results for v0.11 remain to be collected. The user has already confirmed v0.10 local model readiness (2560 dimensions), Codex readiness, settings-reader fix and initial source/vector ingestion; those are target observations, not a v0.11 acceptance claim.
