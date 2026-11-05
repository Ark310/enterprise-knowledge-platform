# v0.20 validation

- Release .NET 10 build: six projects, zero warnings/errors.
- Python: 96 checks passed, including new coverage, required visual planning, exact path matching, source-change and frame-citation regressions.
- Host: 45 checks passed (25 existing + 20 QA); same images reach Knowledge and Verifier, not normalization. Calls use synthetic model responses; not semantic accuracy tests.
- 62 disposable database checks passed across all four suites.
- Disposable PostgreSQL 17.7 / pgvector 0.8.1: v017, v018, v019 and v020 suites pass. New v020 checks exercise actual question-directed SQL reads, complete 18-unit transcript read, FFmpeg sampling with accurate bounded timestamps, image copies, frame FK insertion, tampering rejection, missing/wrong/ambiguous video matching and repeatable migration.
- Final review: two P2 findings (ambiguous full paths and optional visual plan) reproduced before fixes and covered by passing regressions. No deferred review findings.
- Existing Gap calls use the default frame-helper path unchanged. A new optional preverified-hash input lets QA verify once around a bounded batch rather than rehashing an MP4 for each still. Source change during batch is tested.

Limits: no live Windows server, original corpus, real Codex/Ollama responses or answer-parity validation was available here. Still images can miss intervening actions. Model verification is not SME approval. Existing source vectors are reused; answers are not automatically embedded as trusted facts.

Logs in docs/verification-v020. RED logs are intentional pre-fix failures, not release failures. Database tests used an isolated disposable cluster; a root-check compatibility shim was used only to run that container fixture and is not shipped. Never run fixture installers against the operator database.
