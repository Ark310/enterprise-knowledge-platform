# v0.12 verification

Executed in the Linux build environment with .NET SDK 10.0.403:

- Full Release solution build: success, 0 warnings, 0 errors.
- Python evidence/contract suite: 21 tests passed.
- C# host fixture suite: 16 assertions passed. Includes stdin safety, DB-secret removal, isolated CODEX_HOME, live event/stderr visibility before exit, completion status, cancel-file process stop, timeout with retained partial logs, and nonzero exit retention.
- Corrected supplied SRT: COMPLETE, 212 cues using v0.12's unchanged strict SRT parser.
- Captured B response from uploaded v0.11 run: original schema and literal citation checks pass offline. No claim of B database persistence or human semantic correctness.

Not executed here: native Windows PowerShell setup/UI, Windows DPAPI, actual ChatGPT/Codex calls, live PostgreSQL writes or local GPU performance. The release requires a native setup/readiness check and T02 run on the user's server. The original schema, migration and parser extraction version are retained; no database reset is needed. Historical docs/verification-logs belong to earlier versions and are not new v0.12 evidence.

Live reasoning status COMPLETED is process completion only; host validation, PostgreSQL save and local embeddings must subsequently succeed. No attempt is made to display private internal reasoning. Underlying service latency is outside the host's control.

Logs from build and current automated suites are in docs/verification-v012/.
