# v0.14

- Fix exact-label consolidation mismatch: host derives topic modules from original observations, normalizes only syntax and splits distinct module groups. Preserve raw proposal and audit mapping.
- Remove automatic activity windows. Main-console events/10-second heartbeat use a bounded asynchronous queue; pipe readers/cancellation/log writes do not depend on console rendering.
- Add guarded pre-A-save failed-run resume, including copying old run artifacts into the current release, preserving old evidence, source hash checks and duplicate-output prevention.
- Include v0.13.1 FFmpeg capability detection and complete decode diagnostics.
- Preserve contracts, 29-table schema, manual processing, local embedding profile and exact-run gap reporting. No new database migration or reset.
