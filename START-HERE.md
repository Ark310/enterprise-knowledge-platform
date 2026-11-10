# Workspace 0.027 — full release, resume and video tests

## What changed

The 0.26 export showed a PermissionError saving monitoring status. The monitor deliberately exited 125, leaving no final JSON and causing the misleading "invalid JSON" message. This release removes that dependency: optional health snapshots and importer progress logs are written in bounded background queues. Denied or slow status writes produce a warning without stopping ingestion or deadline checking. Status replacement has short bounded retries; snapshots have a single writer. Loading the timeout list has a bounded wait as well.

A real timed-out operation still stops. The host reads its structured reason from the captured process output even when status files are unavailable. Automatic recovery requires a matching attempt ID and a successfully persisted timeout checkpoint; otherwise it stops clearly without guessing which file to exclude. A status-only problem does not mark a source file as corrupt. Latest failure summaries now replace old summaries, while dated failure history remains.

Both POCs, chat history, source hyperlinks, image uploads, original frame galleries, playback links, agent activity windows, chunking and HNSW retrieval are retained. The embedding model/profile and extraction versions are unchanged so saved vectors are reused. No new database schema, model or retrieval strategy is introduced. Scope remains current-state plus all existing-assets subfolders, excluding existing-assets/Meeting Recordings, symlinks/junctions and Office lock files. Unsupported content formats remain explicit conversion/OCR work, rather than silently claimed searchable.

## 1. Close the old application

Stop active work using Stop if needed. Close the application and its activity windows. Keep the old 0.26 folder as fallback; previous cached-image references may still point there. Keep the PostgreSQL database and the original S3 bucket Data folder. Back up knowledge_poc using pgAdmin before setup.

Do not delete tables, clear vectors, or run the fresh schema installer. Do not change Windows folder permissions or disable protection to work around this monitoring bug.

## 2. Extract the full ZIP

Extract TD-POC-v0.027.zip so this file exists:

C:\TD-POC-v0.027\Setup-POC.cmd

The ZIP contains the complete source, scripts, contracts, schema/migrations, tests and instructions. It deliberately excludes your Python environment, credentials, login files, runtime logs and source videos. Your existing videos/transcripts stay in C:\S3 bucket Data.

## 3. One-time setup for this new folder

Open Command Prompt. Run one command at a time:

```bat
cd /d C:\TD-POC-v0.027
Setup-POC.cmd
```

Confirm the existing data root C:\S3 bucket Data (or your actual root). Enter your existing PostgreSQL connection details; use the same knowledge_poc database. Complete the isolated Codex sign-in if requested. Setup creates the new folder's .venv, builds the solution, applies the existing migrations and checks indexes and the local model. It preserves database sources, vectors and chats.

Wait for SETUP PASSED. Then run:

```bat
Start-POC.cmd
```

Choose 2 for Knowledge Retrieval and Verification. Open the localhost URL printed by the app. Leave the main CMD window open. The local embedding model is qwen3-embedding:4b, 2560 dimensions; Codex still supplies reasoning through its saved login.

If setup fails, read that failure before starting processing. Do not continue with missing dependencies or failed database readiness.

## 4. Finish ingestion before testing

1. Wait for Workspace to show Ready. Startup may already be scanning; avoid duplicate concurrent jobs.
2. Click Scan files. Wait for its completion message.
3. Click Process new files. Existing committed vectors are reused; pending transcripts and new supported files receive vectors. Registered MP4 alone does not mean its transcript is ready.
4. Wait for processing totals and inspect failed files, scan errors and timeout exclusions. Do not launch another job while one is active.
5. If copied timeout state from an old installation causes files to be set aside, use Retry timed-out files after reviewing their cause. This action also processes other pending files. A fresh 0.027 folder does not inherit the old timeout list unless you copy it.
6. Open Videos to check the VLC recordings' readiness. Their matching SRTs should have the same basename and sit beside the MP4, e.g. Sections 3 and 4 [iuinh8jZ7J8].mp4 and Sections 3 and 4 [iuinh8jZ7J8].srt.

Processing may take time for long transcripts; progress updates show the active file/stage. A "Monitoring warning (nonfatal)" means a display/log update failed while import continues. A genuine embedding, file-read or database error remains an actual processing error. A heartbeat alone is not proof an external model is advancing. Ingestion remains manual.

The previous scan found 33 VLC videos and 33 SRTs. The previous process stopped before VLCs; their old pending status was not evidence the scanner ignored them. The known TinyTake21-10-2025-05-52-07.srt error is separate: its parser found no usable cues. Such a file is reported individually while other files continue. No transcript content or timings are invented to make it pass.

## 5. Run the video questions

Use the included Video-Test-Questions-v0.027.txt. Begin with the general question in a new chat with no recordings selected. Then try the named-recording and cross-video questions. Answers should cite original sources/timestamps and show frames only where available and relevant. General transcript retrieval does not require selecting a video, but selecting one is useful when you deliberately want to limit a demonstration to it.

For POC 1, start it using Start-POC.cmd and choose 1. In a new chat, enter /review and provide:

```text
current-state\System Admin_ Security_User Master Walkthrough.mp4
```

Wait for A then B. Use /results latest, then ask: "Which topics need rework, why, and which sources support each finding?" The matching SRT must already have been processed. This release does not change A/B review behavior.

## 6. If processing stops

Capture the actual error and run:

```bat
cd /d C:\TD-POC-v0.027
Export-ImportDiagnostics.cmd
```

Keep your database. Share the generated diagnostic ZIP with an authorized reviewer. Logs may contain internal file paths/excerpts. Monitoring files can be stale if their writes are denied; the final result/error in Workspace and captured importer output are authoritative. If a checkpoint cannot be saved on an actual timeout, the app stops without automatic file skipping. It does not claim completion.

Default import limits remain 180 seconds per inner stage, 1800 seconds per file, 120 seconds per SQL statement and embedding socket request, 10 seconds for a SQL lock. A per-stage timeout is not the total batch duration. Change limits only after checking a measured legitimate long operation. The app cannot guarantee every possible machine/storage/model failure is recoverable.

## Verification and limits

162 Python tests; 33 runtime host checks and 41 Knowledge host checks; eight real PostgreSQL 17/pgvector integration checks. Tests cover denied and slow health writes, slow timeout-list reads, a genuine timeout with unwritable status storage, denied raw progress logs with 15,000 output lines, conservative checkpoint handling, truthful exit-125 reporting, latest-error summaries, malformed-SRT isolation, saved vectors reused after restart, new video/SRT ingestion and a general query retrieving transcript evidence without selecting a video. .NET Release build: zero warnings and errors.

The database/media tests use a generated short MP4, controlled embedding vectors and temporary PostgreSQL. These establish wiring and recovery, not live-model answer accuracy or a complete replay of your 34,823-file dataset. Windows-native viewer windows, your exact Windows file lock and your live Ollama/Codex account could not be tested here. Earlier versions' verification notes remain historical and do not replace this release's results.
