# Workspace 0.26 corrected — update and resume

## What the export proves

Access was denied in the application's activity display: Runtime.WriteRoleState could not replace an agent .status.json file. It was not an access-denied error reading C:\S3 bucket Data. The exception stopped the host's progress reader. Python then blocked printing progress to that undrained pipe; its captured stack confirms this. The watchdog eventually stopped that attempt, and the host's display exception prevented normal recovery. The file marked timed out was not thereby proven corrupt.

The last scan completed with 34,824 files and no scan errors. It detected 33 VLC MP4s and their 33 SRTs. Videos were REGISTERED_MEDIA; transcripts were NEW_OR_PENDING. Processing stopped around item 376, before the VLC transcripts were reached. The transcripts were discovered, but not yet successfully imported. The export does not establish why Windows denied the status replacement (for example, a temporary lock versus another filesystem restriction).

## What is corrected

- Activity display writes are isolated from ingestion and cannot stop draining the worker's progress pipe. A denied status update becomes a visible display warning, not a failed ingestion.
- Progress heartbeat output is bounded, avoiding a new blocked logging thread on every heartbeat.
- Reporting/structural timeouts do not blame or exclude the current source file as if its content failed.
- Scan database comparison uses one inventory query rather than one query per file, with checked/total counters.
- Scope covers all folders under current-state and existing-assets. The top-level existing-assets/Meeting Recordings subtree is excluded. Symlinks/junctions and temporary Office lock files remain excluded.
- Supported text/transcript formats are extracted and missing vectors are created. Unsupported binary formats remain explicitly blocked for conversion/OCR. Scanning all files does not mean every format can be understood automatically.
- General questions can retrieve transcript passages without a manually selected recording. Video selection is still useful for a deliberately scoped demonstration, but is not required for ordinary transcript retrieval.

This is a corrected full 0.26 release. It retains both POCs, source links, chats, images, video functions and the existing database schema/model. It does not silently approve unsupported answers or rebuild all vectors.

## Update your existing installation

1. Stop active work, then close the application and its activity windows.
2. Keep a backup of your existing application folder. Keep the PostgreSQL database and data folder unchanged.
3. Extract TD-POC-v0.26-corrected.zip over C:\TD-POC-v0.26, replacing the application files. It contains no .venv, database.dpapi, Codex login, or runtime directory; leave your existing copies of those in place. If you customized appsettings.json, keep your existing settings (the exported settings match this build's defaults).
4. In Command Prompt, rebuild and start:

```bat
cd /d C:\TD-POC-v0.26
dotnet build TD.Poc.sln --configuration Release
Start-POC.cmd
```

If installing in a completely fresh folder, run Setup-POC.cmd before Start-POC.cmd instead; connect to the same existing database. Do not run the fresh schema installer or delete vectors.

## Resume once Ready

1. Click Scan files and wait for completion. Startup may already have scanned; avoid starting another job while one is active.
2. For this first retry, click Retry timed-out files. It processes pending files as well and allows the file incorrectly set aside after the logging failure to be tried again.
3. Wait for totals. Inspect failed files, set-aside files and scan errors. A successful scan alone does not create searchable vectors.
4. Open Videos: the newly imported VLC transcripts should be ready when their processing succeeded. If a particular SRT is not ready, use its reported error rather than assuming a folder permission problem.
5. On later imports use Scan files, then Process new files. Existing committed vectors are reused.

## Test general retrieval (POC 2)

Start a new chat with no videos selected. Ask:

"How do I book a forward in TradeDesk? Look across the imported articles and training transcripts, explain the documented steps, and cite the original sources. If you use a transcript, include its timestamps."

Then follow up in that chat:

"Which parts of that answer came from training recordings, and what outcomes do those sources not establish?"

A second independent question:

"What does the imported training material explain about setting up a corporate client? Compare the useful sources and flag anything that needs clarification."

These are general topic questions, not forced source filters. Retrieval is bounded and may legitimately return articles instead of a video if those are more relevant. The checks below establish the ability to retrieve transcripts, not guaranteed accuracy for every question. Specific product instructions still need source evidence.

## Verification

158 Python tests; 29 runtime host checks plus 41 Knowledge host checks; 20 video checks and five API groups. A deliberately unwritable activity-status destination plus 15,000 progress lines completed without blocking ingestion. A general topic query without video names/selection retrieved imported SRT passages. Original sample file states were compared with exactly one database query. Controlled stalled-service tests confirmed stack capture, bounded stop, safe continuation, explicit retry, retained vectors and SQL deadlines.

Tests use Linux, a real temporary PostgreSQL database, supplied sample videos and controlled embedding/Codex fixtures. They cannot recreate the exact Windows status-file lock or verify your live service/account. Windows-native viewer behavior still needs confirmation on your server. If another failure occurs, run Export-ImportDiagnostics.cmd; do not reset the database.
