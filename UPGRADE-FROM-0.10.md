> Historical v0.11 upgrade notes. For this release use docs/START-HERE.md and Setup-POC.cmd.

# Upgrade to TD POC 0.11

1. Close the main v0.10 console using /exit. Close any failed/finished worker windows. Do not run old and new versions together while upgrading.
2. Extract this complete package to C:\TD-POC-v0.11. Retain the old folder for its historical run exports.
3. Open CMD and run:

```bat
cd /d C:\TD-POC-v0.11
copy "C:\TD-POC-v0.10\config\database.dpapi" "config\database.dpapi"
Setup-LocalModel.cmd
Initialize-Database.cmd
Start-POC.cmd
```

Use the same Windows account; DPAPI encryption is account-specific, not tied to the folder path. Copying this encrypted file locally avoids entering the password again; do not upload it. If the old file is unavailable, run Configure-Database.cmd instead. Model setup creates the new folder's isolated Python environment and builds v0.11; Ollama reuses the already downloaded embedding model. The local-file migration is idempotent and does not change the approved source-category constraint or recreate tables.

At You>, run /pilot. The previous nine registered sources and 23 vectors remain in the existing database. v0.11 reuses compatible successful v0.10 extractions and the existing immutable embedding profile; the failed DOCX is retried. A changed model digest or changed source content appropriately requires new work. The exact new-vector count depends on the DOCX and any file changes, so it is not predetermined.

Do not delete/reset the database or rerun the fresh schema installer. Data root stays C:\S3 bucket Data. If you customised appsettings.json (for example FFmpegExecutable), carry those settings into the new config, keeping PythonExecutable as .venv/Scripts/python.exe for this new folder. On your machine ffmpeg was already on PATH, so Setup-VideoTools.cmd need not be repeated.

## Why the DOCX failed

The final approved schema uses DOCUMENT for Word and PDF sources. v0.10's importer used the earlier draft labels WORD_DOCUMENT and PDF. PostgreSQL correctly rejected WORD_DOCUMENT at the source registration CHECK before document extraction. The failing file transaction rolled back; successful files were committed separately. v0.11 corrects both mappings rather than loosening the database constraint.

Your pilot: 9 registered, 6 extracted, 3 blocked (video and two PNGs), 1 failed DOCX, 23 new text vectors. Blocked video/image processing is separate from the category defect. DOCX is supported; raw MP4 and PNG are not directly embedded by the text model. Video visuals remain sampled evidence in agent tests; image OCR/native conversions remain pending. Existing original User Master recording tests still require the matching original-time SRT under the current test launcher; successful DOCX import alone does not establish SRT pairing.

## Included fixes

- Word/PDF source categories aligned with final v0.3 schema; checks cover emitted categories against actual installed constraints.
- Settings reader trims saved whitespace and uses the corrected process-scoped PowerShell invocation.
- Pilot, full-processing and status launchers use --no-build, avoiding locked running DLL rebuilds.
- Application/package version 0.11.0; schema and handoff contract versions remain unchanged. Compatible extraction processor version remains 0.10.0 intentionally to prevent needless re-extraction/re-embedding.
