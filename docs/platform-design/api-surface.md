# Proposed API surface (design only)

> **Not built.** The POCs expose no public API: the web workspace has a small loopback-only JSON API for
> its own front end, protected by a per-process CSRF token, and its CSP forbids embedding
> (`frame-ancestors 'none'`). The routes below are the *illustrative* service contract from the
> engineering narrative v1 (§16). Authentication method, JSON schemas, pagination, streaming, callbacks,
> limits and versioning are all marked "require detailed design".

## Routes

| Route | Purpose | Important contract fields | Sync / async |
|---|---|---|---|
| `POST /v1/search` | Authorised evidence retrieval | principal, tenant, product / version, query, citations | Sync |
| `POST /v1/conversations` | Conversation session (create / continue) | scope, message, conversation ID, references | Sync (streaming TBD) |
| `POST /v1/cases/analyze` | Support-ticket investigation | ticket ID, tenant, sanitised context, job ID | Async |
| `POST /v1/diagnostics/analyze` | In-application error guidance | error code, operation, release, safe context | Sync or async |
| `POST /v1/documentation/drafts` | Documentation planning and drafting | document type, audience, evidence, media manifest | Async |
| `GET /v1/jobs/{id}` | Status of a long-running job | workflow state, result references, errors | Sync |

## Response shape every route shares (design intent)

Every intelligence response is meant to separate **retrieved evidence** from **generated
interpretation** and to carry enough structure for the caller to render or act on it:

```jsonc
{
  "outcome": "ANSWER | PARTIAL | CLARIFY | INSUFFICIENT_EVIDENCE | ESCALATED",
  "answer": "…human-readable text…",
  "evidence": [
    { "id": "S3", "source": "kb:article/12345@rev7", "excerpt": "…verbatim…",
      "locator": { "start_seconds": 512.4, "end_seconds": 541.0 },
      "verification": "CORROBORATED" }
  ],
  "scope": { "tenant": "…", "product": "TradeDesk", "release": "…", "module": "…" },
  "uncertainty": ["Client-specific configuration was not inspected."],
  "trace_id": "…"
}
```

`ANSWER`, `PARTIAL`, `CLARIFY` and `INSUFFICIENT_EVIDENCE`, and the evidence / scope / uncertainty
split, are what POC 2 already produces internally (see `contracts/knowledge-qa.schema.json`).
`ESCALATED` (hand-off to an authorised team) and the evidence `verification` states are platform
additions from the design. The platform would expose all of this through the API instead of a local UI.

## How each route maps onto what the POCs already do

| Route | Closest POC behaviour today | What the platform must add |
|---|---|---|
| `/v1/search` | Worker search: halfvec HNSW candidates → full-vector rerank → keyword + English-stemmed title/topic lanes, product-family scoping, duplicate-body collapse | Identity, tenant and audience filters applied **before** similarity search; denormalised scope columns on embeddings; exact-search fallback for small eligible sets |
| `/v1/conversations` | POC 2: Normalizer → retrieval → Knowledge Assistant → independent Verifier → host validation → `knowledge_qa`; per-chat history in `workspace_ui` | Multi-user sessions, no cross-tenant memory, streaming |
| `/v1/cases/analyze` | none | Ticket connector, idempotent jobs, similar-case search over eligible resolved tickets |
| `/v1/diagnostics/analyze` | none | Error-code catalogue, runbook and release-note retrieval, sanitised context contract |
| `/v1/documentation/drafts` | POC 1 gap analysis produces cited, AGENT_PROPOSED gap rows | Planner, template registry, writer, quality reviewer, human approval, ReadMe.io adapter with media manifest |
| `/v1/jobs/{id}` | Host-side run folders, checkpoints and exports | Durable workflow state in the controller, completion events |

## Agent contract (applies behind every route)

From the narrative (§12.1) and the review package agent catalogue, every agent needs: identity,
version, purpose and owning team; typed input/output schemas and a permitted tool list; tenant /
audience context and evidence restrictions; prompt and model version; timeout, retry, cancellation and
checkpoint behaviour; confidence, citations and escalation criteria; trace correlation, usage and cost
metrics, and test fixtures. The POC already follows the core of this: each Codex role has a prompt in
`agents/*.md`, a JSON schema in `contracts/`, no tools, and host-side validation of its output.

## Orchestration

The proposed "Chief of Agents" is a **deterministic .NET workflow controller**, not an LLM. It owns
workflow definitions, durable state, step order, idempotency, retries, human-review waits, timeouts,
permissions and audit; specialist agents only make bounded judgements. Microsoft Agent Framework is a
candidate runtime, to be adopted only if a ~3-day proof of concept against plain .NET orchestration shows
a material benefit (restart, parallelism, tool calls, human pause/resume, telemetry, operational cost).
