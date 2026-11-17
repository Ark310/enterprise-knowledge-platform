# Enterprise platform design (not yet built)

> **Status: design only.** Nothing in this folder is implemented. The code in this repository is the
> two local proofs of concept described in the [main README](../../README.md). This folder is a
> sanitized summary, written for the portfolio, of the design work that ran beside the POCs:
>
> - the *Enterprise Knowledge Intelligence Platform* engineering narrative v1 (9 Nov 2026, marked
>   "draft for engineering review, not an approved implementation specification"),
> - the architecture and engineering review package v3 (blueprint v3, requirements, decision
>   register, agent catalog, six Mermaid diagrams, an illustrative `schema-v2.sql`; 4 Nov 2026),
> - the production schema proposal (revision 8, 59 tables) and two independent AI reviews of it
>   (3 Nov 2026), summarised in [schema-reviews.md](schema-reviews.md).
>
> The original documents are not published here. They name the company and contain internal context.

| Document | What it covers |
|---|---|
| [README.md](README.md) (this file) | Goals, the three-domain model, the target architecture, audiences, and the gap from the POCs |
| [portal-integration-and-identity.md](portal-integration-and-identity.md) | Support-portal integration, in-app diagnostics, SSO / tenant open questions, ReadMe.io publishing |
| [api-surface.md](api-surface.md) | The proposed versioned service API and how the POCs map onto it |
| [schema-reviews.md](schema-reviews.md) | Production schema revision 8 and what the independent Claude and Gemini reviews found |

## Why a platform and not a chatbot

Product knowledge for TradeDesk (a back-office FX and payments product) is spread across a
Confluence help site, REST and SOAP API docs, SharePoint, training recordings, support tickets,
meetings and individual people. Some of it is stale, some applies only to one release or one client's
configuration. A search box would make it easier to find, but it would not tell anyone whether an
answer is **safe, correct, current and applicable**.

The design therefore treats knowledge as evidence with provenance, scope and a verification state,
and treats every consumer (staff assistant, support portal, client self-service, the application
itself) as a client of one governed service rather than a separate chatbot each.

## Design principles (from the narrative)

- **API-first and reusable.** Intelligence is exposed through versioned APIs and events; applications are consumers.
- **Evidence over fluency.** Every substantive answer carries citations, scope and uncertainty.
- **Deterministic controls.** Authentication, authorization, workflow transitions, publication gates and withdrawal are enforced in software, never in prompts.
- **Privacy before shared retrieval.** Raw material is quarantined and classified; sensitive content is removed or restricted *before* it enters a shared index.
- **Replaceable dependencies.** Model gateway, embedding provider, retrieval engine and orchestration runtime sit behind interfaces.
- **Human judgement where needed.** AI resolves well-evidenced cases; uncertain ones go to an authorised team; publication always has a human approver.
- **Incremental delivery.** Prove one complete vertical slice, then add sources, services and external audiences.

## Three domains

```mermaid
flowchart LR
  subgraph A["A. Knowledge Engineering"]
    C1[Connectors<br/>Confluence, Teams/Graph, support portal,<br/>MP4 + transcripts, Swagger/OpenAPI, guides]
    S3[(S3<br/>raw / quarantine / derived)]
    X[Extraction + privacy classification<br/>+ sanitisation]
    K[Normalisation, chunking, provenance,<br/>versioned embeddings]
    C1 --> S3 --> X --> K
  end
  subgraph B["B. Knowledge Intelligence Services (API-first)"]
    R[Authorisation-aware retrieval]
    Q[Conversational answers]
    SC[Similar-case and resolution search]
    D[Contextual diagnostics]
    RC[Evidence reconciliation]
    DP[Documentation planning]
    AC[API contract intelligence]
  end
  subgraph C["C. Knowledge Applications"]
    IA[Internal staff assistant]
    SP[Support-portal integration]
    CA[Client self-service assistant]
    APP[In-app diagnostics]
    DOC[Documentation review + ReadMe.io publishing]
  end
  PG[(PostgreSQL + pgvector)]
  WF[.NET workflow controller<br/>"Chief of Agents"]
  GOV[Governance: identity, tenant scope,<br/>audit, OpenTelemetry, withdrawal]
  K <--> PG
  PG <--> R
  K --> B
  B --> C
  WF -.-> X
  WF -.-> B
  WF -.-> DOC
  GOV -.-> A
  GOV -.-> B
  GOV -.-> C
```

1. **Knowledge Engineering** discovers and acquires material, keeps source identity and revision
   history, extracts content (text, timestamped transcripts, selected frames), detects sensitive
   information, and builds derived evidence and search representations. It never assumes a source is
   authoritative because of where it came from.
2. **Knowledge Intelligence Services** is the reusable core: authorisation-aware search, cited
   answers, similar-case detection, resolution recommendations, contextual diagnostics, evidence
   reconciliation, documentation planning and API contract intelligence. Short operations are
   synchronous; long investigations return a job ID and a completion event.
3. **Knowledge Applications** supply identity and authorised context, render answers and collect
   feedback. They never bypass tenant filters or query embeddings directly.

## Audiences

| Audience | What they get | Key constraint |
|---|---|---|
| **Staff** (onboarding, sales, implementation) | Grounded answers with citations, release context and visible uncertainty | Internal-only evidence allowed, still scoped by permission |
| **Support analysts** | On ticket creation: similar resolved cases, approved docs and known workarounds, ranked with evidence | Suggestions only; a human resolves the ticket |
| **Clients** (authorised users) | Self-service product answers | Must never see another client's configuration, customer lists, accounts, transactions or conversations; approved, redacted content only |
| **The application itself** (in-app diagnostics) | A sanitised error code plus context returns likely causes and runbook steps | No raw transaction payloads or account data leave the app |
| **Documentation team** | Gap detection, a draft in the right template, quality checks, human approval, publication | Draft generation alone does not close a gap |

## Evidence states

| State | Meaning | Use |
|---|---|---|
| Unverified | Extracted, not corroborated | May inform an investigation, with a warning |
| Corroborated | Supported by several consistent sources | Usable with scope and citations |
| Verified | Supported by runtime, test or owner evidence | Preferred for definitive guidance |
| Conflicted | Materially inconsistent evidence exists | Investigation or human escalation |
| Withdrawn | Not eligible for retrieval or reuse | Blocked; derivatives purged through lineage |

Authorised staff can **withdraw** an artifact without a maker-checker step. Withdrawal stops retrieval
immediately, and an asynchronous lineage job invalidates derived chunks, embeddings, summaries, caches
and pending publications, with an audit record for each step.

## Agreed and open decisions (decision register v3)

| ADR | Topic | Status | Direction |
|---|---|---|---|
| 001 | Stack | Agreed | .NET / C#, AWS, PostgreSQL + pgvector, S3; LLM provider behind an abstraction (OpenAI first) |
| 002 | Domains | Agreed | Knowledge Engineering / Intelligence Services / Knowledge Applications |
| 003 | Storage | Agreed | One PostgreSQL database to start, media originals in S3; split later only on observed limits |
| 004 | Embeddings | Agreed | Versioned, rebuildable derivatives, separate from authoritative knowledge |
| 005 | Ingestion | Agreed | Polling, webhooks/events and manual; Confluence becomes a legacy *source*, not a destination |
| 006 | Conflicts | Agreed | AI reconciles where evidence supports it; humans only when uncertain |
| 007 | Removal | Agreed | Permissioned, audited withdrawal; no mandatory admin approval |
| 008 | ReadMe.io | Conditional | Preferred single destination, only if internal/external audience separation is verified |
| 009 | Orchestration | Open | Microsoft Agent Framework vs. plain .NET orchestration; ~3-day proof of concept to decide |
| 010 | API verification | Open | What code, deployment and test evidence actually exists |
| 011 | Capacity | Open | ~3 TB of source assets (about half MP4); sample before sizing |
| 012 | Data security | Open | Tenant model, row-level security, encryption, retention |
| 013 | Hosting / SLOs | Open | Performance, RPO/RTO, HA, residency |

## From the POCs to the platform

| Platform capability | Where the POCs stand |
|---|---|
| Source identity, append-only revisions, hashes | **Built** (POC schema v0.3.0 + migrations) |
| Timestamped transcript evidence, frame evidence | **Built** (grouped SRT passages, hash-verified frame cache) |
| Hybrid retrieval with versioned embedding profiles | **Built** (halfvec HNSW + full-vector rerank + keyword + stemming) |
| Cited answers with an independent verifier | **Built** (POC 2) |
| Documentation gap analysis | **Built** (POC 1; findings stay AGENT_PROPOSED) |
| Connectors | KB site and REST API docs via the offline scraper only; SharePoint and videos via a local folder |
| Support-portal / ticket integration | **Not built** |
| SSO, tenants, row-level security | **Not built** (loopback, single operator, no accounts) |
| Client-facing channel | **Not built** |
| In-app diagnostics endpoint | **Not built** |
| ReadMe.io publishing | **Not built** (decided target; connector "for later design") |
| Privacy classification / redaction before external calls | **Not built** (the schema reviews make it a production blocker) |

The narrative's recommended first vertical slice: one product, a controlled subset of Confluence
articles, resolved tickets and training media; ingest through the shared contract; extract, classify,
sanitise and index with provenance; an internal authorised search/conversation endpoint with citations;
demonstrate a conflict and a correct escalation; demonstrate a permissioned withdrawal; produce one
draft article with an approved screenshot through human review and a publication test; capture traces,
evaluation results, cost and throughput at every step.
