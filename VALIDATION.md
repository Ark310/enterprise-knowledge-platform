# v0.15 verification

Completed locally with .NET SDK 10.0.403 and Python:
- Release solution build: 0 warnings/errors.
- 51 Python tests: legacy evidence/contracts, module coverage/provenance, module normalization, UTF-8/ASCII-safe wire transport, large Unicode payload, and refusal to change embedding profile between A/B.
- 23 C# host assertions: process/credential isolation, live logs/cancellation/timeouts, main progress, large Unicode C#/Python roundtrip, the ACTUAL 1.2 MB failed-run retrieval packet across that process boundary with deep JSON equality, persisted worker failure/raw output, and two aggregate A/B status streams with multiple A calls in one stream.
- Actual failed-run data replay: the 37-topic retrieval packet round-trips unchanged through ASCII-safe JSON under CP1252. The old literal Unicode response is not CP1252-encodable. With the explicitly configured Contoso Canada context prefix, the saved index consolidates 37 into 31 topic identities, accounting for all 56 observation IDs. This is a replay of that input, not a promise that a new model run yields a fixed topic count.
- Synthetic PostgreSQL/pgvector integration: source ingest, pre-save resume copy, normalized A handoff/storage, post-A-save verification/resume without increasing vector counts, Unicode documentation retrieval, B row storage/vectors, source links, B→A links and exact/latest report retrieval. One profile is verified across source/A/B, and B/ambiguous-output resume is rejected.

The DB fixture uses PGlite PostgreSQL 18.6 with pgvector, a shared fixture connection (the engine is single-connection), adapted fixture-only database-name guards, fake three-dimensional embeddings and synthetic source/video. Production DB guards/connections/schema are unchanged. It is not a Windows PostgreSQL 17 or real embedding-quality test.

Not executed here: native Windows role-window presentation, PowerShell/DPAPI/login/setup execution, live ChatGPT outputs, local RTX performance and full semantic completeness/accuracy. The role-stream/control plumbing is tested; actual Windows UI remains a first-run check. Existing FFmpeg capability and timestamp handling are retained from the tested hotfix. No database reset/new migration or forced reimport.

All handoffs remain proposed analysis with sampled media and bounded documentation retrieval. No private internal reasoning is shown. The observed Firecrawl MCP startup warning is retained in raw stderr, summarized once per role and not claimed fixed; actual process exit/validation still gates success.

Current logs: docs/verification-v015. Earlier verification directories are historical. Use the new fresh /review walkthrough in docs/START-HERE.md and export the first run for factual review.
