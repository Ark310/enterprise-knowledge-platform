# TD POC v0.16 — whole-recording documentation review

One selected recording goes through Agent A, which identifies its supported topics and observations. Agent B reviews documentation for all those topics and produces one combined coverage/gap report. Three-topic batches are a processing detail, not separate user questions or separate reviews.

## Fix
B may cite any passage supplied in its current batch for any requested topic if relevant. Retrieval topic labels describe search origins, not exclusive passage ownership. The exact UUID and literal excerpt are checked. Unseen other-batch passages, invented quotations, wrong run identities and omitted topics remain invalid. The complete topic index is supplied as module context. Searches remain bounded; no exhaustive absence or human factual approval is claimed.

Each failed-content batch gets an initial attempt plus two corrections with explicit validation feedback. Every attempt and validation is preserved. Process/authentication/cancellation/database errors stop clearly rather than being retried as citation mistakes. Validated batches have context fingerprints and must pass validation again to be reused. Changed evidence forces reassessment.

## Start and resume your failed run (recommended)
Keep C:\TD-POC-v0.15 and your database. Close old POC windows. Extract this release to C:\TD-POC-v0.16. Run these in Command Prompt, one at a time:

```cmd
cd /d C:\TD-POC-v0.16
Setup-POC.cmd
Start-POC.cmd
```

Enter the usual database connection details during setup. At the POC You> prompt:

```text
/resume C:\TD-POC-v0.15\runtime\runs\TD-MODULE-20261029155036-e2c7f8
```

The host checks the saved A output, observations, vectors, model profile, source versions, file hashes and frames before reuse. It copies the run into this release's runtime folder, retains the run ID and does not insert duplicate A findings/vectors. If these checks fail, preserve the export and use a fresh review rather than changing the database manually. Retain the original folder until this finishes.

A completed B report is not resumed or overwritten. B results are validated, linked to the original A records/article passages, and embedded through the same local Qwen profile before the final commit. Failed batches do not become successful final findings. Checkpoints are local files; final validated B findings are stored together in PostgreSQL.

## Fresh review instead
At You> enter /review, then:

```text
current-state\System Admin_ Security_User Master Walkthrough.mp4
```

A new review intentionally creates a new run. Do not use both resume and fresh review for the same retry. No /process is needed if recording/SRT and imported assets are unchanged. Startup scans only. Add future recordings with matching SRT, then /scan and /process before /review.

## Results and export

```text
/results latest
/ask Which topics are covered, need rework, or have missing documentation? Cite the articles and explain the proposed actions.
```

In a separate CMD in this release folder run Export-LatestRun.cmd and share its resulting ZIP for review. This includes excerpts and frames. One A activity window covers all A work; one B window covers retrieval, batches, corrections and save/embedding. Main shows concise status/results. Existing Codex MCP warnings can still be logged; the release does not claim to repair unrelated connector credentials.

## Verification and limits
Release solution build: zero warnings/errors. Python: 53 tests passed. Host: 26 assertions passed including bounded correction, persistent invalid output, cancellation and role streams. Real failed batch replay: original 11 citations accepted unchanged; altered fabricated quote rejected. No live Codex reasoning, native Windows UI/DPAPI, or fresh database integration was executed for v0.16 in this environment. Existing A/B transactional storage and embedding code is retained; native end-to-end completion and semantic report quality must be checked on the server. The earlier v0.15 database fixture results are not claimed as a new v0.16 DB test.
