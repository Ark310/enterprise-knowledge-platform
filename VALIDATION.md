# v0.13 verification and limits

- .NET SDK 10.0.403 Release solution build: 0 warnings, 0 errors.
- Python suites: 33 tests passed (21 original regressions plus 12 whole-review contract/provenance/accounting checks).
- C# host fixtures: 16 assertions passed for process launch, credential stripping, live logs, cancellation/timeout and exit status.
- Real supplied video preparation: first 120-second section decoded 60 frames (0–118 seconds); final 720–774.784-second section decoded 28 frames (720–774). Frame manifest used showinfo timestamps, not assumed fps offsets. This tests section preparation, not semantic comprehension.
- Synthetic database integration: whole-review source ingest, A consolidation/save/embedding, per-topic queries, B row/save/embedding, record links, source citations and exact/latest report retrieval passed. One shared embedding profile was verified for source/A/B; two analysis vectors and one B→A link were checked.

Database integration used an isolated in-memory PGlite PostgreSQL 18.6 engine with pgvector, synthetic source text/three-second video, and a fake three-dimensional embedding service. PGlite's fixed postgres database name required adapting only fixture database-name guards. Production schema/migration files and production name guards are unchanged. This is not a native Windows/PostgreSQL 17/Ollama/Codex end-to-end test or an embedding quality benchmark.

Not tested here: Windows activity UI/DPAPI/setup, live ChatGPT reasoning, RTX GPU performance, completeness of discovered topics or adequacy of the user's documentation coverage. Review the first live exported run. An accounted-for topic index does not prove that the model noticed every visible/narrated topic; sparse frames and bounded retrieval remain disclosed limits. No articles are auto-published or findings human-approved. Existing Firecrawl startup noise was not claimed fixed.

No table/migration change is required. Model name and source extraction version remain unchanged. Old docs/verification-v012 and verification-logs are historical evidence, not new v0.13 tests. Current logs: docs/verification-v013.
