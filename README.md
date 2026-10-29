# TD POC v0.15

Read docs/START-HERE.md. Fresh run:

```cmd
cd /d C:\TD-POC-v0.15
Setup-POC.cmd
Start-POC.cmd
```

At You>: `/review`, then `current-state\System Admin_ Security_User Master Walkthrough.mp4`.

Main console: start/stage completion and compact results. One A activity window follows ALL sections/consolidation/save/embedding; one B window follows ALL searches/batches/save/embedding. No per-call viewer windows. Startup and C chat do not open A/B windows. Q in the active role window or Ctrl+C in main cancels active work. Closing a viewer alone does not cancel it.

Explicit UTF-8 and ASCII-safe JSON fix the Windows Python/C# Unicode handoff defect. Content is preserved, not replaced. Every worker's stdout/stderr and exceptions are saved; failure.json and workflow-state.json identify the failing phase. Agent handoffs pass validation before DB storage/embedding. B rows link to A records and cited source units under the existing local profile. No schema reset or forced reimport.

/results latest selects one saved gap report; /ask and subsequent ordinary questions use it. /search remains general cross-run retrieval. Full results: gap-list.json and gap-list.txt. Export-LatestRun.cmd includes the diagnostics. Optional guarded /resume supports eligible failures before or after A save, verifying sources/records/vectors and refusing ambiguous/B-already-saved states; see guide. Start fresh for the requested first v0.15 test.

51 Python tests and host/database verification are described in VALIDATION.md. Native Windows execution and live semantic quality still need the first server run. Codex reasons using ChatGPT login; Qwen3-Embedding 4B embeds locally. Stored findings are proposed retrievable memory, not model training.
