# v0.26 verification

- .NET10 solution Release build: zero warnings/errors.
- Python suite: 152 tests pass. Includes all three captured v024 screenshot failures, ambiguous/unique recording titles, selected-video normalization, transcript-only requests, point-only cues and reversed-timing rejection.
- Host suites: 25 runtime checks +41 Knowledge-flow checks pass.
- Real uploaded samples: both MP4/SRT pairs imported in disposable PostgreSQL17.7/pgvector0.8.1 with real FFmpeg. Twenty checks pass for current-profile transcript readiness, no repeat vectors, exact recording identity, original JPGs, cached frames, pinned playback references, stale-transcript rejection and article-image normalization.
- Five direct HTTP API check groups pass: selected-video Knowledge/Verifier save flow; actual JPEG bytes and206 MP4 range playback; identical agent image attachments; concise scan with stale selection; videos/status/process controls with stale selections.
- Independent source review found maintenance-pin and readiness/companion issues. Both were corrected and regression/integration tested; no remaining Important/Critical source blocker reported.
- JavaScript syntax check passes.

## Limits

Deterministic substitute model responses exercise the actual host, database, extraction and verification boundaries. They do not establish live Codex reasoning/vision accuracy. No operator account or production database was used. Rendered-browser and native Windows agent-window behaviour still require a local smoke test; no browser visual pass is claimed. Sampled frames do not prove continuous visual coverage or successful outcomes. Transcripts remain supplied speech evidence, not independent audio alignment.

Both sample SRTs contain zero-duration cues (one and five respectively). They remain unchanged on disk. v025 preserves these as POINT_ONLY timestamps with warnings; it does not invent durations or silently remove their text. Existing ordinary transcript/vector identities are retained, so unchanged material is not forced through re-embedding.
