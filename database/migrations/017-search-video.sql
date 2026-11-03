-- Additive POC upgrade. Legacy cue IDs, vectors, active extractions and runs are retained.
-- HNSW indexes are built separately after validating the actual embedding profile.
CREATE TABLE IF NOT EXISTS knowledge.poc_video_frames (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 source_version_id uuid NOT NULL REFERENCES knowledge.source_versions(id),
 extractor_key text NOT NULL, frame_seconds numeric NOT NULL CHECK(frame_seconds>=0),
 storage_uri text NOT NULL, image_sha256 text NOT NULL CHECK(length(image_sha256)=64),
 metadata jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source_version_id,extractor_key,frame_seconds,image_sha256)
);
CREATE TABLE IF NOT EXISTS analysis.poc_frame_evidence (
 record_id uuid NOT NULL REFERENCES analysis.records(id),
 frame_id uuid NOT NULL REFERENCES knowledge.poc_video_frames(id),
 relationship text NOT NULL DEFAULT 'SUPPORTS' CHECK(relationship IN ('SUPPORTS','CONTRADICTS')),
 PRIMARY KEY(record_id,frame_id)
);
CREATE INDEX IF NOT EXISTS poc_frame_source_time ON knowledge.poc_video_frames(source_version_id,frame_seconds);
CREATE INDEX IF NOT EXISTS poc_grouped_extractions ON knowledge.extractions(source_version_id,processor_version,config_sha256);
