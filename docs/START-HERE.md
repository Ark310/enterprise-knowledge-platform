# Workspace v0.24 — start here

You now use a local website for both POCs. Codex still does the reasoning; Ollama's **qwen3-embedding:4b** still creates the 2,560-dimensional vectors; PostgreSQL and HNSW still retrieve your existing data.

## 1. Keep your data

Close the previous POC and its agent windows. Back up `knowledge_poc` in pgAdmin. Keep the previous application folder as a fallback.

Extract the new ZIP to:

```text
C:\TD-POC-v0.24
```

Your `C:\S3 bucket Data` folder and PostgreSQL database stay where they are. **Do not recreate the database, run the fresh schema installer, or delete your vectors.** Setup adds web-chat tables and image references; it retains existing source records and reviews. Extraction and embedding profile versions remain unchanged, avoiding a forced corpus re-embedding.

## 2. Run setup once

Open CMD under the same Windows account you normally use:

```cmd
cd /d C:\TD-POC-v0.24
Setup-POC.cmd
```

Follow its prompts:

1. Confirm the data folder, normally `C:\S3 bucket Data`.
2. Enter the PostgreSQL host (`localhost`), port (`5432`), username and hidden password.
3. Sign into Codex if requested. This version uses its own POC login directory.
4. Wait for `SETUP PASSED`.

The script installs Python dependencies (including image decoding), checks the local embedding model, builds the solution, applies additive migrations, checks HNSW indexes, checks FFmpeg and checks Codex. It requires your existing Python 3.11+, .NET 10 SDK, Ollama, Codex and PostgreSQL 17/pgvector installation.

If CMD's title starts with **Select**, press **Esc** to leave selection mode and let output continue.

## 3. Start Workspace

```cmd
cd /d C:\TD-POC-v0.24
Start-POC.cmd
```

Choose:

- **1** — Documentation gap analysis: Agent A understands a recording, B compares the documentation, C discusses the saved results.
- **2** — Knowledge retrieval: ask a question, retrieve sources, then independently check the proposed answer.

The selected POC checks the database, local embedding model and indexes before opening:

```text
http://127.0.0.1:5250
```

If it does not open automatically, paste that address into your browser. **Keep CMD open** while using the website. Existing agent activity windows still open during work; they show status and progress, not private internal reasoning.

Only one agent job runs at a time. You can browse other saved chats while it works. Use **Stop** in the website to cancel the current request. If an application crash interrupts a request, the chat reports it once the job lease expires (up to 90 seconds); it does not silently rerun the request.

If port 5250 is occupied, use another local port before starting:

```cmd
set WORKSPACE_PORT=5251
Start-POC.cmd
```

To use the previous command-line interface instead:

```cmd
Start-CLI.cmd
```

## 4. POC 2 — first test

Choose **2**, then type a natural question, or paste:

```text
How do I view posting entries after clicking Post in TradeDesk? Give me clear steps, explain the required setting, and identify any conflicting instructions in the sources.
```

The reply should show clear steps first, then important notes and clickable **Sources** at the end. Numbered references connect claims to sources. Clicking a source opens the original local file preview; supported files can be opened or downloaded. A source website link appears when an original URL is available in the imported metadata.

An original screenshot or sampled video frame appears only when available, supplied to the agent and selected as relevant. **Not every answer will include an image.** Unsupported binary formats and screenshots without a usable source link are not automatically interpreted as shared documentation.

Source previews are pinned to the revision used in the answer. If an original was moved, deleted or changed, the preview is unavailable rather than showing a different revision.

Follow up in the same chat:

```text
Can you explain the required setting more simply?
```

Then click **New chat** and ask an unrelated question. Each chat retains its own history and context across reloads and application restarts. POC 1 and POC 2 have separate chat lists.

Old CLI conversations are not automatically imported into this new sidebar. Existing database QA audit records remain. Existing gap reviews can be selected using `/results latest` or an exact run key.

## 5. Try an image

Click **Attach image**, or paste a screenshot into the question box with **Ctrl+V**. Enter a question, for example:

```text
What does this message show? Search our documentation for the matching setting and explain what I should check. Clearly separate what is visible in my screenshot from what the articles establish.
```

PNG, JPEG and WebP are accepted, up to 10 MB and 20 megapixels each; up to four selected images per message. Images are decoded and resized for processing. Deselect an earlier image if it should not accompany the next question.

**Your uploads stay within their chat.** They do not enter the data bucket, shared source corpus or embedding tables. Both the Knowledge and Verifier agents receive the same image evidence. Uploads can show your problem; they cannot establish general product behaviour by themselves.

## 6. POC 1 — reuse an existing review first

Choose **1** on startup. In a new web chat, enter:

```text
/results latest
```

Or use an exact saved run key:

```text
/results YOUR-RUN-KEY
```

Then ask:

```text
/ask Which topics need rework, why, and what should a documentation writer change first? Cite the topics and articles.
```

The selected review belongs to this chat. A different chat can select a different run. Saved findings remain agent proposals awaiting human review.

For a new whole-recording review:

```text
/review current-state\System Admin_ Security_User Master Walkthrough.mp4
```

Put the recording path on the **same line** as `/review`. The matching SRT must already be imported. A and B still validate, save and embed their findings through the existing workflow before C discusses the result.

C can show relevant supplied frames from the saved review. The displayed frame set is bounded; images are sampled evidence, not continuous video inspection. Historical source warnings remain important. If frames only exist in an older application folder, they may not preview in this version; run a fresh review to populate its frame cache.

Search original documentation from POC 1 with:

```text
/search How do I view posting entries after posting?
```

This uses the shared checked retrieval path, with source links and the verifier.

## 7. Add new files later

Place the new video and matching `.srt` in `current-state`. On startup, scanning is read-only; it does **not** import or embed source data automatically. During a session:

```text
/scan
/process
/status
```

`/scan` discovers changes. `/process` explicitly imports supported content and creates missing vectors. Wait for processing to finish before starting a review or asking questions about the new content. `/pilot` processes a limited sample; it is not a complete corpus import.

## 8. Quick regression questions for POC 2

Run each main question in a new chat; keep its follow-up in the same chat:

1. **How do I change an existing TradeDesk user's password? Compare the article with the System Admin Security User Master Walkthrough. Explain the documented steps, what the presenter says, and what the sources do not establish. Cite timestamps.**
   Follow-up: **Does that prove the password change was successfully completed?**
2. **Which TD version has the latest Woodgrove Bank changes, and what changed? Compare the relevant release notes and distinguish exact “Woodgrove Bank” mentions from broader Woodgrove changes.**
3. **Are View Posted Entries and Posting Warning the same setting? Explain what each controls and cite the supporting articles.**
4. **Does the User Master walkthrough prove a new user was created and saved? Separate spoken instructions, sampled visual evidence and unverified outcomes.**

Check whether the answer addresses the question, whether links open the right originals, whether relevant images match the topic, and whether follow-ups preserve context. The verifier checks the answer; it does not guarantee perfect product accuracy.

## 9. Where things live

- `agents/knowledge-assistant.md`: POC 2 normalization, reasoning and clear-answer instructions.
- `agents/knowledge-verifier.md`: independent relevance, evidence, completeness and image checks.
- `agents/agent-a-module.md`, `agents/agent-b-module.md`: POC 1 comprehension and gap-review instructions.
- `src/TD.Poc.Core/ModuleReview.cs`: selected-run C instructions and A→B workflow.
- `src/TD.Poc.Web`: local website and API.
- `tools/workspace_ui.py`: chat persistence and protected source previews.
- `database/migrations/024-workspace.sql`: additive web-chat tables.
- `runtime`: diagnostic logs and run files; existing export scripts still export agent runs.

New `workspace_ui` tables store chats, messages, asset references and the active-job lease. Chat images are stored outside the versioned application folder, normally under `%LOCALAPPDATA%\Contoso\Workspace`. Retain that directory and the database to retain chats and uploads through upgrades. Back up both as needed. This POC is for one local Windows operator; it is not a multi-user or tenant-isolated web deployment.

In Visual Studio, open `TD.Poc.sln` and set **TD.Poc.Launcher** as the startup project. It builds the selected web/console targets through project dependencies. CMD setup is still needed once for Python, credentials, database migrations and model checks.

## Validation and limits

The release includes unit, host and disposable PostgreSQL/API checks for both POCs. Deterministic test-only model responses exercise the application wiring and evidence gates; they do not establish real Codex answer quality on your corpus. Browser access was blocked in the build environment, so rendered browser interaction and native Windows PowerShell window behaviour still need your local smoke test. No production database or real operator credentials were used during verification.
