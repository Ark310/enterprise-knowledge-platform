# v0.15 — one clean whole-recording review

## Install and start

Keep v0.14 as a backup. Close its main POC and activity windows. Extract the new package to C:\TD-POC-v0.15 so Setup-POC.cmd is directly inside it. Do not delete PostgreSQL, vectors, the data folder, or previous run evidence.

Open CMD:

```cmd
cd /d C:\TD-POC-v0.15
Setup-POC.cmd
```

Accept the data folder C:\S3 bucket Data if unchanged. Enter localhost, 5432 and postgres unless your settings differ, followed by your hidden database password. Complete the POC ChatGPT login if prompted. Setup checks dependencies, reuses the existing embedding model, creates the new folder's Python environment, builds the solution, configures the connection, applies the existing idempotent local-file migration, checks video tools and verifies Codex readiness. It does not reset the schema or import source data.

After SETUP PASSED:

```cmd
Start-POC.cmd
```

Wait for readiness and the scan. The corrected recording/SRT were already imported; if unchanged, you do not need /process. The 12,734 pending count seen earlier includes known unsupported formats; it need not become zero.

## Run fresh

At You>:

```text
/review
```

Recording prompt:

```text
current-state\System Admin_ Security_User Master Walkthrough.mp4
```

This creates a NEW run. A reviews every scheduled two-minute section of the recording with approximately two-second frame sampling and supplied SRT cues, then consolidates topics. The host validates source references and topic accounting, stores A's observations and embeds them. Only then is A's phase completed and B's started. B performs separately audited bounded searches per topic, assesses batches of three topics, and returns exactly one coverage row per indexed topic. The host validates, stores and embeds B rows and links them to A/source records. The JSON/text report is then saved and selected for C.

This is a longer review than T02. The 12m55s video has seven A section calls, one consolidation call, and B calls according to the discovered topic count. Latency depends on model response and retrieval. No specific completion-time promise is made. Every represented observation/topic must be accounted for, but sparse video and bounded retrieval do not prove every product feature or every transient action was examined.

## What windows you should see

Main: compact readiness, Agent A working/completed, Agent B working/completed, final summary and topic/status list.

One A window: all section steps, model events, elapsed heartbeat, consolidation, validation, PostgreSQL save and local embedding progress. It remains the SAME window for all A calls.

One B window: per-topic retrieval progress, all assessment batches, validation, PostgreSQL save and local embedding progress. It remains the SAME window for all B calls.

Completed role windows stay open until you press Enter, so you can inspect them. Closing a viewer does not stop work. No A/B viewer opens for startup readiness or ordinary C questions. /process still opens its separate import worker only when you explicitly request it.

Press Q in the active A/B viewer or Ctrl+C in the main window to request cancellation. The host stops its active reasoning/worker process, retains partial files, marks failure where the DB is reachable, and does not claim final success. Closing the main console abruptly can bypass orderly failure marking; prefer cancellation first. QuickEdit is disabled for main/viewers; explicit manual text selection can still pause rendering, so Esc leaves selection mode. Complete logs are saved independently of viewer rendering.

## Read and discuss the exact results

```text
/results latest
```

This selects the latest WHOLE-RECORDING run and shows compact status/topic rows. Failed/incomplete runs do not silently fall back to an earlier success. The full report is saved as gap-list.txt and gap-list.json. Each coverage row is also stored in PostgreSQL and embedded; the combined A/B JSON is in analysis.agent_outputs.

Ask C normally after selecting/completing a report:

```text
Which topics have no adequate article in the reviewed sources?
Which existing articles need rework, and what exactly needs changing?
Which topics are adequately documented? Cite those articles.
What must be confirmed by a person before writing anything?
```

Or:

```text
/ask Summarize the missing coverage and proposed work, with topic IDs and article references.
```

/results <exact-run-key> selects an earlier broad run. After restarting, use /results latest again. /search is general semantic retrieval across source/derived records and can mix runs; /ask is exact-run discussion. Current source revision flags disclose superseded evidence. Findings remain AGENT_PROPOSED; no article is automatically written/published.

Coverage: COVERED, NEEDS_REWORK, NOT_FOUND_IN_REVIEWED_SOURCES, NEEDS_REVIEW. Not-found is qualified to the reviewed sources, not company-wide absence. Unknown product behavior or unread relevant guidance must not be forced into a create/update decision. Overall PARTIAL is normal for sampled/bounded human-unapproved reports; it does not itself mean execution failed.

## Export success or failure

In a separate CMD:

```cmd
cd /d C:\TD-POC-v0.15
Export-LatestRun.cmd
```

Share that ZIP. It includes role activity/status, workflow-state.json, raw model responses/events/stderr, per-operation worker stdout/stderr, section and batch validation, topic-index normalization audit, evidence packets, outputs and final reports when reached. On failure it includes failure.json (the first captured error) plus failures/ entries for subsequent diagnostic context. No database connection secret or Codex login files are included. Never upload the whole configured installation folder.

If it stops, keep the failed run folder. The main window shows a concise failure; the role window and exported files contain details. Do not reset/reimport data as a response to an agent failure.

## Optional recovery without repeating saved A work

You requested a fresh run first; use /review above. For the known older failure, optional:

```text
/resume C:\TD-POC-v0.14\runtime\runs\TD-MODULE-20261029144637-b22d55
```

The host requires a matching FAILED run, unchanged current imported recording/SRT, complete valid saved sections/frames, and either no saved outputs or exactly one matching valid A output with matching observation records and embeddings under the unchanged model fingerprint. With A already saved, it skips reanalysis/consolidation and does not duplicate A rows/vectors. It restarts B retrieval/assessment. It refuses B-already-saved, ambiguous or mismatching records. Files are copied into the current runtime/runs; the original folder remains intact. A previously saved topic index is reused unchanged, so it does not retroactively gain new deduplication rules. Interrupted B batches are not automatically certified or silently skipped; B reruns against freshly retrieved evidence.

## Specific corrections and limitations

- Python/C# input/output explicitly use UTF-8; worker protocol JSON uses ASCII escapes, which preserve all original Unicode on decoding. Real failed-run content including □ is not dropped or transliterated.
- Main console remains compact. Two role viewers replace per-call windows and the excessively verbose main-console progress layout.
- Module context prefix 'Contoso Canada' is explicitly configured in config/appsettings.json as organizational display context. It is removed ONLY from topic identity, not original observations/citations. Case, spaces and navigation separators are normalized; identical topic titles under that identity can merge. Other product prefixes are not guessed aliases. The raw proposal and complete source-label mapping remain in proposed-topic-index.json and index-normalization.json.
- Original contracts, 29-table schema, source parser fingerprint and model are retained. The whole review uses td-module-review-1.0; targeted /test T02/T04/T05 still use the original td-doc-review-2.0 contract. No new database migration.
- The old Firecrawl MCP authentication startup warning may still occur. It is recorded in raw stderr and summarized once per role as an optional connector warning. It is NOT relabelled as successful execution; actual exit/validation still gates the handoff. No Firecrawl key is required. This release does not claim the external connector startup attempt is eliminated.
- Stored vectors are retrievable memory, not training of Codex weights. Source chunks, A observations and B rows share the local model/profile; evidence stays separate from proposed analysis.

Agent instructions: agents/agent-a-module.md and agent-b-gaps.md. C# orchestration: src/TD.Poc.Core/ModuleReview.cs. Worker/storage: tools/worker.py and module_review.py. Process/UI plumbing: Runtime.cs, AgentProcess.cs and RoleActivity.cs. Workflow/all tables: docs/architecture-and-tables.html. Test evidence and native Windows limits: VALIDATION.md.
