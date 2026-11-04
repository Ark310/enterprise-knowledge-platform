# v0.18 validation

## Passed in this build
- .NET 10.0.100 Release build: 0 warnings, 0 errors (six projects).
- Python unittest discovery: 74 tests passed (65 inherited + 9 knowledge gates).
- .NET host checks: 25 inherited + 17 knowledge/launcher checks = 42 passed.
- Disposable PostgreSQL integration: 23 existing v017 checks + 11 new v018 persistence checks = 34 passed.
- Launcher version/menu/input-rejection smoke check passed.
- Independent code review completed. Its two important findings were reproduced with failing tests and fixed: withdrawn/superseded review freshness at final save; local-file failure after DB completion no longer produces contradictory failure status.

## What was actually exercised
Deterministic fixture model outputs test the real C# orchestration with the actual Python citation/contract validators. Tests cover successful handoff, nonexistent quotes, verification rejection, one correction only, missing evidence, clarification, cancellation, failed DB save, local final-file failure and no automatic answer ingestion. PostgreSQL checks use real halfvec HNSW indexes and synthetic 2560-dimensional vectors, relational evidence links, audit events, repeatable migration and current review/source checks. They do not measure model answer quality.

## Environment and limits
Linux .NET SDK10.0.100, Python3.12, disposable PostgreSQL16.15 and compiled pgvector0.8.1, actual FFmpeg. A test-only first-call UID shim was used because this container maps only UID0; the fresh-schema PostgreSQL17 guard was lowered to16 in fixture memory only. Neither workaround nor a modified production installer is shipped.

Windows CMD/PowerShell/Visual Studio and the user's live PostgreSQL17.11/pgvector0.8.7, Codex ChatGPT login and Ollama Qwen model were not executed here. Follow START-HERE.md to smoke-test that combination. No existing user database was contacted. No real model inference was used as a substitute for semantic accuracy testing. Verification is an AI review, not SME approval.

## Regression evidence
Successful test/build logs are in docs/verification-v018. Files labelled RED are expected pre-fix failures proving the regression tests detected the issues, not current failures. Inherited v017 logs remain historical and are separately labelled by version.
