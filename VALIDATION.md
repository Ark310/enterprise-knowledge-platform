# v0.14 verification

- .NET SDK 10.0.403 Release build: success, 0 warnings/errors.
- Python tests: 44 passed, including seven module-index regression cases. Renamed headings use original module attribution; original data/proposals are not silently mutated; separator/case/space variants are accepted; distinct modules are split; unknown, duplicate and omitted observation references still fail.
- C# host fixtures: 17 assertions passed. These include main-console progress subscription, process/secret isolation, continuously flushed logs, cancellation, timeout and exit status. Automatic activity-window launch code was removed, not merely disabled by a default setting.
- Synthetic database integration passed: reproduce an index heading mismatch, mark the fixture run failed, copy its saved section artifacts from a legacy run location to this release, validate/reuse sections, normalize index, save/embed A and B under one profile, create evidence/A links, retrieve exact/latest reports, and reject resume after outputs exist. Original legacy artifacts remain present.
- Includes prior FFmpeg fix with capability-detected fps_mode/legacy numeric vsync and complete diagnostics. Prior real-video section-preparation checks were retained; this release does not claim to have semantically reviewed the entire recording here.

The DB test used a dedicated in-memory PGlite PostgreSQL 18.6 engine with pgvector and fake 3-dimensional embeddings. PGlite fixed-name fixture guards and a shared fixture connection were used because the engine is single-connection; production knowledge_poc guards and production connection code are unchanged. A first socket-based fixture attempt failed at reconnect; the shared-connection fixture passed. This is not a native Windows/PostgreSQL 17/live Ollama/Codex semantic test.

Not verified here: actual Windows console presentation, DPAPI/login/setup execution, live model output quality, semantic completeness of topic coverage, all possible failed-run recovery states. Resume is deliberately limited to failed runs before A database save, with original source hashes, complete section validation and saved frames required. Retain the original v0.13 folder. Native first retry/export remains necessary.

Contracts and schema are unchanged. Findings remain proposals; sampled media and bounded searches remain explicit limits. MCP connector startup noise is not claimed fully resolved. Complete current logs are in docs/verification-v014. Older verification folders are historical.
