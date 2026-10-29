# TD POC v0.13 — recording-wide documentation gap lists

Read docs/START-HERE.md. No database reset or reimport is required for unchanged data/model fingerprints.

```cmd
cd /d C:\TD-POC-v0.13
Setup-POC.cmd
Start-POC.cmd
```

At You>, use `/review` (alias `/test MODULE`), then give the recording path. A reviews all scheduled sections and builds a topic index; B searches per topic and writes one coverage row per topic. The host validates, stores and embeds both stages using the existing local Qwen profile. `/results latest` retrieves one exact whole-recording run; ask C follow-up questions or use `/ask`.

Coverage statuses: COVERED, NEEDS_REWORK, NOT_FOUND_IN_REVIEWED_SOURCES, NEEDS_REVIEW. Gaps are qualified; a bounded search cannot establish company-wide absence. The scope is the recording's supported topics, not every unshown feature of its modules. All findings remain AGENT_PROPOSED.

Existing `/test T02`, T04 and T05 remain narrow regression tests. The original td-doc-review-2.0 contract is unchanged. The broad workflow uses the separately validated td-module-review-1.0 envelope in contracts/module-review.schema.json. Existing 29 tables and 55 relationships are retained; no migration is added.

View workflow and tables in docs/architecture-and-tables.html. Agent instructions are in agents/agent-a-module.md and agents/agent-b-gaps.md. Logs and per-section/batch JSON are exported by Export-LatestRun.cmd. Credentials are excluded.
