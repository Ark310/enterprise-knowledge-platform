# TD POC v0.12

Start with **docs/START-HERE.md**. Existing approved PostgreSQL schema/data is retained.

One-time setup (CMD):

```cmd
cd /d C:\TD-POC-v0.12
Setup-POC.cmd
```

Daily start: `Start-POC.cmd`. Startup scans only. `/process` explicitly imports and embeds. Wait for that worker before `/test T02`.

Codex supplies reasoning through a dedicated POC ChatGPT login. Ollama `qwen3-embedding:4b` supplies source, query, A observation and B finding vectors via the same immutable database profile. Agents never receive database passwords.

Each invocation opens a read-only PowerShell activity window on Windows. Press Q there, or Ctrl+C in the main console during a Codex call, to cancel that call. Closing a viewer does not cancel it. Logs are live; use Export-LatestRun.cmd even during a test. No private internal model reasoning is exposed.

Architecture and all tables: docs/architecture-and-tables.html. Agent instructions: agents/. Contracts: contracts/. Diagnosis: docs/DIAGNOSIS-v0.11.md. Verification and platform limits: VALIDATION.md.
