# v0.24 verification

- .NET 10 solution: Release build, zero compiler warnings/errors.
- Python offline suite: 140 tests pass, including scoped images, safe paths, linked media and image-evidence deduplication.
- .NET host suites: 25 runtime checks and 41 knowledge-flow checks pass, including safe process invocation, hidden credentials, bounded corrections, partial answers and conversation restore.
- Disposable PostgreSQL 17.7/pgvector 0.8.1: 18 v024 integration checks pass. These cover durable messages/context, new-chat isolation, upload ownership, no corpus-vector changes, repeat migrations with image evidence, source previews pinned to exact revisions, busy leases and interrupted-request recovery.
- Direct local HTTP API tests exercise the real Web host and PostgreSQL, with deterministic external test-only Codex/Ollama substitutes. They cover the Knowledge→Verifier→database path, original source text and image references, cancellation and restart, plus POC1 A/B validation/save/embedding, saved review selection, C discussion/frame selection and original-source search.
- Node syntax check passes for the browser JavaScript.
- Independent code review: source presentation, original URLs, POC1 media and source-revision issues identified and fixed; no remaining Important blocker reported after review.

## Limits

Rendered-browser testing could not be completed: the environment blocked local browser access, and a separate local headless browser could not start under its socket restrictions. No browser visual pass is claimed. Native Windows CMD/PowerShell window behaviour and a live Codex run on the operator corpus require a local smoke test. The deterministic model tests verify application wiring and guardrails, not actual model answer quality or image relevance judgment.

No user database, real credentials or production model account was used. Existing parser/profile identities remain unchanged; this upgrade does not force re-embedding existing documents. Uploads and QA answers are not promoted to source facts.
