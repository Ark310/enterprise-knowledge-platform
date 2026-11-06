# TD v0.23 — POC 2 setup and natural-question tests

## What changed

The system can show a verified partial answer: **Confirmed information → Documented steps (incomplete when necessary) → Unresolved → Next question**. Every displayed factual claim still needs original evidence and independent verification. Unsupported drafts are not automatically downgraded into published partials.

The normalizer now supplies the interpreted task, requested parts, user-confirmed context, assumptions and whether this is a new task, follow-up or correction. A clarification reply stays connected to its task. Topic changes replace the active task. /new clears the session. Memory holds intent, not product evidence, and lasts only in the current console session (up to four recent turns within the active task). Closing/reopening starts a new session; saved run audits remain.

## 1. Prepare

Close v0.22 and its activity/processing windows. Keep its folder as fallback. Back up knowledge_poc in pgAdmin. Extract so Setup-POC.cmd is directly inside **C:\TD-POC-v0.23**. Keep C:\S3 bucket Data and the existing database. Do not run the fresh schema installer or recreate the database.

## 2. Run setup once

```cmd
cd /d C:\TD-POC-v0.23
Setup-POC.cmd
```

Confirm your data folder. Enter the existing PostgreSQL host, port, username and password (normally localhost, 5432, postgres). Complete isolated Codex login if requested. Setup prepares this folder's Python environment, checks the existing Qwen embedding model, builds and applies migrations.

**Migration023 is required:** it updates the existing QA publication constraint to recognize independently verified partials. It adds no tables and does not rewrite your sources or vectors. Partial answers retain an explicit PARTIAL answer status and PARTIAL_PASS verification in JSON; the existing database audit state VERIFIED means the displayed content was checked, not that the entire request was answered. Setup applies this automatically. Stop and send the full error if it fails.

Do not copy old .venv, bin, obj, database.dpapi or Codex credentials. No re-embedding for this release. Answers remain audit records, not automatically trusted learning. POC1 workflow retained.

## 3. Start

```cmd
Start-POC.cmd
```

Choose **2**. Wait for You>. Startup scans only. If no source files changed, start testing. If files changed, /process and wait for completion first.

## 4. Test natural questions

Use **POC2-v023-Natural-Test-Questions.txt**. Start each numbered scenario with /new, but **do not use /new between a question and its clarification/follow-up reply**. Enter plain text to reply, or /ask followed by your reply. Wait for the agents to finish before the next message.

Answers may be complete, partial, a clarification, or insufficient. A partial is a useful success when a real gap remains. It must explain that gap and must not guarantee two different people simply because two approval stages exist. Similarly, documented user MFA steps do not prove a complete first-time provider integration.

## 5. Export each result

After each answer/clarification, in a separate CMD:

```cmd
cd /d C:\TD-POC-v0.23
Export-LatestRetrieval.cmd
```

Rename each ZIP before continuing, e.g. S04-question.zip, S04-clarification.zip, S04-followup.zip. The export includes structured intent before/after the turn, evidence, drafts, verifier decisions and sampled frames. Share exports as you would the source material.

## 6. What to check

- Did it preserve your actual question, product and number of approvers?
- Did a short reply retain the original task? Did a topic change stop carrying the old task?
- Are supported facts shown instead of disappearing because one detail is missing?
- Are incomplete steps clearly marked? Are unsupported steps still withheld?
- Does it ask one useful question rather than repeating the same broad search?
- Do claims cite the correct product/version/source? Does /new actually reset?

The implementation has offline captured-run, host and disposable PostgreSQL checks. These verify tested mechanics and evidence boundaries, not new live Codex answers. Your live Windows retest is still needed; there is no promise every question has a complete answer. Linked KB screenshots are not newly made available for general questions by this release, so some configuration details may remain unresolved.
