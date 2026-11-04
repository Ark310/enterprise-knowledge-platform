# v0.18 changes
- Launcher selects existing Gap Analysis or separate Knowledge Retrieval executable.
- Shared imported data, Qwen embedding profile and HNSW indexes retained.
- Knowledge Assistant normalizes intent, drafts source-backed answers and labels general reasoning/inferences.
- Independent Verifier checks original intent, premise, evidence, source scope and readability.
- Literal citation gate + per-claim verifier contract + one correction limit; withheld unverified drafts.
- Additive knowledge_qa audit schema; conversations never automatically become trusted embeddings.
- Individual role activity windows, five-minute per-call retrieval timeout, diagnostic export.
- Gap workflow and comparison modes remain available under option 1.
