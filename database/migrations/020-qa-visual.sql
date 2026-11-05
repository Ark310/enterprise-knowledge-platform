-- Additive POC 2 audit extension; no source/vector rewrite or POC 1 changes.
ALTER TABLE knowledge_qa.evidence ADD COLUMN IF NOT EXISTS frame_id uuid REFERENCES knowledge.poc_video_frames(id);
ALTER TABLE knowledge_qa.evidence DROP CONSTRAINT IF EXISTS evidence_check;
ALTER TABLE knowledge_qa.evidence DROP CONSTRAINT IF EXISTS qa_evidence_shape_v020;
ALTER TABLE knowledge_qa.evidence ADD CONSTRAINT qa_evidence_shape_v020 CHECK (
 (content_unit_id IS NOT NULL AND source_version_id IS NOT NULL AND record_id IS NULL AND frame_id IS NULL)
 OR (content_unit_id IS NULL AND source_version_id IS NULL AND record_id IS NOT NULL AND frame_id IS NULL)
 OR (content_unit_id IS NULL AND source_version_id IS NOT NULL AND record_id IS NULL AND frame_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS qa_evidence_frame ON knowledge_qa.evidence(frame_id);
