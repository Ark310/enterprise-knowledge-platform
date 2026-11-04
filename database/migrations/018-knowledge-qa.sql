-- Additive only. No imported sources, vectors or gap-analysis contracts are changed.
CREATE SCHEMA IF NOT EXISTS knowledge_qa;
CREATE TABLE IF NOT EXISTS knowledge_qa.sessions (
 id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS knowledge_qa.turns (
 id uuid PRIMARY KEY, session_id uuid NOT NULL REFERENCES knowledge_qa.sessions(id),
 question text NOT NULL CHECK(length(question)>0), normalization jsonb,
 status text NOT NULL CHECK(status IN ('PROCESSING','VERIFIED','INSUFFICIENT_EVIDENCE','CLARIFY','FAILED','CANCELLED')),
 retrieval jsonb, answer jsonb, verification jsonb, completion_note text,
 created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz,
 CHECK(status <> 'VERIFIED' OR (answer IS NOT NULL AND verification IS NOT NULL AND coalesce(verification->>'decision'='PASS',false)))
);
CREATE TABLE IF NOT EXISTS knowledge_qa.evidence (
 turn_id uuid NOT NULL REFERENCES knowledge_qa.turns(id), evidence_key text NOT NULL,
 content_unit_id uuid REFERENCES knowledge.content_units(id),
 source_version_id uuid REFERENCES knowledge.source_versions(id),
 record_id uuid REFERENCES analysis.records(id), snapshot jsonb NOT NULL,
 PRIMARY KEY(turn_id,evidence_key),
 CHECK((content_unit_id IS NOT NULL AND source_version_id IS NOT NULL AND record_id IS NULL)
 OR (content_unit_id IS NULL AND source_version_id IS NULL AND record_id IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS knowledge_qa.events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 turn_id uuid NOT NULL REFERENCES knowledge_qa.turns(id), stage text NOT NULL
 CHECK(stage IN ('NORMALIZATION','DRAFT','VERIFICATION','VALIDATION','FAILURE')),
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS qa_turns_session_time ON knowledge_qa.turns(session_id,created_at);
CREATE INDEX IF NOT EXISTS qa_events_turn ON knowledge_qa.events(turn_id,id);
CREATE INDEX IF NOT EXISTS qa_evidence_unit ON knowledge_qa.evidence(content_unit_id);
COMMENT ON SCHEMA knowledge_qa IS 'POC chat audit. Model verification is not SME approval. Never a trusted embedding corpus.';
