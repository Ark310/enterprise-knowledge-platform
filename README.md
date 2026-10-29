# TD POC v0.14

Fixes v0.13 consolidation failures caused by exact module-label equality and removes all automatic per-call activity windows. Includes the v0.13.1 FFmpeg compatibility/error-log fix.

```cmd
cd /d C:\TD-POC-v0.14
Setup-POC.cmd
Start-POC.cmd
```

Read docs/START-HERE.md. Keep the v0.13 run folder: `/resume C:\TD-POC-v0.13\runtime\runs\TD-MODULE-20261029142006-735a56` reuses eligible completed sections from the reported failed run. Otherwise `/review` starts a new whole-recording review.

Every topic retains source-derived module attribution; formatting aliases are reconciled conservatively, distinct source modules are split, and the mapping is audited. Unknown/missing/duplicate observation references still fail. The host saves/embeds A/B results with the same existing local profile. /results latest and /ask retrieve/discuss one exact saved gap run.

Main-console progress/events/elapsed heartbeat; Ctrl+C cancels the active Codex call. Complete event/stderr/status files stay on disk. No separate Codex viewers open automatically. /process still opens its separate import worker by explicit request.

No database reset, schema migration change, reimport or model change is required. Source-backed memory is not model training. Findings remain AGENT_PROPOSED with sampled-video/bounded-search limitations. Existing MCP startup noise is not claimed fully resolved; no Firecrawl key is needed for supplied-evidence review. See VALIDATION.md for actual tests and native Windows limits.
