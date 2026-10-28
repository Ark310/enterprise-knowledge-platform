# Implementation decisions

- The approved folder layout is implemented. Mature Python extraction and psycopg DB operations are hosted behind the C# console/core/infrastructure boundary; no Npgsql or agent SDK dependency. Cost: Python venv is an additional local setup dependency.
- Codex calls omit ambient user configuration and disable shell/code/App/web capabilities. This avoids importing AML project integrations, but a custom CodexModel may need configuration if the account default differs. Installed CLI compatibility is checked at startup, not claimed from a fixture.
- Sparse video frames are evidence only for the sampled instants; rapid transitions remain unverified. This keeps initial scope manageable without claiming complete video comprehension.
- Images/SNAG/legacy DOC remain visible blocked conversion tasks; no placeholder success states. Further extraction support is future work.
- Local files use explicit LOCAL_FILE objects while the existing two Drive group mappings remain available for future connectors. No fake Drive IDs.
- Historical analyses are retained. Superseded-source indicators are returned for derived results; source removal and full automatic invalidation need later policy work.
