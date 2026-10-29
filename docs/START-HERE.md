# v0.13 walkthrough

## What changed

The new default broad workflow is `/review` (alias `/test MODULE`). It does NOT ask a predefined feature question. You choose an imported recording, A reviews its scheduled sections and builds a topic index, B assesses documentation per topic, and the host saves a gap list to PostgreSQL and JSON. Only recorded/narrated topics are in scope; this is not an exhaustive certification of an entire product/module.

A uses two-minute sections and approximately two-second visual sampling, with original timestamps mapped from decoded frames. Every scheduled section must complete validation, every extracted observation must be assigned once, and every indexed topic must receive one B row. This accounts for supplied evidence, not all possible unobserved actions: the model can still miss content, and sampled video is not continuous video/audio review. Transcript narration, visual states, demonstrated actions and unverified outcomes remain distinct.

For the 12m55s User Master recording, expect seven section calls, one consolidation call, and one B call per group of three discovered topics, plus retrieval/embedding. This is substantially longer than T02; the duration depends on topic count and Codex latency. Use the activity windows for progress. No precise total-time promise is made.

## Install and start

1. Close the old POC. Keep it as a backup. Extract this package to C:\TD-POC-v0.13, with Setup-POC.cmd directly inside that folder.
2. Keep PostgreSQL and C:\S3 bucket Data untouched. No fresh-install SQL or database reset.
3. Open CMD:

```cmd
cd /d C:\TD-POC-v0.13
Setup-POC.cmd
```

4. Accept the data-root default; enter PostgreSQL host localhost, port 5432, user postgres (unless changed), and your hidden password. Complete the POC ChatGPT login if prompted. The script creates its Python environment, checks the existing local model, builds, configures the connection, applies the existing idempotent migration, checks video tools and tests Codex readiness. Existing extraction/vector rows are reused when fingerprints match.
5. After SETUP PASSED:

```cmd
Start-POC.cmd
```

## First whole-recording test

After startup scan completes, if the corrected SRT/video are already imported, no `/process` is necessary. Otherwise enter `/process`, wait until its worker finishes, and check failed=0. Known unsupported files can remain blocked.

At You>:

```text
/review
```

Recording path:

```text
current-state\System Admin_ Security_User Master Walkthrough.mp4
```

The command reads recording duration, pins current imported video/SRT hashes, then runs A section by section. A builds a topic index; the host saves and embeds A's observations. B performs three logged searches per topic (up to eight passages each), assesses groups of three topics, and returns one row per topic. Each B row is stored as a separate FINDING with its own vector and links to the corresponding A observations and cited source units. Agent reasoning never has direct database credentials.

Do not prefeed an expected gap list. Content not shown in this recording cannot be classified as a missing product feature. A broad test is not expected to reproduce a fixed number of topics on every model run; review the evidence and coverage accounting.

## Read and discuss the result

```text
/results latest
```

This retrieves the newest WHOLE-RECORDING run, not the newest narrow T02/T04/T05 test. It prints topic IDs, module, coverage, reason, source citations and actions. Failed/incomplete reviews do not fall back to an older successful report.

After selecting a report, type ordinary questions to C:

```text
Which topics have no article in the reviewed sources?
Which existing articles need rework, and what exactly needs changing?
Show me the topics that are adequately covered, with their article references.
What needs human confirmation before we write anything?
```

Or explicitly:

```text
/ask Summarize the missing coverage and the proposed work, with topic IDs.
```

C answers ONLY from the selected report. It does not silently mix old runs. After restarting, use `/results latest` again. To select an older broad run:

```text
/results TD-MODULE-<your-exact-run-key>
```

The exact run key is printed by the app. General `/search` still searches across source/derived records; use `/results` and `/ask` for exact-run discussion. `/status` lists database runs.

## Meaning of gap statuses

- COVERED: applicable supplied text adequately covers the reader task. This does not certify untested product behavior.
- NEEDS_REWORK: coverage exists but a concrete omission, outdated claim or reader problem is evidenced; article citations and proposed actions are required.
- NOT_FOUND_IN_REVIEWED_SOURCES: a qualified candidate gap in the bounded reviewed sources, not proof of company-wide absence. Human/source confirmation remains necessary before new writing.
- NEEDS_REVIEW: applicability, product meaning, unread linked guidance or available coverage prevents a defensible conclusion. It is not forced into a missing/update bucket.

Reports and database run status remain PARTIAL because media are sampled, documentation retrieval is bounded, and human approval has not occurred. That status alone is not a technical failure. No articles are automatically created/published.

## Adding four more recordings

Put each MP4 and matching same-basename SRT in current-state. Keep unrelated meeting-recording exclusion unchanged. Start the app or `/scan`; then `/process` and wait for completion. Use `/review` separately for each recording. Each creates a distinct run and gap list. This release does not merge several recordings into one global report; the user can select each run by key.

## Export and cancellation

In a separate CMD:

```cmd
cd /d C:\TD-POC-v0.13
Export-LatestRun.cmd
```

Upload the ZIP to review the first broad run. It includes section evidence/results/validation, topic-index.json, agent-a.json, per-topic executed search evidence, B batch results, agent-b.json, gap-list.json, gap-list.txt and live logs. The combined JSON report is also persisted in analysis.agent_outputs; `/results` does not depend on local files surviving an upgrade. Current source-version flags warn if evidence versions have subsequently been superseded.

Press Q in the active activity viewer or Ctrl+C in the main console during a Codex call to cancel. Earlier completed sections remain in files for diagnosis; interrupted reviews are marked FAILED where the DB is reachable and no final gap list is claimed. There is no resume of interrupted broad reviews in this version; a new `/review` creates a new run. There is no automatic processing on ordinary chat. Keep config/database.dpapi and config/codex-home private; export only the review bundle.

## Storage and learning

The importer already chunks text to about 3,000 characters, uses timestamped SRT cues and format-specific paragraph/page/row units. It creates chunks; PostgreSQL stores chunks/vectors. A/B records, provenance and vectors use the existing tables. This is retrievable memory, not fine-tuning or a change to Codex weights. Prior agent conclusions are proposals, not independent source truth.

Original targeted tests and their old contract are retained. New whole-review instructions are agents/agent-a-module.md, agents/agent-b-gaps.md; new envelope schema is contracts/module-review.schema.json. tools/module_review.py owns broad coverage validation/storage; src/TD.Poc.Core/ModuleReview.cs owns orchestration and exact-run C context. Original 29-table diagram remains in docs/architecture-and-tables.html.

A nonblocking Firecrawl connector startup error appeared in earlier Codex stderr despite POC-home isolation. This release retains tool restrictions but does not claim that external startup behavior is fully resolved. No Firecrawl key is needed to perform the supplied-evidence workflow. Check VALIDATION.md for what was actually tested locally versus on Windows.
