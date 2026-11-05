# TD v0.22 — setup and fair POC 2 retest

This release improves **Knowledge Retrieval and Verification (menu 2)**. It searches important topic words ahead of generic words such as setting/permission, understands inflections such as posting/posted, removes identical complete document text from optional retrieval slots, and lets verifier feedback change the follow-up keyword search. Answers have clear sections, numbered steps and short source labels. Full original evidence and paths remain in exports. Existing named-video, chronology and publication gates are retained. Gap Analysis's Agent A/B workflow is retained.

## 1. Prepare
1. Close the older POC and its activity/processing windows.
2. Back up `knowledge_poc` in pgAdmin. Keep the old folder as a fallback.
3. Extract this ZIP so `Setup-POC.cmd` is directly inside `C:\TD-POC-v0.22`.
4. Keep your data in `C:\S3 bucket Data`. Keep matching MP4/SRT files together. Do not recreate the database or run the fresh-schema SQL installer.

## 2. Run setup once
Open CMD under the same Windows account you normally use:

```cmd
cd /d C:\TD-POC-v0.22
Setup-POC.cmd
```

Enter the existing PostgreSQL connection details when asked: host `localhost`, port `5432`, your existing database username and password. Setup creates this folder's Python environment, checks/downloads the same local embedding model, builds the solution, applies additive migrations, checks HNSW indexes, FFmpeg and Codex login. Complete Codex login if requested. Existing source vectors are reused; setup does not re-embed the dataset.

Retained v0.20 database change (v0.22 adds no new migration): `knowledge_qa.evidence.frame_id` links QA frame citations to the existing video-frame table. It stores IDs, hashes, timestamps and paths, not image blobs. Existing rows remain. Answers remain audit records, not automatically trusted learning or embedded source facts.

Do not copy old `.venv`, `bin` or `obj` directories. No need to copy old run folders for source retrieval. Run setup in the new folder even if the old release worked. Stop if setup reports FAILED and send the full error.

## 3. Start POC 2

```cmd
Start-POC.cmd
```

Choose **2**. Wait for the `You>` prompt. Startup scans only. If you changed/added source files, run:

```text
/process
```

Wait for the processing window to finish; check failures before testing. For an unchanged dataset that was already imported, do not perform another full import merely because this version changed. The two role windows show activity; Ctrl+C cancels active work. Video questions may take longer because frames are prepared and both agents examine them.

## 4. Run matching tests
Use the questions in `GPT-Comparison-Prompt-and-Questions.txt`. For **each independent question**:

1. In POC 2 type `/new`.
2. Type `/ask ` followed by the exact question.
3. Let Knowledge and Verifier finish. Copy the complete answer, including limitations, sources and run path.
4. Export immediately from a separate CMD (the script exports the latest question):

```cmd
cd /d C:\TD-POC-v0.22
Export-LatestRetrieval.cmd
```

Rename each exported ZIP to `Q1-POC.zip`, `Q2-POC.zip`, etc before running another question. The ZIP is created in the solution folder. **Exports now include the selected frame images** as well as prompts, evidence and verdicts. Share them as you would the underlying source material.

For ChatGPT, start a fresh chat per question with the same comparison instructions and Drive folder. Paste the exact same question without `/ask`. Do not show either system the other's answer. Confirm both can access the same source revisions; equal prompts with different available files are not an equal-source comparison.

For a conversation/follow-up demo, keep one session and label it a follow-up test. Do not mix it with independent-question scores.

## 5. What to compare

| Check | Good result |
|---|---|
| Meaning | Corrects typos while preserving the actual question and names |
| Evidence | Relevant original files and passages; applicable product/version |
| Procedure | All supported steps; missing steps clearly identified |
| Chronology | Relevant versions compared; exact versus broader names distinguished |
| Video | Exact recording; speech separated from visible sampled state and outcome |
| Honesty | No invented save, permissions, global absence or complete-video claim |
| Clarity | Direct, readable answer with sources and short useful limits |

More citations or longer answers do not automatically win. A justified qualified answer is better than unsupported certainty. Compare source coverage before blaming the embedding model.

## 6. Video limits and diagnosis
Frames are selected from the question-bearing transcript sections plus opening/ending, at most 12 samples per recording and two recordings per question. Exact names are required; similar names are not substituted. Still frames can miss actions between samples. A visible Save button does not prove successful save. An existing user's Created By field does not prove a new user was created in the recording.

Question-directed text reads keep original unit IDs, use up to 24 units per source and at most eight source versions per round, with an overall evidence budget. A short 18-unit transcript can now be supplied completely. Longer sources remain bounded and disclose coverage. One verifier-requested follow-up remains the limit.

If an answer disappoints, send both complete answers and the POC export. `evidence.json`/`evidence-expanded.json` show what was actually supplied; `visual_inspection` lists exact match and sampling/unavailable status; `source_reads` reports units supplied. Verification events retain the coverage decision/reason. The exporter includes all question-local files and sampled images, not your database password or Codex login files.

Optional direct source diagnostic inside POC 2:

```text
/diagnose Woodgrove
/diagnose Woodgrove
/last
```

`/diagnose` searches imported usable text; it does not prove missing originals do not exist. `/last` redisplays the last result in this session.

Engineering checks accompany the release, but real Windows/Codex answers and parity with ChatGPT require your live retest. Do not treat AI verification as human approval.

## Optional: separate retrieval quality from answer quality
If answers differ, perform a second comparison using **the identical evidence**. In a fresh ChatGPT chat, attach only `evidence.json` (or the final `evidence-expanded.json`) and the run's `sampled-frames` folder images. Do not attach `result.txt`, drafts, verdicts or the full run ZIP, which would reveal the POC answer. Ask ChatGPT to answer the original question using only that packet, with the same citation IDs and limits. If this agrees while independent searches differ, retrieval/source selection is the likely gap. If identical evidence leads to different claims, inspect reasoning/instructions/verification. This diagnostic is separate from the independent-source test.

## v0.22 acceptance checks
Run the same five questions, independently with `/new` before each. For Q1 the packet should contain original supporting passages for BOTH the exact-name result and the broader Woodgrove result, with product families separated. For Q2 the packet should include the requested recording's own SRT/DOCX, not only another training video's transcript. Q4 should continue to include its matching transcript, and Q3/Q5 should retain the documented settings distinction. A known missing source must trigger a follow-up or clarification, not full verification merely because remaining claims are narrowly true.

In the run export inspect `scope.recordings`, `scope.required_transcript_versions`, `scope.required_release_matches`, `scope.blocking_errors`, `source_reads` and `visual_inspection`. The verdict now contains `requested_scope_complete` separately from supported-claim checks. The host checks blockers again at database publication.

The title mismatch in your prior export was real: the opening still said Bank Upload Module Walkthrough although the file was named User Master Walkthrough. Preserve that caveat; do not rename the recording just to make a test pass. Filename/link pairing is not independent proof of audio alignment.

The prior Firecrawl authentication warning belonged to a connector worker; all 15 captured Codex calls completed with exit code 0. This release focuses on evidenced retrieval omissions and does not claim to repair that separate connector authorization. Never add an external API key merely to make this local dataset retrieval work.

Release tests replay recorded source snapshots and use a disposable SQL fixture. They demonstrate evidence selection and gates; your live test must still establish answer quality. No raw user run exports or credentials are bundled.


## v0.22 first acceptance test
Run Q3 (posting entries) first, independently with `/new`. The packet should now contain the posted-entries prerequisite guide and the Posting Warning guide. An answer should distinguish clicking Posted, View Posted Entries, and automatic GL opening, and explain any conflicting menu routes. No source-specific answer or bank alias is hardcoded.

The added lexical lane uses PostgreSQL English full-text matching over imported usable text; semantic search still uses HNSW. It does not add a persistent full-text index or require re-embedding. This scan may add latency as the corpus grows. Follow-up remains bounded to one investigation. Full-body deduplication saves optional reading slots; it does not delete sources or vectors, and source-role boundaries remain separate.
