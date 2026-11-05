# v0.22 validation and acceptance evidence

Scope: POC 2 retrieval/completeness correction. Original Qwen profile/vectors, pgvector indexes, schema and POC 1 workflow retained. No new database migration.

- Release .NET 10 build: six projects, zero warnings/errors. Host suite: 49 checks passed (25 existing and 24 QA).
- Python: 109 checks pass. Required-first assembly, fair source budgets, stable citation IDs including IDs retained in database audit, supported product scopes, transcript pairing and strict verdict gates.
- Disposable PostgreSQL 17.7/pgvector 0.8.1: 70 checks across v017–v021, using real SQL and FFmpeg, synthetic vectors/model verdicts.
- Captured v0.20 export replay: original video question had zero matching transcript units. Identity-first lookup retrieves all 30 recorded SRT/DOCX companion units available in its password-question packet. Replay uses recorded SOURCE text, not generated answer text. It makes no model/vector calls and does not establish original audio alignment or source truth.
- Release-name regression uses an unseen synthetic vendor: an older exact phrase survives six newer broad matches; Web release material is excluded from the TradeDesk evidence allowance.
- Host scope tests: missing source triggers follow-up even with a model PASS; repaired scope is reverified; persistent missing scope never publishes a verified answer.
- Independent read-only review found image-presence, follow-up capacity and additional product-scope gaps. All were reproduced RED, corrected and tested GREEN. No deferred minor findings.

Decisions and limitations:
- Existing filenames/registered links establish pairing, not independent audio alignment. Ambiguous identities ask for a path.
- Known incomplete release inventory remains a semantic scope limitation: a bounded newest-among-checked claim can be valid, while an unrestricted latest claim must be rejected by the Verifier. The host separately enforces required matching-passage presence. This does not guarantee every synonym or absent original was searched.
- The source title-card mismatch is real in the exported frame. We preserve it rather than changing source identity to satisfy a test.
- No live Windows/Codex/Ollama run or full original corpus was available here. Live answer quality and GPT comparison still require operator acceptance. Code tests and two agents agreeing do not prove product truth.
- The separate Firecrawl authorization warning is not claimed repaired; all captured reasoning calls completed successfully.
- No user run archives, raw source snapshots, database credentials, runtime caches or container-only test shims are distributed.

RED logs are intentional pre-fix evidence. Final green logs accompany them. The disposable cluster was isolated, with a container-only root-check compatibility shim, not shipped in the solution.
