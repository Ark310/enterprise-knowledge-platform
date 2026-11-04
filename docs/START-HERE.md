# TD POC v0.19 — retest guide

This release improves **option2: Knowledge Retrieval and Verification**. Option1 remains the existing Gap Analysis. Codex reasons, local Qwen embeds, and PostgreSQL retains the existing data/vectors.

## Start afresh without deleting your data

1. Finish active work and close the old POC. Back up `knowledge_poc` in pgAdmin. Keep the old release folder.
2. Extract the ZIP to **C:\TD-POC-v0.19**. Keep **C:\S3 bucket Data** where it is. Do not delete/recreate Postgres or rerun the fresh-schema installer.
3. Open CMD with your usual Windows account:

```bat
cd /d C:\TD-POC-v0.19
Setup-POC.cmd
```

Accept your existing data path, host `localhost`, port `5432`, username `postgres` if that is your current account, and enter its DB password privately. Complete the isolated Codex ChatGPT login if prompted. Setup builds the new programs, creates the Python environment and applies the same additive migrations/index checks. Your installed Qwen model is retained; existing vectors and gap results are reused. New folder means configuration/login may need re-entering, not a new dataset import.

4. After **SETUP PASSED**:

```bat
Start-POC.cmd
```

Choose **2**. Do not run `/process` just to retest the same imported dataset. Startup scans only. If sources have changed or were never imported, `/process` is still the explicit import command; wait for it to finish before comparing results.

## First check: is Woodgrove Bank text present?

Inside POC2 run:

```text
/diagnose Woodgrove
/diagnose Woodgrove
```

This checks the imported ORIGINAL usable text directly, excluding catalogue files. It reports matching source versions and how many matching passages have vectors for this model. A zero result does not prove absence from your original files: extraction/import or source naming may still need checking. Full reports are saved under `runtime/knowledge-diagnostics`.

This diagnostic is NOT a Woodgrove answer key and does not use ChatGPT's claimed version as ground truth. Share its report if there are no matches or some text has no vectors. Do not re-embed everything blindly.

## Compare fairly

Use `GPT-Comparison-Prompt-and-Questions.txt` in this folder (also provided separately). Connect Google Drive in a **fresh ChatGPT chat**, replace the folder link, and paste only the SETUP PROMPT first. After access is confirmed, ask the listed questions ONE AT A TIME, exactly as written.

In POC2 type `/new`, then paste `/ask ` followed by that SAME question. Use `/new` before each independent test. In ChatGPT start a fresh chat/setup for strict independent comparisons, or use the same question order and avoid giving feedback until all tests finish. Keep the same data files/versions in Drive and PostgreSQL. General procedural knowledge may aid reasoning, but product facts must come from the dataset.

Do not paste either system's answer into the other before it answers. Do not put the claimed Woodgrove version into the question. Compare correct evidence-backed conclusions and honest limits, not exact wording or which system sounds more confident. Different retrieval systems/models mean this is an answer-quality test, not an isolated HNSW speed benchmark.

## What you should notice

- Fewer catalogue results and irrelevant saved findings.
- Focused term searches and fuller source reads, with one follow-up investigation if needed.
- Numeric version comparison and explicit chronology limits for latest-release questions.
- A concise answer with numbered source references, rather than repeated JSON locators.
- Insufficient evidence now goes through the Verifier; no misleading handoff followed by immediate refusal.

These changes are tested plumbing, not a guarantee that your exact corpus contains the necessary Woodgrove passages or that the model never makes semantic mistakes. A qualified or insufficient answer may still be appropriate. For release questions, keywords may not capture every synonym; incomplete imports/partial extraction or inventory/read caps prevent an exhaustive newest claim.

## Export each test BEFORE running the next

In a SECOND CMD:

```bat
cd /d C:\TD-POC-v0.19
Export-LatestRetrieval.cmd
```

Keep the generated `TD-knowledge-...zip` next to the matching ChatGPT answer and question number. It includes initial evidence, expanded evidence if used, drafts, verifier checks and logs. Credentials are excluded; source excerpts remain internal material. You can also zip a particular question directory under `runtime/knowledge-runs` if needed.

## Instructions and solution

- `agents/knowledge-assistant.md`: normalization, evidence-backed answers and labelled reasoning.
- `agents/knowledge-verifier.md`: relevance/provenance checks and follow-up requests.
- `contracts/knowledge-qa.schema.json`: strict handoff formats.
- `tools/knowledge_search.py`: QA-only source investigation and chronology.
- `tools/knowledge_qa.py`: audit persistence and final citation/freshness gates.
- `src/TD.Poc.Core/KnowledgeRetrieval.cs`: bounded agent handoffs and final output.
- `src/TD.Poc.Launcher`: set this as Startup Project if launching from Visual Studio.

The two agents remain independent roles. Each active role opens its activity viewer; a follow-up may reopen that role for its correction phase. Individual Codex calls remain hidden; status windows show progress, not private reasoning. Five-minute per-call retrieval timeout remains configurable in `KnowledgeAgentTimeoutMinutes`. Ctrl+C or Q in an active role viewer cancels the current work. No final success is claimed after a failed evidence gate.

Question history remains in `knowledge_qa.sessions/turns/events/evidence`; generated answers are not automatically embedded into trusted knowledge. Existing source embeddings remain in `retrieval.content_embeddings`; gap findings retain their existing storage/embedding workflow.

Commands: plain question or `/ask`, `/new`, `/last`, `/diagnose keyword`, `/status`, `/scan`, `/process`, `/help`, `/exit`. Gap `/review` and comparison modes belong under menu1.
