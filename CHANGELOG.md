# v0.15

- Explicit UTF-8 process protocol plus ASCII-safe JSON response transport; replay actual failed-run Unicode packet.
- Exactly one aggregate A viewer and one aggregate B viewer per fresh workflow; compact main status/results, full logs retained.
- Persist all worker stdout/stderr, exceptions, phase checkpoints and failure context into review exports.
- Guarded resume after A save verifies the persisted handoff/records/vectors/model/source identity and avoids duplicate A storage.
- Explicit organizational-context prefix mapping and identical-title topic consolidation; retain immutable observations and full mapping audit.
- Preserve schema/contracts, same local embedding profile, original targeted tests, FFmpeg compatibility fix and source extraction fingerprint.
