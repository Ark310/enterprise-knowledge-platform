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
