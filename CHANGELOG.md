# v0.12.0

- Combined Setup-POC.cmd with isolated Codex login, database setup/migration, dependencies/model/build and video/readiness checks.
- Read-only per-agent activity windows; Q/Ctrl+C cancellation, independent elapsed heartbeat and continuously flushed event/stderr files.
- Disable QuickEdit in the main console and viewers. Bounded pipe draining after process exit; preserve failure/timeout/cancel diagnostics.
- Snapshot active run logs with read/write sharing. No credentials in exported bundles.
- Make shared local embedding model/profile visible during A/B database saves. Retain extraction version 0.10.0 for successful-data reuse.
- Remove duplicate upstream handoff from the B prompt (original evidence packet retained).
- Original contracts, agent guardrails, PostgreSQL schema and 25-minute per-agent timeout retained.

See docs/DIAGNOSIS-v0.11.md and VALIDATION.md for findings and verification limits.
