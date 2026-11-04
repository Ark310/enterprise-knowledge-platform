# TD POC v0.17 — upgrade and test, step by step

This uses your existing `knowledge_poc` database. Do not delete it, rerun the fresh schema installer, or delete v0.16. Production-schema redesign and the writer/ReadMe work remain paused.

## What changed

- Original transcript cues and all old citation IDs remain intact. New grouped passages are stored alongside them; unchanged documents reuse their vectors.
- Grouping starts around 30 seconds, ends at sentence boundaries where possible, and normally limits passages to 60 seconds/1,800 characters. Long pauses break groups. Oversized individual cues split by characters while retaining original timestamps/character offsets; timestamps are not invented. These are configurable-code POC defaults, not proven ideal semantic topic boundaries.
- Grouped passages retain cue provenance, parent section and neighbouring context. A matching video is linked to its exact imported revision; duration bounds are checked. Filename pairing does not prove speech alignment. Standalone transcripts remain explicitly marked unpaired.
- Selected video frames are reused from a hash-verified local cache. PostgreSQL stores frame locators/hashes and finding links, not images or MP4 bytes. This is not OCR, exhaustive video understanding, or automatic frame embedding.
- Keyword search remains. Halfvec HNSW retrieves candidates; original vectors rerank them. Source and saved-finding indexes are separate. The actual database query plan is reported.
- A/B/C, handoff validation, T02/T04/T05 and whole-module /review remain available. Agent A still cites original cues/actual frames; grouped context helps reading without replacing those citation IDs.

## 1. Stop the old app

Finish any active processing first. Type `/exit` in the main console and close completed worker/activity windows. Keep `C:\TD-POC-v0.16` as your rollback copy.

## 2. Extract this release

Extract the ZIP so this file and `Setup-POC.cmd` are directly inside:

`C:\TD-POC-v0.17`

Do not copy `.venv`, `bin`, `obj`, passwords or Codex login files from an older folder. This release recreates its environment. Your data folder stays at `C:\S3 bucket Data`.

## 3. Back up the current database

In a new CMD window:

```bat
cd /d C:\TD-POC-v0.17
"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" -h localhost -p 5432 -U postgres -Fc -f "C:\TD-POC-v0.17\knowledge_poc-before-v017.dump" knowledge_poc
```

Enter your PostgreSQL password when asked. If PostgreSQL is installed elsewhere or uses another username/port, adjust those values. Confirm the command finishes without errors and the dump exists. This command does not alter your database. Keep the dump private.

## 4. Run setup once

```bat
Setup-POC.cmd
```

It sets up Python dependencies, retains the existing local Ollama model, builds/tests the solution, asks for the data folder and database credentials, applies additive POC changes, and builds/verifies HNSW indexes for the detected model profile. It then checks video tools and the isolated Codex login. Complete login if prompted.

Database prompts for your same-machine setup normally are:
- Host: press Enter for `localhost`.
- Port: press Enter for `5432`.
- Username: press Enter for `postgres` if that is still your account.
- Password: your PostgreSQL password, not your Windows/ChatGPT password.

Index creation can take several minutes and uses CPU/RAM in PostgreSQL, separately from the embedding GPU. Source/finding vectors are retained at full precision; the index uses half precision. Setup validates dimensions; it does not assume 2,650 or 3,650. Earlier model output was 2,560.

If an import is running, index setup refuses to proceed. Finish it and run `Build-Search-Indexes.cmd`. If setup fails, stop and retain its exact error; do not reset the database.

## 5. Start the POC and prepare the improved transcripts

```bat
Start-POC.cmd
```

Startup scans only. It now shows transcript grouping pending separately from unchanged original files.

In the main POC window:

```text
/process
```

A worker window opens. Let it finish; do not launch another worker or a test simultaneously. It reuses existing extractions/vectors, prepares grouped SRT passages and embeds only missing/new units. Unsupported video/image formats can still show BLOCKED as in v0.16; that is separate from a failed transcript job. The first grouping pass may take time across your transcript collection.

Expected: `failed: 0`, plus `grouped_embedded` showing new grouped vectors. `embedded` is the existing source-unit counter; `grouped_embedded` is an additional counter, not a total. Fix any failure before using its affected transcript.

Then run in the main window:

```text
/search-health
```

Check `hnsw_ready: true`, the actual `dimensions`, and `grouped_transcripts`: ready should increase and pending should ideally be zero. If all transcripts remain pending, do not interpret a three-mode run as a chunking improvement.

## 6. Compare the three searches

These commands run database searches; they do not invoke Codex or create a new gap-analysis run:

```text
/compare How do I reset a user's password in User Master?
/compare How are user permissions and security roles configured?
/compare What does the training material say about confirmations?
```

Each uses one question embedding and one repeatable-read database snapshot:

| Mode | What it searches | What it demonstrates |
|---|---|---|
| old_exact | Original cue-sized passages and existing documents | Baseline |
| improved_exact | Ready grouped transcript passages and the same existing documents | Effect of grouping/context |
| improved_hnsw | Exactly the same eligible improved corpus as improved_exact | ANN retrieval versus exact |

The main window reports database milliseconds, matches, actual HNSW use and semantic recall@k. Full results, paths, locators, neighbours and query plans are saved under `runtime\comparisons` as JSON and readable Markdown. Open the Markdown to compare evidence; share the matching JSON for diagnosis. No assertion is made that overlapping results are factually correct.

`old_exact` versus `improved_exact` may have different chunk IDs; compare source/version coverage and completeness. ANN recall compares only improved exact semantic neighbours with improved HNSW semantic neighbours. Hybrid top-k overlap is reported separately. An empty exact reference has undefined recall (`null`), not 100%.

If HNSW use is false, the result is not an ANN performance measurement. Comparisons request the ANN access path and retain the actual plan; missing/invalid indexes require `Build-Search-Indexes.cmd`. Very selective filters can still reduce available ANN candidates; a higher recall budget may be needed. No claim of guaranteed 100% recall or universal speedup.

Run each question a few times to see warm-cache behaviour. Timings exclude model loading, query embedding and Codex reasoning; the fixed mode order is not a rigorous production latency benchmark.

## 7. Ask the user-facing agent

```text
/mode improved_hnsw
/search How do I reset a user's password in User Master?
```

`/search` invokes Agent C using retrieved evidence. To try another mode:

```text
/mode old_exact
/search How do I reset a user's password in User Master?
/mode improved_exact
/search How do I reset a user's password in User Master?
/mode improved_hnsw
```

Mode selection applies to this session and to new reviews/tests. A review pins its mode at creation so an A→B handoff cannot silently change search mode. Source-group permissions are the existing internal POC scope; this is not the paused production tenant-isolation feature.

## 8. Run the same agent tests

Start with one test and wait for it to finish:

```text
/test T02
```

At its recording prompt, enter only:

```text
current-state\System Admin_ Security_User Master Walkthrough.mp4
```

Agent A activity appears in its window, then Agent B, then the main console reports the saved run folder. After checking that result, run `/test T04`, then `/test T05` using the same recording path. The original test requests are unchanged. Outcomes still require evidence/human review; this upgrade does not predeclare their answers.

For the complete module gap list:

```text
/review
```

Enter the same relative video path. Then:

```text
/results latest
/ask Summarize the missing documentation and the topics needing review.
/ask Why does User identity and credentials need review? Cite the evidence and limitations.
```

`/compare` measures retrieval. It does not automatically run all three full A/B workflows. To compare full workflows, choose a mode, start a new `/review`, save/export it, choose the next mode and start another new review. These remain stochastic reasoning runs, not a controlled search-only benchmark.

## 9. Export and send results

From a second CMD window:

```bat
cd /d C:\TD-POC-v0.17
Export-LatestRun.cmd
```

The run ZIP includes its referenced cached frames/diagnostics and `referenced-media-map.json`; it does not include unrelated cached videos or credentials. For search comparisons, also send the relevant `.json` and `.md` files from `runtime\comparisons`. Exported material contains internal evidence; use your authorized review channel.

## 10. Add another recording later

Copy the MP4 and matching-basename SRT completely into `current-state`. Then `/scan`, `/process`, wait for completion, `/search-health`, and `/review` with its relative path. Do not modify media/transcripts during processing or a review. Timing failures are reported; timestamps are never silently repaired.

## Roll back the application

Close v0.17 and start the retained v0.16 folder. Original active extractions, original vectors and historical IDs were not replaced. Leave the additive tables/indexes in place while investigating; do not drop them or restore over live data automatically. A database restore is a separate deliberate recovery action, not the normal application rollback.

## What was verified here

See `docs\verification-v017` and `VALIDATION-v017.md`. No live connection was made to your server; no real Codex/Ollama end-to-end run was performed here. Complete the above checks on your Windows machine before a demo. The production schema, cross-client sharing, privacy/approval policy and writer/ReadMe workflow are explicitly parked.
