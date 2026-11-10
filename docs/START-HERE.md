# Workspace v0.25 — videos, screenshots and tests

## What changes

You can select existing-asset videos, ask about their content, and receive transcript-grounded answers with relevant original video frames and playback timestamps.

- **Videos** opens a searchable list of recordings and their transcript/vector readiness.
- Select up to **two recordings** for the current chat. The selected filenames stay pinned through normalization and retrieval.
- Video questions may take longer than text-only questions because frames must be extracted and visually checked. The app finds relevant transcript passages, extracts/reuses a bounded set of original JPGs and sends the same images to Knowledge and Verifier.
- Helpful selected images appear after the answer, with timestamps and a **Play video at…** button.
- Article screenshot requests no longer require a video name. Your three captured v0.24 failures are regression tests.
- **Scan files** and **Process new files** are visible actions; registered MP4s no longer keep appearing as unfinished text extraction.

Your two supplied SRTs contain six zero-duration cues: one in Sections3/4 and five in Sections5/6. v0.25 imports their text and original exact timestamps as **POINT_ONLY** cues, with warnings that spoken duration is unverified. It does not invent timings, silently drop these words or rewrite the SRTs. Reversed timestamps and malformed cues still require attention.

## 1. Upgrade

Close v0.24 and its activity windows; keep its folder as fallback. Back up `knowledge_poc` in pgAdmin. Extract the new application to:

```text
C:\TD-POC-v0.25
```

**Keep your existing PostgreSQL database and data bucket. Do not run the fresh schema installer, delete vectors or recreate the database.** This release uses the existing024 tables and metadata; it adds no new production table schema.

In CMD:

```cmd
cd /d C:\TD-POC-v0.25
Setup-POC.cmd
```

Confirm your data folder, enter the PostgreSQL connection details and complete the POC Codex login if requested. Setup installs dependencies, builds the solution, checks migrations/indexes, FFmpeg, model and login. Existing embeddings are reused with the same local model/profile.

Then:

```cmd
Start-POC.cmd
```

Choose **2 — Knowledge Retrieval and Verification**. Open the localhost URL printed in CMD, normally `http://127.0.0.1:5250`. Keep CMD open. Agent activity windows still show progress.

## 2. Place the sample files correctly

Under your existing data root, the four files should be together in:

```text
C:\S3 bucket Data\existing-assets\VLCs\TradeDesk\
  Sections 3 and 4 [iuinh8jZ7J8].mp4
  Sections 3 and 4 [iuinh8jZ7J8].srt
  Sections 5 and 6 [H232GBThOTE].mp4
  Sections 5 and 6 [H232GBThOTE].srt
```

If a video already exists there, keep that single copy and put its matching SRT beside it. Do not create another copy under a second folder. Extract the files from the sample ZIP; the importer does not search inside a ZIP archive.

Use the supplied SRTs as they are. They do not need to be retranscribed solely because of their zero-duration cues.

The application ZIP does not duplicate your MP4 samples. Use the files you already have.

## 3. Import the new transcripts

Click **Scan files**, then wait for its summary. Click **Process new files** and wait for completion.

The equivalent chat commands are:

```text
/scan
/process
/status
```

Processing imports new/changed transcripts and creates missing vectors. It reuses vectors already present for unchanged content. It does not run a speech transcriber or embed raw MP4/image bytes. If some files fail, review the listed filenames/errors; other files can still finish.

Open **Videos**. Search for `Sections`. These recordings should show **Transcript searchable**, with embedded-passage counts. Refresh the list by closing and reopening it after processing.

- **Needs processing:** new/changed content, incomplete vectors or missing searchable companion content.
- **No imported transcript:** put a matching SRT beside the MP4 and process it.
- MP4 revision hashes are checked on selection; required local transcripts are checked for changes before use.

## 4. Test the first video

Start a **New chat**. Open **Videos**, select **Sections3and4**, then close the video list. Ask:

> According to this training video, how do I draw down a forward? Explain what the presenter says, show the relevant screen frames, and cite the timestamps. Do not assume that every action completed successfully.

Follow up in the same chat:

> What does the presenter say about fixed-date versus window forwards? Show the relevant screen if it was inspected.

The supplied transcript discusses forwards, drawdowns and margin. That establishes a useful test topic; it is not a predetermined answer or proof of current product behaviour.

## 5. Test the second video

Start another **New chat**. Select **Sections5and6** in Videos. Ask:

> Where does the presenter go to open a corporate client, and what information do they review? Walk me through the video and show relevant screenshots with timestamps.

Follow up:

> What does the video say about corporate and individual clients being different? Separate the presenter’s explanation from anything the screenshots directly establish.

This transcript discusses client onboarding and front-office information. Test whether the reply cites this recording rather than the User Master video.

## 6. Compare both recordings

New chat → select both recordings → ask:

> Using these two videos, explain how client setup relates to the dealing workflow. Clearly say which video supports each point, show a useful frame from each if available, and identify any connection the recordings do not actually establish.

The answer should distinguish the two recordings. It may say that a relationship is not established; it must not invent a connection just to provide a complete story.

## 7. Test a typed video title

In a new chat without selections:

> In the Sections 5 and 6 training video, how does the presenter start onboarding a corporate client? Include relevant screenshots and timestamps.

A unique human title can resolve without its YouTube ID. If more than one recording has that title, select the exact file in Videos. File paths remain the most reliable selection.

## 8. Retest the original screenshot error

New chat, no recording selected:

> I need to add a new employee to TradeDesk. Where do I start, and what needs to be set up first? Show any relevant screenshots from the articles.

Then:

> Are there any pictures to show what that looks like?

These requests should reach article retrieval rather than asking for a recording name. Images appear only if relevant original article images are available and approved by the verifier.

## What to check

1. The answer concerns your selected video and question.
2. Spoken instructions and visible screen evidence are distinguished.
3. Timestamps and pictures are relevant, with playable source links.
4. Source links open the right original revision; changed/missing files give warnings.
5. Follow-ups keep the selected recording/context; New chat starts separately.
6. Missing evidence is acknowledged rather than replaced with an invented product step.

Search is driven by transcript text. Visual-only details that are never described may not be found; the system does not index every screen in advance. Frames are bounded samples, not continuous viewing. Not every answer needs an illustration. A screenshot showing Save does not prove that saving succeeded. You can request **“Use the transcript only; no video frames”** when images are unnecessary.

## Storage and what stays unchanged

MP4s remain in the data folder. Transcript text, vectors, timestamps and source relationships are in PostgreSQL. JPGs remain on disk in `runtime\frame-cache` and run snapshots; PostgreSQL stores their paths, hashes and recording references, not image blobs.

There is no frame-vector model or new embedding provider. Existing HNSW retrieval remains. POC1’s current-state A→B→C review workflow remains available under option1; its findings still follow the existing save/embed handoffs. Chat image uploads remain private to their chat and are not promoted into shared knowledge.

Chats and uploaded chat images retain the same database and `%LOCALAPPDATA%\Contoso\Workspace` storage used by024. Keep those through upgrades. Old per-version frame caches may not preview in the new folder; asking the video question again builds this version’s cache.

Agent instructions are in `agents\knowledge-assistant.md` and `agents\knowledge-verifier.md`. Media logic is in `tools\knowledge_visual.py`, `tools\video_evidence.py` and `tools\video_catalog.py`. The selected-video and gallery interface is in `src\TD.Poc.Web`.

## Verification limits

Both actual uploaded MP4/SRT pairs were ingested and sampled with real FFmpeg and a disposable PostgreSQL/pgvector database. Automated tests cover original frame files, correct recording identity, timestamps, cache reuse, readiness, changed transcripts and playback references. Direct API checks exercise selected-video normalization, retrieval, verification, persistence and identical agent image attachments.

Model responses in the integration harness are deterministic test substitutes. These checks validate wiring and evidence safeguards; they do not establish live Codex answer quality. Browser rendering and native Windows activity-window behaviour still need your local smoke test. No operator credentials or production database were used.
