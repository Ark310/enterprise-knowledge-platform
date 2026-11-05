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
