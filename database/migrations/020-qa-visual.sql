-- Additive POC 2 audit extension; no source/vector rewrite or POC 1 changes.
ALTER TABLE knowledge_qa.evidence ADD COLUMN IF NOT EXISTS frame_id uuid REFERENCES knowledge.poc_video_frames(id);
ALTER TABLE knowledge_qa.evidence DROP CONSTRAINT IF EXISTS evidence_check;
ALTER TABLE knowledge_qa.evidence DROP CONSTRAINT IF EXISTS qa_evidence_shape_v020;
DO $upgrade$ BEGIN
IF NOT EXISTS(select 1 from information_schema.columns where table_schema='knowledge_qa' and table_name='evidence' and column_name='workspace_asset_id') THEN
ALTER TABLE knowledge_qa.evidence ADD CONSTRAINT qa_evidence_shape_v020 CHECK (
 (content_unit_id IS NOT NULL AND source_version_id IS NOT NULL AND record_id IS NULL AND frame_id IS NULL)
 OR (content_unit_id IS NULL AND source_version_id IS NULL AND record_id IS NOT NULL AND frame_id IS NULL)
 OR (content_unit_id IS NULL AND source_version_id IS NOT NULL AND record_id IS NULL AND frame_id IS NOT NULL)
);
END IF; END $upgrade$;
CREATE INDEX IF NOT EXISTS qa_evidence_frame ON knowledge_qa.evidence(frame_id);
