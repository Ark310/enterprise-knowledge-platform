# POC 2 evidence coverage — implementation plan
Approved scope: implement the POC 2 improvements discussed in the comparison. v0.20 retains POC 1 and existing source vectors; additive QA frame audit column only.

1. Question-focused reading: prioritize matching passages, adjacent context, opening and ending; whole short sources up to 24 units. Report actual supplied coverage. Test late outcome, adjacent context, bounded long sources and stable IDs.
2. Visual evidence: exact recording-name matching only; at most two recordings, 12 timestamped samples each, selected from transcript question hits plus opening/ending. Reuse existing frame extractor/cache, pin imported recording hash, save frame snapshots to QA audit. Assistant and Verifier see identical images. No transcript-only visual proof. Missing/ambiguous videos are explicit limitations. Test wrong-name/duplicate-name, bounds, tampering, citations and host image handoff.
3. Verifier: require evidence_coverage_sufficient and coverage_reason; PASS cannot coexist with missing coverage or outstanding read requests. Keep one bounded follow-up. Audit and compare exact evidence packets separately from independent retrieval.
4. Version, instructions and release: no schema reset, no automatic answer embedding, no POC 1 behavior changes. Python suite, host/build checks, disposable DB/FFmpeg checks where available. Package source, setup/retest guide and identical ChatGPT prompts.

Engineering choices: new QA-only module; matching is conservative rather than guessing a video. Sampling does not prove absence between frames. Images are files, not database blobs. Export includes copied sampled images, which can contain source-screen information. No promise of ChatGPT parity before real corpus retests.

## Verification ledger
- Python regression tests cover separate frame IDs, required visual plans, exact-path disambiguation, missing recording names, frame-only visual citations, evidence coverage and source change during sampling. RED→GREEN observed.
- Reviewer found two important edge cases: path disambiguation and optional visual planning fields. Both fixed with RED→GREEN regressions.
- Ruling: optional verified_source_hash parameter on shared frame helper retains existing Gap call behavior; QA checks recording once before/after the whole sample batch to avoid re-hashing large MP4s for every still. Final publication rechecks recording and image hashes.
- No external repo was supplied; release built in isolated extracted ZIP tree.

Complete: source reads, frame audit, dual-agent image handoff, coverage gates, setup/retest docs and regression verification. All suites green; real corpus retest is operator acceptance.
