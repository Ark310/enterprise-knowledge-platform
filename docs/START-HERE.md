# TD POC 0.10 — start here

Built for the supplied machine: Windows Server 2019 x64, Ryzen 7 7700 (8 cores/16 threads), 31.1 GB RAM, RTX 5060 Ti 8 GB, .NET SDK 10.0.403, Visual Studio Community 2026, Codex CLI 0.163.0 and existing Ollama. This is a local single-user POC, not a production service. Live Windows/GPU/Codex acceptance happens on your machine; see VALIDATION.md for what was actually tested by the author.

## 1. What you are running

Codex performs all three agents' reasoning. Ollama runs **qwen3-embedding:4b** for vectors only. This is different from your installed `qwen3:4b-thinking-2507-q4_K_M`. No agent SDK or separate reasoning API key is used. Codex uses your existing saved CLI login and account limits. The POC deliberately omits ambient user Codex configuration/MCP integrations and disables shell tools, code mode, Apps and web search on its reasoning invocations. Your other Codex projects/configuration are not edited.

The C# solution owns the console, workflow and process orchestration. A bundled Python worker performs PostgreSQL access and document parsing using psycopg and mature document libraries. This is an implementation choice: no Npgsql is required. It remains one launchable Visual Studio solution; setup creates an isolated Python environment so existing Python applications are not changed.

Your original folders remain unchanged:

- `C:\S3 bucket Data\current-state`
- `C:\S3 bucket Data\existing-assets\Confluence Articles`
- `C:\S3 bucket Data\existing-assets\REST API`
- `C:\S3 bucket Data\existing-assets\Sharepoint`
- `C:\S3 bucket Data\existing-assets\VLCs`

`existing-assets\Meeting Recordings` is never traversed. Folder links/junctions, symlinks and Office `~$` temporary files are skipped. Files are not executed. No product API samples are sent to a live product endpoint.

## 2. Extract the solution

Extract the package to `C:\TD-POC-v0.10`. Avoid special characters such as `&`, `%`, `!` in the solution path because Windows command shims need safe quoting. Preserve the package's subfolders. Do not extract over your evidence folder or another project's folder.

Open CMD:

```bat
cd /d C:\TD-POC-v0.10
```

Use the same Windows account that is signed into Codex. Do not run setup under a different account unless you intend to configure that account separately.

## 3. First-time model and dependency setup

```bat
Setup-LocalModel.cmd
```

This finds Python 3.11+, creates `.venv`, installs the pinned Python packages, checks Ollama, downloads `qwen3-embedding:4b`, warms it with a small readiness input, builds the .NET solution and runs offline evidence tests. It does not import your evidence, reinstall Codex or delete existing models. It never stops unrelated processes.

Ollama is already present on your Server 2019 machine. The Windows Ollama documentation lists newer Windows desktop requirements; therefore native compatibility must be established by the readiness check on this machine, not assumed from installation alone. If an installed build cannot load the model, retain the exact error and stop there rather than switching platforms/models silently.

For video-frame evidence, check:

```bat
ffmpeg -version
```

If unavailable, run:

```bat
Setup-VideoTools.cmd
```

This downloads a Windows ZIP build from Gyan (linked by the FFmpeg project), extracts it beneath this solution and records its path in configuration. No system PATH changes. If corporate internet policy blocks the download, place an approved ffmpeg.exe on PATH or set `FFmpegExecutable` in `config\appsettings.json` to its full path. No automatic audio transcription is performed.

## 4. Configure PostgreSQL privately

```bat
Configure-Database.cmd
```

Enter host `localhost`, port `5432`, database username and password. Database name is fixed to `knowledge_poc`. The script encrypts the connection for your Windows account using DPAPI in `config\database.dpapi`. Do not send this file, passwords or Codex auth.json to anyone. The app can also read `TD_PG_CONNECTION` as a libpq connection string for controlled testing.

Your existing `postgres` account can be used for this local setup/migration. For continuing POC operation a dedicated database role is preferable; database provisioning/permissions depend on your policy and are not silently created by this package. The POC process must be able to read/write the approved tables and call vector operations. Codex never receives the connection string; the host performs DB operations. This is not an OS-level tenant boundary: anyone who can run code as your Windows user may access your user's protected secrets.

## 5. Apply the local-file compatibility migration once

```bat
Initialize-Database.cmd
```

Expected: `010-local-files applied`, database `knowledge_poc`.

You already installed the approved schema. **Do not rerun the fresh installer**. The v0.10 migration only permits explicit LOCAL_FILE storage objects with no fake Drive IDs. It preserves the 29 tables, 301 fields and 55 foreign keys, existing data and original Drive-root mappings. It can be rerun safely. Do not run it against another database. `database\approved-v0.3-fresh-install.sql` is for a completely new database only, retained for reproducibility.

## 6. Start the POC

```bat
Start-POC.cmd
```

Equivalent command after Ollama is available:

```bat
dotnet run --project src\TD.Poc.Console\TD.Poc.Console.csproj --configuration Release
```

Startup loads/decrypts your DB settings, checks DB and Codex login, warms the embedding model and scans all five roots. The readiness input generates a small disposable vector, but no source content is imported/embedded until you explicitly process.

Expected console: file counts, pending extraction count, scan errors, commands and `You>` prompt. A first scan hashes all included files, so it can take time on 6–10 GB. It is read-only with respect to evidence and database data. It writes only `runtime\last-scan.json`. It does not infer that the earlier Drive inventory count matches the local collection.

## 7. First import and re-runs

At `You>`:

```text
/pilot
```

This opens a worker window for the first ten files in deterministic path order. It is an ingestion smoke check, not a representative quality benchmark or an automatic selection of User Master files.

Then:

```text
/process
```

This scans again, registers all discovered files, extracts supported content and creates missing vectors. It uses a database advisory lock so only one import worker runs at once. The main window remains available. Use `/status` while it works. Run analysis tests only after relevant processing completes.

Each file gets a physical identity and hash revision. Repeating processing reuses the same revision/units/vectors when unchanged; it retries missing vectors. A changed file gets a new version and the old version becomes SUPERSEDED. Old analysis outputs remain historical proposals; they are not silently rerun or declared current. Missing/deleted files are not automatically deleted or deactivated by v0.10: review them before relying on search. Replacing a file intentionally selects its new local revision; modification time is not proof of universal product truth.

Processing summary distinguishes committed registrations/extractions, blocked formats, failed operations and new vectors. `intake_batches.scan_status` describes enumeration; import outcome is stored separately in its `notes.processing_summary`. A scan-complete result does not mean every file was processed successfully.

### Coverage by asset type

| Asset | v0.10 handling |
|---|---|
| SRT | Original cue times and text; supplied narration evidence |
| Markdown, text, code, CSV, HTML, XML | Text extraction/chunking with locators; never executed |
| JSON/Confluence | Parse JSON; readable article text plus physical provenance |
| REST page.json | Version-scoped endpoint, nested parameters, reference responses, snippets and Try It capture; raw status labels retained |
| DOCX | Paragraph text and locators, including text in tables |
| XLSX/XLS | Sheet/row/cell content; formulas preserved where supported, not recalculated |
| PDF | Extracted page text; pages without text flagged for OCR |
| MP4/WMV/other video | Register original; selected test ranges sampled into frames; separately imported SRT provides narration |
| PNG/JPG/SNAG/legacy DOC/other binary | Register and BLOCK conversion/OCR; no fabricated extraction or successful embedding |

Physical alternate exports remain separate for provenance and can produce duplicate retrieval candidates. v0.10 does not promise canonical article deduplication or exhaustive semantic inventory. Unsupported formats are intentionally visible in status; fully processing your collection will require later OCR/native conversion work. A READY database is not proof of complete document comprehension.

## 8. Talk to Agent C

Type ordinary questions, for example:

```text
What evidence do we have about Authentication Type in User Master?
```

Agent C can request bounded search or status/scan operations. The host supplies actual results. Natural-language requests to process data result in instructions to type `/process` or `/pilot`; they do not bypass manual control.

Useful commands:

| Command | Meaning |
|---|---|
| `/scan` | Find current new/changed files; no import |
| `/pilot` | Process first ten allowlisted files in another window |
| `/process` | Process all included files; resume missing embeddings |
| `/status` | Actual DB totals, jobs and recent runs |
| `/search your question` | Hybrid search then Codex explanation with evidence |
| `/run C:\path\request.json` | Run a custom START_CURRENT_STATE request for another recording/topic |
| `/test T02` | Run A → validate/save/embed → B → validate/save/embed |
| `/help` | Command reminder |
| `/exit` | Close main console; an already running worker is a separate process |

The bounded search returns source passages and derived findings. Derived findings are AGENT_PROPOSED, may reference superseded evidence, and are not independent corroboration. Coordinator context is a bounded local history, not this ChatGPT conversation. Source text/selected frames and questions are sent to Codex for reasoning; local embeddings do not make Codex reasoning offline.

## 9. Add a new recording later

Place both `Topic.mp4` and `Topic.srt` in current-state. Copy them completely before scanning. Matching basename pairs are required for A/B recording tests. Filenames and matching names do not prove SRT alignment; agents must report uncertainty. For the original User Master tests below, provide an SRT with **original-video timestamps** alongside its MP4. The earlier DOCX transcript is not automatically retimed or renamed into SRT.

At startup files are found automatically. During a running session use `/scan`, then `/process`. No restart, ZIP creation or automatic agent run is necessary. Existing results do not automatically apply to the new recording. For another topic, copy a scenario JSON to your own request file and change its test ID, module, topic, target element, question, aliases and review ranges to match the actual recording. Then run `/run C:\path\request.json` and select its recording. The same schema/guardrails apply. Do not blindly apply old User Master time ranges to a new recording.

## 10. Run the same earlier User Master tests

The latest recommended cases are retained exactly, with original reviewer expectations separated:

| Test | Topic | Original-video range | What to ask/check |
|---|---|---|---|
| T02 | Two Factor Authentication / Authentication Type | 08:15–09:30 | Actual options and visible states; separate narrated claims from saved/login outcomes |
| T04 | Time Zone | 01:30–02:45 | Location/value/option format and narrated purpose; no invented persistence/enforcement |
| T05 | Profile button | 10:50–11:45 | Observed navigation/destination vs narrated purpose; no inferred security changes |

T01 (Time Zone) and T03 (Profile button) from the earlier v2 pack are also available for historical regression comparisons. Prefer the refined T04/T05 requests. Additional older Bank Upload, Bank Reconciliation, Fiscal Periods and Finance Invoice packs are preserved under `tests\legacy`; they are historical packs, not silently migrated into the v2.1 User Master workflow.

Run `/test T02`, then enter the exact MP4 path relative to your data root, for example:

```text
current-state\System Admin_ Security_User Master Walkthrough.mp4
```

The app checks that recording and matching SRT were imported at their current hashes. It creates a **new local launch request** derived from the original case, with a unique run ID, explicit local archive labels and actual recording/transcript paths. The derived request is preserved unchanged across A/B. Original scenario files are not overwritten.

Frames are sampled every two seconds within the selected ranges, up to 80 per range. This does not establish clicks/transitions between frames. A must remain partial or qualify claims requiring denser evidence. Missing ffmpeg means no visual evidence, so visual/corroborated claims are rejected. No independent original-audio listening is claimed. A transcript alone cannot prove saving, persistence or login outcomes.

Console events show stage starts, validation gates and handoffs. Codex's exposed JSON event stream is retained; hidden chain-of-thought is not exposed. If A is invalid or blocked, B does not run. B retrieves up to 60 hybrid candidate passages; incomplete inventory/linked guidance must be disclosed, never turned into a company-wide absence claim.

A/B contract is still `td-doc-review-2.0`, instructions 2.1.0 with a documented local-file adapter. Text citations copy exact supplied locator JSON and verbatim excerpts; visual locators identify an attached frame. The app checks structure, IDs, exact request preservation, observation coverage and supplied citation provenance. It does not prove visual interpretation or every semantic claim true. No human approvals are invented; records stay AGENT_PROPOSED.

## 11. Bring results back for review

Run:

```bat
Export-LatestRun.cmd
```

Upload that ZIP here. It includes the local request, pinned evidence packet, sampled frames, raw A/B outputs, validation results and events. If B did not run, its absence and failure logs are part of the diagnosis. The exported bundle contains internal source excerpts: share with authorised reviewers only.

A useful review request is: “Review this v0.10 T02 run against the original reviewer checks. Check citations, current-state scope, A/B handoff, uncertainty, article-purpose fit and whether PASS/PARTIAL/FAIL is justified.” Repeat for T04 and T05. Do not attach the reviewer-only expected-result files to the runtime agents.

## 12. Open and understand the solution

Open `TD.Poc.sln` in Visual Studio Community 2026. Set `TD.Poc.Console` as the startup project, choose Debug or Release, then press Ctrl+F5. You can also use F5 to debug. The application finds the solution root by walking parent folders. First-time setup/configuration/migration must already be complete. To run offline host tests in the solution, temporarily select `TD.Poc.HostTests` as startup project; this is a console test harness, not Visual Studio Test Explorer discovery.

- `agents\agent-a-current-state.md`: original current-state operating rules.
- `agents\agent-b-documentation-review.md`: original article-review operating rules.
- `agents\agent-c-coordinator.md`: conversation/action rules for the third agent.
- `agents\shared-guardrails.md`: local evidence adapter and machine-checked citation format; appended after original A/B instructions.
- `contracts\contracts-v2.schema.json`: unchanged approved schema.
- `src\TD.Poc.Console\Program.cs`: startup/menu and command dispatch.
- `src\TD.Poc.Core\Workflow.cs`: C conversation and A/B orchestration.
- `src\TD.Poc.Infrastructure\Runtime.cs`: safe subprocess plumbing, secret loading, Codex event capture.
- `tools\worker.py`: scanner, extraction, DB access, vectors, retrieval and output checks.
- `config\appsettings.json`: paths/model/runtime settings; no passwords.
- `docs\architecture-and-tables.html`: self-contained combined workflow and all-table graph; open in browser, select a table to highlight its exact FK links.
- `docs\table-fields.md`: field dictionary and meanings from the approved schema.
- `runtime\runs\...`: each test's immutable evidence packet and outputs.
- `runtime\workflow.log`: stage/handoff audit.

## 13. Troubleshooting

- **Model missing:** run Setup-LocalModel.cmd. Do not substitute a thinking/chat model.
- **Ollama unreachable:** run `ollama serve` and preserve the error; the launch script checks an existing service first.
- **Codex CLI flag error:** preserve the exact error and run `codex exec --help`; the package uses documented exec/JSON/read-only/ignore-user-config flags and feature overrides. Do not bypass the sandbox to force a run.
- **Codex rate limit/auth:** run `codex login status` under the same account; retry after access is restored.
- **DB failure:** run Check-Status.cmd. Confirm the DB is knowledge_poc and the encrypted connection belongs to the running Windows account.
- **Invalid handoff:** inspect validation-a.json or validation-b.json plus raw output; don't hand-edit it into a fake PASS. Start a new corrected run.
- **Missing frames:** configure ffmpeg; transcript-only partial results can be valid but not visual verification.
- **Partial corpus:** inspect blocked/failed jobs and processing summaries. PNG/SNAG/legacy DOC need later extraction/conversion; none are silently complete.

References checked during development: OpenAI Codex non-interactive and configuration docs; Ollama embed API and Windows docs; Qwen3 embedding model cards; FFmpeg download page. Versions and live capabilities should be confirmed on the target during acceptance.
