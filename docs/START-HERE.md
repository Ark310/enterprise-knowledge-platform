# Start here — v0.12

## Install once

1. Stop the old POC. Keep the v0.11 folder as a backup. Extract this ZIP so the solution is at C:\TD-POC-v0.12 (avoid a second nested folder).
2. Keep C:\S3 bucket Data and PostgreSQL untouched. Do not run the fresh-install SQL again.
3. In CMD run:

```cmd
cd /d C:\TD-POC-v0.12
Setup-POC.cmd
```

4. Accept the data-root default or supply the folder containing current-state and existing-assets. The script checks dependencies, sets up its own Python environment, verifies the local model, builds, prompts for PostgreSQL host/port/user/hidden password, applies the existing idempotent migration, checks ffmpeg, and checks Codex.
5. Complete the ChatGPT login if prompted. v0.12 deliberately uses its own Codex home so unrelated personal connectors cannot start. No API key is required. config/codex-home contains credentials: do not share it or the whole configured folder. Export-LatestRun.cmd excludes it.
6. Setup requires your already installed approved schema, PostgreSQL 17+, pgvector, Python 3.11+, .NET 10 SDK, Codex and Ollama. It checks prerequisites; it does not install PostgreSQL, reset tables, or silently change system execution policy.
7. Wait for SETUP PASSED. No source ingestion occurs during setup.

The optional corrected SRT is in data-fixes/current-state. If you have not already replaced the invalid original, back up the old SRT outside the data root and copy this same-named corrected SRT into C:\S3 bucket Data\current-state. Keep the MP4 and DOCX. This is the previously supplied format repair, not verified audio alignment.

## Start and test

```cmd
cd /d C:\TD-POC-v0.12
Start-POC.cmd
```

Wait for startup readiness and scan. Then, at You>:

```text
/status
```

If files changed, or vectors may be missing:

```text
/process
```

Wait for the worker window to finish; check failed=0 and empty failures/scan_errors. Known blocked images, videos without text extraction, .snag and legacy unsupported formats can remain blocked. The scan's pending count includes those unsupported files, so it need not reach zero. Existing successful extractions/vectors are reused when hashes, parser version and model digest match; no forced full reimport.

Next:

```text
/test T02
```

Recording prompt:

```text
current-state\System Admin_ Security_User Master Walkthrough.mp4
```

A activity opens, then A validation/save/local embeddings, B retrieval, then B activity and B validation/save/local embeddings. These run in order. Activity windows show execution events, elapsed time and terminal status. COMPLETED in a viewer means only that Codex exited; main-console validation/database storage must also succeed. Close completed viewer windows when convenient.

After T02, in another CMD:

```cmd
cd /d C:\TD-POC-v0.12
Export-LatestRun.cmd
```

Upload the reported ZIP for review before continuing. Other cases, one at a time:

```text
/test T04
/test T05
```

Use the same recording path when prompted. T02 covers Authentication Type/2FA (495–570 seconds), T04 Time Zone (90–165), T05 Profile (650–705). Never feed reviewer expected answers to the agents.

## Cancel and diagnose

Press Q in the active activity window to request cancellation, or Ctrl+C in the main window while Codex runs. The host stops that process tree, retains partial files, marks the workflow failed where the DB is reachable, and returns control. No successful handoff is claimed. Cancellation during a database/embedding worker is not part of this Codex cancellation path; allow the worker to complete or preserve logs before closing.

Closing an activity window alone does not stop the agent. If the main console was left in manual selection mode, press Esc. QuickEdit is disabled for this application but explicit selection modes may still pause console writes. Logs/heartbeat keep running independently of main-console progress writes.

Export-LatestRun.cmd can snapshot an active or cancelled analysis run. Files are copied with read/write sharing; a snapshot is not an atomic database backup. Inspect export-snapshot.json for copy warnings. Never send config/database.dpapi, config/codex-home, or an entire installed application directory.

Each run holds prompt-a.txt, prompt-b.txt, evidence-a.json, evidence-b.json, raw final output, agent-a/b.json when consumed, validation-a/b.json when reached, a/b-events.jsonl, a/b-stderr.txt, a/b-activity.log and a/b-status.json. Status can be RUNNING, COMPLETED, FAILED, CANCELLED or TIMED_OUT. Heartbeats indicate host liveness, not hidden reasoning or confirmed model progress. Default timeout remains 25 minutes per agent, adjustable in config/appsettings.json.

## Files and responsibilities

- Setup-POC.cmd / scripts/Setup-POC.ps1: combined setup; individual older setup commands remain for troubleshooting.
- Start-POC.cmd: starts the prebuilt host after setup.
- src/TD.Poc.Console/Program.cs: CMD commands and readiness.
- src/TD.Poc.Core/Workflow.cs: A → validation/save/embedding → B → validation/save/embedding.
- src/TD.Poc.Infrastructure/Runtime.cs and AgentProcess.cs: controlled process launch, credential isolation, live logs, cancellation, activity windows.
- tools/worker.py: extraction, PostgreSQL, shared Ollama embedding profile, retrieval and contract/provenance gates. The host writes records on behalf of agents; reasoning agents do not connect directly to PostgreSQL.
- agents/agent-a-current-state.md, agent-b-documentation-review.md, agent-c-coordinator.md, shared-guardrails.md: instructions. Original A/B instructions and contracts remain bundled.
- docs/architecture-and-tables.html: combined workflow and all 29 tables/55 relations. This schema is unchanged in v0.12.

A/B findings remain AGENT_PROPOSED. Schema and literal citation validation do not replace human factual review. Transcript narration is not proof that a screen transition/save/login succeeded. No product API calls or documentation publishing occur.
