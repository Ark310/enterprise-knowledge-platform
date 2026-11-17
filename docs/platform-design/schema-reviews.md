# Production schema revision 8 and its independent reviews

> **Design only.** The production schema below was never installed. On 3 Nov 2026, after these reviews,
> production work was explicitly **parked** and the POCs continued on the approved v0.3.0 schema with
> additive migrations (see [`docs/DECISIONS-PARKED.md`](../DECISIONS-PARKED.md)). This page summarises
> the reviews in my own words; the original PDFs are not published.

## What was reviewed

A 59-table production proposal ("revision 8") written as a decision document plus a machine-readable
schema model, covering:

| Schema | Tables (examples) | Role |
|---|---|---|
| `integration` | connections, sync_streams, sync_events, outbox_events | Connector configuration (support portal, Microsoft Graph, local folders), cursors, events |
| `knowledge` | sources, source_versions, processing_jobs, representations, sections, chunks, chunk_evidence, topics | One identity per item, append-only revisions, processing builds |
| `retrieval` | embedding_profiles, chunk_embeddings, policies, requests | Versioned embedding profiles, search policy, query log |
| `support` | tickets, ticket_comments, ticket_attachments, ticket_resolutions, ticket_changes, time_entries | One ticket identity; open/closed are views |
| `collaboration` | conversations, messages, meetings, meeting_assets | Teams chats and meetings |
| `analysis` | runs, run_steps, findings, finding_evidence, finding_links | Agents as data: definition → version → run → step → attempt |
| `review` | review_cases, review_decisions | Human decisions on findings and publications |
| `security` | access_scopes, access_grants (plus tenants, principals, memberships) | Tenant and audience scoping |

The same plan was given to two models for an **independent cross-model review**: Claude and Gemini
(both 3 Nov 2026). Neither had a live database; both reviewed the design documents, and the Claude
review also read the v0.16 source and two real run exports.

## Verdicts

- **Claude:** "Not good enough for production yet, but the shape is right, and it needs targeted fixes,
  not a redesign." What it called right: one identity per source with append-only revisions; originals
  outside PostgreSQL; processing recipes as versioned profiles; one ticket row with open/closed as views;
  agents as data so a new agent needs no new tables; findings, review and publication as separate stages;
  correct halfvec HNSW plus rerank reasoning.
- **Gemini:** the shape is comprehensive, but treating it as production-ready before fixing tenant
  isolation, polymorphic references, dimension verification and hard-fail redaction would be premature.

Both converged on the same blockers.

## Findings (Claude review: 6 blockers, 8 high, 10 medium, 2 low)

| # | Severity | Finding | Proposed fix |
|---|---|---|---|
| F1 | Blocker | Tenant safety only in prose: no UNIQUE keys, single-column FKs, so cross-tenant links were possible in 121 references | `UNIQUE (tenant_id, id)` on every tenant table; every FK carries the tenant; natural keys per table |
| F2 | Blocker | Nothing proves redaction happened before an external LLM call | New `model_calls` table: every external call references a passed redaction check, and the payload hash must equal the check's output hash |
| F3 | Blocker | Customer-support retrieval could reach raw chunks of a published revision | Client-facing eligibility = only the redacted representation tied to the publication's check, through one view |
| F4 | Blocker | An agent principal could record an approval | Trigger: reviewer must be an active **human** membership with an approve grant on that audience |
| F5 | Blocker | PII in metadata columns (titles, external keys, error summaries, raw event payloads) bypasses redaction | Classify columns; only the redacted payload may leave the boundary |
| F6 | Blocker | Lineage consistency not enforced (a section's job could belong to another revision, etc.) | Composite "same-parent" foreign keys |
| F7 | High | Production design lost a safeguard the POC has: visual claims need a frame, narrated claims need a transcript cue | Add modality and typed timestamps to `finding_evidence` |
| F8 | High | Retry after a partial save could duplicate sections and chunks | Attempt and build identity; `UNIQUE (build, sequence)`; only a succeeded build is eligible |
| F10–F11 | High | Per-tenant embedding profiles fight HNSW; permission filtering needed four joins per ANN candidate | Global profiles; denormalise tenant, scope, build and eligibility onto embeddings |
| F13 | High | Internal ticket notes not distinguished from client-visible ones | Comment visibility mapped to a scope |
| F23–F24 | Medium | POC silently truncated findings to 3,000 characters; transcript chunks too small (median 74 characters in one run) | Reject or split, never truncate; evaluate chunking on a fixed question set |

## How the POCs responded

The POC is single-tenant and local, so the tenant blockers were recorded for the production design.
The evidence-quality findings went straight into the next releases:

- **F24 (tiny transcript chunks)** → v0.17 grouped timestamped SRT passages (target 30 s, max 60 s),
  keeping the original cues for citation.
- **Vector dimension "not verified"** → v0.17 checks the stored dimension (2560 for
  `qwen3-embedding:4b`) instead of assuming it; immutable embedding-profile digests already stopped
  vectors from different models being mixed.
- **HNSW recall** → v0.17 added a three-mode comparison (`old_exact`, `improved_exact`, `improved_hnsw`)
  on one shared query embedding and DB snapshot, with recorded query plans proving index use.
- **F7 (visual vs narrated evidence)** → kept and strengthened in POC 2: a `VISUAL` citation needs an
  actual frame, and image and recording hashes are rechecked at publication (v0.20).

## Acceptance scenarios proposed (to run as automated tests against a migrated copy)

Cross-tenant denial; ticket reopen keeps identity and history; a late, older comment event never moves
the current pointer back; an invalid SRT blocks the transcript without crashing ingestion; a new SRT
revision gets new chunks while old citations still resolve; unsupported media is registered but not
searchable; a superseding article suspends the old one for client-facing use; an SME correction creates
a linked revision; a denied publication never reaches client-facing search; an agent attempting approval
is rejected; killing a worker mid-build and retrying leaves exactly one eligible build; HNSW recall is
measured against exact search under selective tenant filters; a failed redaction refuses the external
call and quarantines the item.

## Staged migration plan (Claude review)

1. Inventory and back up, with a restore test. 2. Create new schemas beside the POC. 3. Backfill
identity with an old→new ID map. 4. Backfill analysis; frame citations imported from run exports, never
invented. 5. Re-process under new profiles; the new chunking must beat the POC on a fixed question set.
6. Shadow retrieval with tenant-denial and recall gates. 7. Switch through compatibility views, one agent
at a time. 8. Retire POC tables only after the rollback window and a second restore drill.
