# v0.26 — Video questions, frames and ingestion readiness

- Separates article screenshots, user images and video inspection; captured v024 screenshot requests pass normalization regression tests.
- Video library lists registered/scanned recordings and transcript/vector readiness; up to two exact selections retained per chat.
- Scan/Process buttons, concise scan/import summaries and registered-media states.
- Human video titles resolve unique filenames without trailing YouTube IDs; ambiguous names ask for selection.
- Topic-first bounded original JPG samples, timestamp captions and seekable original-video playback.
- Zero-duration SRT cues retained as POINT_ONLY with original text/timestamps and warnings; reversed timings remain errors.
- Changed required transcripts block stale answers/readiness; pinned source and image hashes remain enforced.
- Existing embeddings, HNSW profiles, both POCs, private uploads and audit history retained; no new SQL schema required beyond024.

# v0.24 — Workspace local web interface

- Both POCs launch locally from the existing menu; legacy CLI remains available.
- PostgreSQL-backed, per-chat history and context; new chats isolate selected reviews and QA intent.
- Human-readable steps, source previews pinned to cited revisions, and selected original images.
- Chat-private pasted/uploaded images; same evidence to Knowledge and Verifier; no shared ingestion or upload vectors.
- Stop/progress, existing agent status windows, serialized work and interrupted-request notices.
- Additive migration024; existing source data, vector profiles and gap handoffs retained.
- Setup includes Pillow; source/model versions retained to avoid forced re-embedding.

# v0.23 — verified partial answers and conversation intent
- POC2 contract supports PARTIAL + independently checked PARTIAL_PASS; unsupported claims remain blocked.
- Required structured normalization: relationship to prior turn, requested parts, user-confirmed context and assumptions.
- Pending clarification and unresolved intent survive terminal responses; new topics replace active task and /new clears session memory. Memory is intent only, never source evidence.
- Confirmed information, incomplete documented steps, unresolved details and a focused next question are displayed separately.
- Repeatable migration023 updates only the QA publication constraint; no source/vector rewrite or new tables. Existing full answers remain valid; partial distinction stored in answer/verification JSON and completion note.
- Prompts distinguish per-user enablement from first-time integration and distinct people from approval stages. A broad multiple-count cannot silently become exactly two.
- Captured natural-run replay and actual SQL publication tests accompany host/context checks. Live model quality still requires operator retest.

# v0.22 — focused retrieval and readable answers
- Topic/title matching uses PostgreSQL English stemming; generic settings/permission terms no longer dominate the topic rank.
- Long-source focused reads use the same word-inflection matching; release chronology preserves exact-name matching.
- Complete usable-text duplicates share optional candidate slots, including before lexical caps; the most relevant matching title wins. No original source or vector is deleted.
- Verifier can repair follow-up keywords; newer optional evidence can replace earlier optional material without changing citation IDs or required-source protections.
- Main answer has clear sections, numbered steps, useful caveats, short source labels and clock timestamps. Full paths, quotes and diagnostics remain in the run export.
- No new schema migration or model change. Existing source vectors and Gap Analysis are retained.

# v0.21 — POC 2 identity-first evidence retrieval
- Named video resolves to imported companion SRT/VTT/DOCX before generic search, including existing transcript links.
- Exact phrase and broader name release matches each get a required original passage, scoped by product family.
- Distinct-source selection and required-first fair evidence budget; follow-up may displace optional prior evidence without reusing citation IDs.
- Requested scope checked separately from claim support; host blocks full verification when required evidence/images are missing.
- Ambiguous recording names request a relative path. Existing schema, source vectors, Qwen model and Gap workflow retained.
- Captured export replay and synthetic changed-name SQL cases accompany verification. No claim of live answer parity.

# v0.20 — POC 2 evidence coverage and visual checks
- Question-focused original-source reads include relevant sections, neighbours and both ends; complete short-source reads up to 24 units.
- Exact named local recording lookup, bounded timestamped samples, shared images for Assistant/Verifier, run-local copies for diagnosis.
- VISUAL citation basis requires frame evidence. Final validation checks image and recording hashes.
- Verifier must assess evidence coverage and cannot PASS with outstanding retrieval requests.
- Additive QA frame foreign key; existing source vectors, Qwen model and Gap Analysis behavior retained.
- Fresh setup and independent ChatGPT comparison instructions included.

# v0.19 — improved knowledge-source investigation

See docs/CHANGES-v019.md, START-HERE.md and GPT-Comparison-Prompt-and-Questions.txt. Existing source vectors and Gap POC retained.

# v0.18 — dual POC launcher and verified knowledge retrieval

See `docs/CHANGES-v018.md` and `START-HERE.md`. Existing gap analysis and HNSW comparisons retained.

# 0.17 — transcript context and measured retrieval comparisons

- Add grouped timestamped SRT passages alongside immutable legacy cues; original citation IDs remain valid. Grouped readiness requires all vectors for the selected profile. Other file parsers and vectors are reused.
- Add reusable, hash-verified frame cache and explicit frame evidence links. Referenced cached frames and diagnostics are included in run exports.
- Add source/finding halfvec HNSW expression indexes, original-vector reranking, keyword search and actual query-plan reporting.
- Add /compare, /mode, /search-health and build/check scripts. Comparison shares a query embedding and database snapshot, and distinguishes chunking changes from ANN recall.
- Keep v0.16 A/B/C workflow, T02/T04/T05 and whole-module /review. Production schema redesign, writer and cross-client policy work remains paused.
- See START-HERE.md for safe upgrade, commands and validation limits.

# 0.16

Shared supplied batch evidence for whole-recording assessment; precise citation errors; whole-module topic context; initial attempt plus two validation corrections; preserved attempt logs; fingerprinted/revalidated batch checkpoints. Existing A-to-B provenance, embedding profile guard, PostgreSQL schema and manual import policy retained. See START-HERE.md.
