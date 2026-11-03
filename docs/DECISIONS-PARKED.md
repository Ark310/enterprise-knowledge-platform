# TD decisions parked; v0.17 POC scope

Recorded 3 November 2026 from Abdul's explicit instructions.

## Production work is paused
Do not modify the proposed production schema or implement the following production decisions until Abdul resumes that work. The v0.17 work is limited to the existing v0.16 POC and its MP4/retrieval improvements. This note records decisions, not implemented changes.

| Previous question | Decision |
|---|---|
| 1 Client isolation | Client-specific information must remain private. Repeated issues across clients should contribute to common knowledge so a third client can receive a useful general answer. This does not authorize exposing another client's ticket, identity or confidential details. Sharing/redaction/approval mechanics remain to be designed. |
| 2 Duplicate prevention | Approved. |
| 3 Same-parent relationship checks | Approved. |
| 4 Exact checked outbound AI payload audit | Approved. |
| 5 Customer-support approved-safe-only retrieval gate | TBD; not approved or rejected. |
| 6 Human approval | Approved. Missing documentation topics should go to a writer agent. They remain recorded as missing until a human approves and the article is published to ReadMe.io. Draft generation alone does not close the gap. ReadMe publication connector and status-confirmation details remain for later design. |
| 7 Explicit frame/transcript evidence and timestamps | Approved. |
| 8 Versioned processing builds and retry safety | Approved. |
| 9 Ticket/Teams permission synchronization | TBD; not approved or rejected. |
| 10 Evidence dependency and hold protection | Approved. |

## Active request: v0.17 POC
Baseline is the attached TD-POC-v0.16(1).zip, not a rewrite using the 59-table production proposal. Preserve Agent A comprehension, Agent B whole-module gap analysis, Agent C results/Q&A, handoff contracts, tests T02/T04/T05 and /review, concise main console and A/B activity windows. Reasoning remains Codex CLI; embeddings remain local Ollama qwen3-embedding:4b. Startup scans only; /process is manual.

Requested changes: improve MP4 usability via grouped timestamped transcript passages, retained original cue provenance and surrounding context; link reusable selected frames and their actual timestamps without putting MP4/image bytes in PostgreSQL; retain clear visual-versus-narrated evidence checks. Add HNSW retrieval while keeping keyword search and original-vector reranking. Verify live stored dimensions rather than assume 2650/3650; observed earlier warm-up output was 2560. Preserve source and historical run evidence.

## Source inspection findings
Attached source worker.srt_units currently emits one content unit per subtitle cue. Search uses exact cosine plus keyword reciprocal-rank fusion, not HNSW. Whole-module review uses 120-second execution windows and samples frames every two seconds into run folders. Current POC schema already has extraction profiles/active extractions, content units, representation/link structures and separate content/analysis embeddings; do not replace it with the production proposal.

## Proposed implementation boundary — awaiting database choice
Reuse existing POC structures where possible; introduce only additive POC upgrades needed for chunk metadata and HNSW indexes. A new transcript extraction version must avoid rewriting cited content. Keep keyword search, half-precision HNSW candidate indexing where supported, full-vector reranking and explicit exact fallback diagnostics. Preserve original cue-level evidence used by current test contracts. Validate that actual query plans use the new index; don't merely create an unused index.

Abdul approved Option A: reuse knowledge_poc with an additive upgrade and three comparison modes: old exact, improved exact, improved HNSW. Frame/cache and chunk boundary settings will be documented as proposed implementation choices, not previously approved fixed values. v0.17 implementation is authorized. Changes are packaged for the operator to apply; the operator database has not been accessed here.
