# Workspace 0.26 — full release and restart guide

This is the full application, including both POCs, local web UI, chat history, source links, images, video playback, agent activity windows, database migrations and tests from 0.25. It is not a patch.

## Why processing appeared stuck

The supplied logs show processing stopped advancing at file 433 and was later cancelled. They do not prove whether the wait was Ollama, a file read or PostgreSQL. The pgAdmin row showed only pgAdmin idle at that instant. The old app printed a filename before doing the work and could wait without showing the inner operation.

0.26 adds inner-stage progress every 10 seconds, bounded waits, timeout diagnostics with the file/stage and Python stack, and bounded automatic recovery. It preserves committed vectors. After a file timeout it can resume twice, setting that unchanged file aside instead of repeatedly getting stuck there. Skipped files are explicitly listed and remain unfinished. A startup timeout or unavailable embedding service stops with an error rather than endlessly retrying. This addresses silent waiting and recovery; the historical cause is still unknown.

## 1. Close and extract

Stop any active processing with Stop in Workspace. Close the previous app and its activity windows. Keep the 0.25 folder as fallback. Back up the existing knowledge_poc database using pgAdmin.

Extract the entire new folder to C:\TD-POC-v0.26. Keep your existing data folder, PostgreSQL database and Ollama installation. Do not drop tables, delete vectors, or run the fresh-install schema SQL.

## 2. One-time setup in Command Prompt

Run these commands one at a time (without numbering):

```bat
cd /d C:\TD-POC-v0.26
Setup-POC.cmd
```

Confirm your existing data folder (normally C:\S3 bucket Data) and enter the same database connection details. Complete the isolated Codex login if requested. Setup creates this folder's Python environment, builds the app, applies existing migrations and checks indexes/model readiness. Credentials and Python environments are deliberately not bundled. Your PostgreSQL sources, vectors, chats and reviews remain in the same database.

Wait for SETUP PASSED, then:

```bat
Start-POC.cmd
```

Choose 1 for Gap Analysis or 2 for Knowledge Retrieval. Open the localhost address printed by the app. Leave the main window open. Setup uses the existing local qwen3-embedding:4b model (2560 dimensions); Codex handles reasoning separately.

## 3. Resume ingestion

In Workspace, click Scan files, then Process new files. Scanning inventories files; processing imports supported content and fills missing vectors. Existing successfully saved vectors are reused. The first scan still hashes the dataset, so it can take time on large folders/videos.

The Processing window shows the current inner stage. Every 10 seconds it reports the active file or startup, operation and elapsed time. A heartbeat means the host is checking the deadline, not proof the external service is progressing.

Defaults: local embedding request socket timeout 120 seconds; inner stage deadline 180 seconds; whole-file deadline 1800 seconds; SQL statement timeout 120 seconds; SQL lock timeout 10 seconds. Configure these in config/appsettings.json if real measured operations need longer. Limits apply to importing/scanning; agent reasoning keeps its existing separate timeout.

After a hard stage timeout the app records diagnostics before terminating that import attempt, then allows at most two recovery attempts. The offender is set aside while unchanged. The final attempt's totals list files set aside; earlier attempts' committed work remains saved and logged. These totals are not cumulative across recovery attempts. A missing/unresponsive embedding service normally stops the batch for investigation rather than failing thousands of files.

Use Retry timed-out files after resolving the cause. It explicitly retries previous timeout exclusions, while avoiding reattempting the same newly timed-out file during that invocation's recovery. A changed file is eligible automatically. Console users can run Retry-TimedOut.cmd. Do not start a second processing job concurrently.

## 4. If anything stops again

Do not reset PostgreSQL or delete vectors. Capture the visible message. Run:

```bat
Export-ImportDiagnostics.cmd
```

The ZIP is written beside the application. It contains import state, timeout exclusions, stack traces and worker error logs. It excludes database credentials and Codex login files. Paths/logs may reveal internal filenames or source details; share with your authorized reviewer. The key files are runtime/import-state.json, runtime/import-timeouts.json and runtime/import-traces/<attempt>/python-stack.log.

A file set aside is unfinished, not silently counted as successfully ingested. If the recovery limit is reached, review the diagnostics before retrying. A health-log write failure stops processing explicitly rather than leaving an unmonitored wait.

## 5. Recheck both POCs

After processing completes, POC 2: choose Videos, select a ready video, and ask: "Explain the main steps demonstrated in this recording. Cite timestamps and show relevant screenshots. Separate spoken instructions from what the frames establish."

Then: "Compare this with the documentation. What is confirmed and what remains unclear?"

POC 1: start a new chat, use /review and provide the existing recording path (matching imported SRT required). Wait for Agent A and then B to finish. Use /results latest and ask: "Which topics need rework, why, and which sources support each finding?"

Source links, per-chat history and image/video features are retained. This release does not introduce new product facts or automatically approve incomplete evidence.

## Verified before packaging

157 Python tests; 26 runtime host checks plus 41 Knowledge host checks; 20 real sample-video checks; five web API groups; six additional real PostgreSQL/embedding recovery checks, including a deliberately stalled response, stack capture, safe resume, explicit retry and database statement timeout. .NET Release build: zero errors and zero warnings. Tests use a controlled embedding service and model fixtures, not your live Ollama/Codex account. Windows-native launch/PowerShell windows and rendered browser layout could not be exercised in this Linux environment. Your exact historical stall is not reproduced or attributed to a proven cause.
