# TD POC v0.17

Start with **START-HERE.md** for the full upgrade and test commands. Keep the v0.16 folder and back up knowledge_poc before setup. Do not run the fresh schema installer over your existing database.

This release adds grouped transcript passages without replacing original cue IDs, reusable timestamped frame evidence, halfvec HNSW candidate search with original-vector reranking, and three-mode comparison. Same A/B/C workflow, test cases and local Qwen embeddings; Codex remains the reasoning engine. Startup scans only; /process is manual.

Setup once: `Setup-POC.cmd`. Start: `Start-POC.cmd`. Check: `/search-health`. Prepare grouped vectors: `/process`. Compare: `/compare your question`. Choose mode: `/mode old_exact`, `/mode improved_exact`, `/mode improved_hnsw`. Full module: `/review`. Saved results: `/results latest`, `/ask your question`.

Production schema redesign and writer/ReadMe/cross-client policy work are paused. See docs/DECISIONS-PARKED.md. This is an internal POC, not production publication approval.
