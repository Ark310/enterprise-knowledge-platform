# v0.17 progress
User approved Option A and all three comparison modes; implementation authorized.
Inspection: source supplied includes environment and runtime files; excluded from new release. Original cue parser and extraction version stay unchanged. Grouped retrieval will use an alternate extraction, avoiding active-extraction swaps that would break old tests.

Completed: grouped transcript extraction alongside old cues, parent/next/derived provenance, profile-scoped readiness, transcript/video linkage and duration checks; frame cache with explicit frame/record persistence and portable run exports; profile-specific source/finding HNSW indexes and matching queries; repeatable-read comparison plus compact console commands and full reports.
Ruling: retain baseline cue extractions as active to preserve original A citations. Alternate grouped extractions are selected by v0.17 retrieval only after embedding completion. Cost: temporary additional cue and grouped vectors; intentional for comparison/rollback.
Ruling: grouping starts with deterministic sentence/time/size/pause rules, not an unvalidated AI topic-segmentation call. Cost: boundaries are heuristic and need real-corpus evaluation; neighbour context mitigates fragmentation.
Ruling: compare requests the ANN access path and reports actual plans; timing excludes embeddings/reasoning and fixed order is not a production benchmark. No recall/quality guarantee.
Final: fixed independent-review findings (export, readiness, derived ANN, cache shape, pairing). Tests: 65 Python, 25 host, 23 synthetic database checks, Release build green. Operator Windows/live-model validation remains required and explicitly documented.
