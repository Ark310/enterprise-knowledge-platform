-- TD approved schema v0.3.0: fresh installation into knowledge_poc.
-- Run the ENTIRE file in pgAdmin Query Tool connected to knowledge_poc.
-- Existing vector extension is kept. Existing project schemas are never overwritten.
-- No original files, extracted content, vectors or agent findings are loaded here.
-- Only two approved Drive-root configuration rows are registered.
BEGIN;
DO $preflight$
DECLARE v_ext_schema text; v_existing text;
BEGIN
 IF current_database()<>'knowledge_poc' THEN
  RAISE EXCEPTION 'Wrong database: %. Open Query Tool on knowledge_poc and run the complete file there.',current_database();
 END IF;
 IF current_setting('server_version_num')::integer < 170000 THEN
  RAISE EXCEPTION 'This installer expects PostgreSQL 17 or newer. Detected: %',version();
 END IF;
 SELECT n.nspname INTO v_ext_schema FROM pg_extension e
 JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector';
 IF v_ext_schema IS NULL THEN
  RAISE EXCEPTION 'pgvector is not enabled in knowledge_poc. Enable it before installing the schema.';
 END IF;
 IF v_ext_schema<>'public' THEN
  RAISE EXCEPTION 'pgvector is in schema %, rather than public. Stop and adapt the installer search path before proceeding.',v_ext_schema;
 END IF;
 SELECT string_agg(nspname,', ' ORDER BY nspname) INTO v_existing
 FROM pg_namespace WHERE nspname IN ('knowledge','analysis','retrieval');
 IF v_existing IS NOT NULL THEN
  RAISE EXCEPTION 'Project schema(s) already exist: %. Nothing is overwritten. Run 02-verify.sql and inspect the existing installation.',v_existing;
 END IF;
END
$preflight$;
SET LOCAL search_path=pg_catalog,public;


CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA knowledge;
CREATE SCHEMA analysis;
CREATE SCHEMA retrieval;
CREATE TABLE knowledge.sources (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_system text NOT NULL,
 external_key text NOT NULL, source_type text NOT NULL CHECK(source_type IN
 ('ARTICLE','RELEASE_NOTE','RECORDING','TRANSCRIPT','SCREENSHOT','WORKBOOK','SAMPLE_DATA','API_SPEC','API_COLLECTION','PDF','WORD_DOCUMENT','OTHER')),
 title text NOT NULL, product text NOT NULL DEFAULT 'TD', module text,
 source_url text, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source_system,external_key)
);
CREATE TABLE knowledge.source_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_id uuid NOT NULL REFERENCES knowledge.sources,
 revision_key text NOT NULL, evidence_role text NOT NULL CHECK(evidence_role IN('CURRENT_STATE','EXISTING_ASSET')),
 storage_uri text NOT NULL, object_version_id text, mime_type text NOT NULL,
 byte_size bigint CHECK(byte_size>=0), content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
 external_revision text, source_modified_at timestamptz, ingested_at timestamptz NOT NULL DEFAULT now(),
 lifecycle_status text NOT NULL DEFAULT 'ACTIVE' CHECK(lifecycle_status IN('ACTIVE','SUPERSEDED','DELETED')),
 metadata jsonb NOT NULL DEFAULT '{}' CHECK(jsonb_typeof(metadata)='object'),
 UNIQUE(source_id,revision_key)
);
-- Originals remain at storage_uri (private S3 or approved local storage), not in vectors.
CREATE TABLE knowledge.extractions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_version_id uuid NOT NULL REFERENCES knowledge.source_versions,
 method text NOT NULL, processor_version text NOT NULL,
 status text NOT NULL CHECK(status IN('PENDING','PROCESSING','COMPLETE','PARTIAL','FAILED')),
 warnings jsonb NOT NULL DEFAULT '[]', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE knowledge.content_units (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), extraction_id uuid NOT NULL REFERENCES knowledge.extractions,
 parent_unit_id uuid REFERENCES knowledge.content_units, unit_key text NOT NULL,
 unit_type text NOT NULL, heading text, content_text text NOT NULL,
 representation_kind text NOT NULL CHECK(representation_kind IN
 ('SOURCE_TEXT','SUPPLIED_TRANSCRIPT','GENERATED_TRANSCRIPT','OCR','GENERATED_DESCRIPTION')),
 locator jsonb NOT NULL CHECK(jsonb_typeof(locator)='object'),
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
 metadata jsonb NOT NULL DEFAULT '{}',
 search_text tsvector GENERATED ALWAYS AS
 (to_tsvector('simple'::regconfig,coalesce(heading,'') || ' ' || content_text)) STORED,
 UNIQUE(extraction_id,unit_key)
);
CREATE INDEX content_units_text_idx ON knowledge.content_units USING gin(search_text);
CREATE TABLE knowledge.source_links (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), from_version_id uuid NOT NULL REFERENCES knowledge.source_versions,
 to_source_id uuid REFERENCES knowledge.sources, target_uri text NOT NULL, relationship text NOT NULL,
 resolution_status text NOT NULL CHECK(resolution_status IN('RESOLVED','UNRESOLVED','UNAVAILABLE')),
 CHECK(resolution_status<>'RESOLVED' OR to_source_id IS NOT NULL),
 UNIQUE(from_version_id,target_uri,relationship)
);
CREATE TABLE analysis.runs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_key text UNIQUE NOT NULL,
 module text NOT NULL, topic text NOT NULL, question text NOT NULL,
 contract_version text NOT NULL, agent_a_version text NOT NULL, agent_b_version text NOT NULL,
 status text NOT NULL CHECK(status IN('PENDING','PROCESSING','COMPLETE','PARTIAL','FAILED')),
 created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE analysis.run_sources (
 run_id uuid NOT NULL REFERENCES analysis.runs, source_version_id uuid NOT NULL REFERENCES knowledge.source_versions,
 coverage_status text NOT NULL CHECK(coverage_status IN('LISTED','SEARCHED','REVIEWED','PARTIAL','UNREADABLE')),
 coverage_details jsonb NOT NULL DEFAULT '{}', PRIMARY KEY(run_id,source_version_id)
);
CREATE TABLE analysis.agent_outputs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL REFERENCES analysis.runs,
 agent_role text NOT NULL CHECK(agent_role IN('CURRENT_STATE','ARTICLE_REVIEW')),
 output_json jsonb NOT NULL CHECK(jsonb_typeof(output_json)='object'),
 schema_validated boolean NOT NULL DEFAULT false, validation_details jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(id,run_id)
);
CREATE TABLE analysis.records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL REFERENCES analysis.runs,
 agent_output_id uuid NOT NULL, record_key text NOT NULL,
 record_type text NOT NULL CHECK(record_type IN('OBSERVATION','ARTICLE_ASSESSMENT','FINDING')),
 subject_version_id uuid REFERENCES knowledge.source_versions, topic text NOT NULL, statement text NOT NULL,
 evidence_level text, currency_status text CHECK(currency_status IN
 ('MATCHES_RECORDED_SCOPE','UPDATE_REQUIRED','CONFLICTED','UNVERIFIED')),
 quality_status text CHECK(quality_status IN('ACCEPTABLE','IMPROVEMENT_NEEDED','INDETERMINATE')),
 finding_type text, review_status text NOT NULL DEFAULT 'AGENT_PROPOSED'
 CHECK(review_status IN('AGENT_PROPOSED','CONFIRMED','REJECTED','NEEDS_EVIDENCE')),
 supersedes_record_id uuid REFERENCES analysis.records, details jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(run_id,record_key),
 FOREIGN KEY(agent_output_id,run_id) REFERENCES analysis.agent_outputs(id,run_id)
);
CREATE TABLE analysis.record_evidence (
 record_id uuid NOT NULL REFERENCES analysis.records, content_unit_id uuid NOT NULL REFERENCES knowledge.content_units,
 relationship text NOT NULL CHECK(relationship IN('SUPPORTS','CONTRADICTS','CONTEXT')),
 locator jsonb NOT NULL, excerpt text NOT NULL,
 PRIMARY KEY(record_id,content_unit_id,relationship)
);
CREATE TABLE retrieval.embedding_profiles (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), profile_key text UNIQUE NOT NULL,
 provider text NOT NULL, model text NOT NULL, model_revision text NOT NULL,
 dimensions integer NOT NULL CHECK(dimensions>0),
 distance_metric text NOT NULL CHECK(distance_metric IN('COSINE','L2','INNER_PRODUCT')),
 preprocessing_version text NOT NULL
);
-- Dimension-free storage allows deciding the model later. Always query ONE profile.
-- Add fixed-dimension expression/partial ANN indexes only after model selection.
CREATE TABLE retrieval.content_embeddings (
 content_unit_id uuid NOT NULL REFERENCES knowledge.content_units,
 profile_id uuid NOT NULL REFERENCES retrieval.embedding_profiles,
 input_sha256 text NOT NULL CHECK(input_sha256 ~ '^[0-9a-f]{64}$'),
 embedding vector NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(content_unit_id,profile_id)
);
CREATE TABLE retrieval.analysis_embeddings (
 record_id uuid NOT NULL REFERENCES analysis.records,
 profile_id uuid NOT NULL REFERENCES retrieval.embedding_profiles,
 input_sha256 text NOT NULL CHECK(input_sha256 ~ '^[0-9a-f]{64}$'),
 embedding vector NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(record_id,profile_id)
);
CREATE FUNCTION retrieval.check_dimensions() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected integer;
BEGIN
 SELECT dimensions INTO STRICT expected FROM retrieval.embedding_profiles WHERE id=NEW.profile_id;
 IF vector_dims(NEW.embedding) <> expected THEN
  RAISE EXCEPTION 'Embedding dimension mismatch: expected %, got %', expected,vector_dims(NEW.embedding);
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER content_dimensions BEFORE INSERT OR UPDATE ON retrieval.content_embeddings
 FOR EACH ROW EXECUTE FUNCTION retrieval.check_dimensions();
CREATE TRIGGER analysis_dimensions BEFORE INSERT OR UPDATE ON retrieval.analysis_embeddings
 FOR EACH ROW EXECUTE FUNCTION retrieval.check_dimensions();
CREATE INDEX versions_source_idx ON knowledge.source_versions(source_id);
CREATE INDEX extractions_version_idx ON knowledge.extractions(source_version_id);
CREATE INDEX units_extraction_idx ON knowledge.content_units(extraction_id);
CREATE INDEX records_subject_idx ON analysis.records(subject_version_id);
CREATE INDEX records_run_idx ON analysis.records(run_id);
CREATE INDEX evidence_unit_idx ON analysis.record_evidence(content_unit_id);
CREATE INDEX run_sources_version_idx ON analysis.run_sources(source_version_id);
CREATE INDEX records_status_idx ON analysis.records(currency_status,review_status);
COMMENT ON SCHEMA knowledge IS 'TD local single-user POC schema 0.3.0. No production tenant/ACL policies yet.';
-- Included by 01-schema.sql before COMMIT. Do not run separately.
CREATE TABLE knowledge.source_groups (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), group_key text UNIQUE NOT NULL,
 evidence_role text NOT NULL CHECK(evidence_role IN ('CURRENT_STATE','EXISTING_ASSET')),
 drive_folder_id text UNIQUE NOT NULL, folder_url text NOT NULL,
 sync_cursor text, last_successful_scan_at timestamptz,
 metadata jsonb NOT NULL DEFAULT '{}'
);
-- Physical files are distinct from logical articles. ZIP members are objects too.
CREATE TABLE knowledge.storage_objects (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), group_id uuid NOT NULL REFERENCES knowledge.source_groups,
 object_key text NOT NULL, object_kind text NOT NULL CHECK(object_kind IN ('DRIVE_FILE','ARCHIVE_MEMBER')),
 drive_file_id text, parent_object_id uuid REFERENCES knowledge.storage_objects,
 member_path text, title text NOT NULL, mime_type text, original_url text,
 availability text NOT NULL DEFAULT 'AVAILABLE' CHECK(availability IN ('AVAILABLE','TRASHED','MISSING','INACCESSIBLE')),
 last_seen_at timestamptz NOT NULL DEFAULT now(), metadata jsonb NOT NULL DEFAULT '{}',
 UNIQUE(group_id,object_key), UNIQUE(id,group_id),
 CHECK((object_kind='DRIVE_FILE' AND drive_file_id IS NOT NULL AND parent_object_id IS NULL AND member_path IS NULL)
 OR (object_kind='ARCHIVE_MEMBER' AND drive_file_id IS NULL AND parent_object_id IS NOT NULL AND member_path IS NOT NULL)),
 CHECK(parent_object_id IS DISTINCT FROM id)
);
CREATE TABLE knowledge.object_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), object_id uuid NOT NULL REFERENCES knowledge.storage_objects,
 version_key text NOT NULL, provider_revision text, provider_modified_at timestamptz,
 byte_size bigint CHECK(byte_size>=0), sha256 text CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 parent_archive_version_id uuid REFERENCES knowledge.object_versions,
 archive_entry_index integer CHECK(archive_entry_index>=0), crc32 text,
 registered_at timestamptz NOT NULL DEFAULT now(), storage_uri text,
 read_status text NOT NULL DEFAULT 'REGISTERED' CHECK(read_status IN
 ('REGISTERED','READABLE','SIZE_BLOCKED','CORRUPT','ENCRYPTED','UNSUPPORTED','FAILED')),
 error_details jsonb NOT NULL DEFAULT '{}', UNIQUE(object_id,version_key),
 CHECK((parent_archive_version_id IS NULL)=(archive_entry_index IS NULL)),
 CHECK(parent_archive_version_id IS DISTINCT FROM id)
);
CREATE FUNCTION knowledge.check_archive_lineage() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE o record; parent_object uuid;
BEGIN
 SELECT * INTO STRICT o FROM knowledge.storage_objects WHERE id=NEW.object_id;
 IF o.object_kind='ARCHIVE_MEMBER' THEN
  SELECT object_id INTO STRICT parent_object FROM knowledge.object_versions WHERE id=NEW.parent_archive_version_id;
  IF parent_object<>o.parent_object_id THEN RAISE EXCEPTION 'ZIP member must reference its parent archive version'; END IF;
 ELSIF NEW.parent_archive_version_id IS NOT NULL THEN RAISE EXCEPTION 'Drive file cannot have parent archive version';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER archive_lineage BEFORE INSERT OR UPDATE ON knowledge.object_versions
 FOR EACH ROW EXECUTE FUNCTION knowledge.check_archive_lineage();
-- Physical exports may resolve to one logical article revision; retain both provenances.
CREATE TABLE knowledge.version_representations (
 source_version_id uuid NOT NULL REFERENCES knowledge.source_versions,
 object_version_id uuid NOT NULL REFERENCES knowledge.object_versions,
 representation_role text NOT NULL CHECK(representation_role IN ('PRIMARY','ALTERNATE_EXPORT','ATTACHMENT','TRANSCRIPT','SCREENSHOT')),
 PRIMARY KEY(source_version_id,object_version_id)
);
CREATE UNIQUE INDEX primary_representation_idx ON knowledge.version_representations(source_version_id)
 WHERE representation_role='PRIMARY';
CREATE TABLE knowledge.ingestion_jobs (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), object_version_id uuid NOT NULL REFERENCES knowledge.object_versions,
 operation text NOT NULL CHECK(operation IN ('ENUMERATE','EXTRACT','OCR','TRANSCRIBE','DESCRIBE','CHUNK','EMBED')),
 processor_version text NOT NULL, config_sha256 text NOT NULL CHECK(config_sha256 ~ '^[0-9a-f]{64}$'),
 attempt integer NOT NULL DEFAULT 1 CHECK(attempt>0),
 status text NOT NULL CHECK(status IN ('PENDING','PROCESSING','COMPLETE','PARTIAL','BLOCKED','FAILED')),
 started_at timestamptz, finished_at timestamptz, error_details jsonb NOT NULL DEFAULT '{}',
 UNIQUE(object_version_id,operation,processor_version,config_sha256,attempt)
);
CREATE TABLE knowledge.unit_links (
 from_unit_id uuid NOT NULL REFERENCES knowledge.content_units,
 to_unit_id uuid NOT NULL REFERENCES knowledge.content_units,
 relationship text NOT NULL CHECK(relationship IN ('ILLUSTRATES','TRANSCRIBES','DERIVED_FROM','NEXT','ATTACHMENT')),
 details jsonb NOT NULL DEFAULT '{}', PRIMARY KEY(from_unit_id,to_unit_id,relationship),
 CHECK(from_unit_id<>to_unit_id)
);
ALTER TABLE knowledge.sources ADD COLUMN external_namespace text NOT NULL DEFAULT 'td';
ALTER TABLE knowledge.sources DROP CONSTRAINT sources_source_system_external_key_key;
ALTER TABLE knowledge.sources ADD UNIQUE(source_system,external_namespace,external_key);
ALTER TABLE knowledge.source_versions ADD COLUMN applicability jsonb NOT NULL DEFAULT '{}';
ALTER TABLE knowledge.source_versions ADD COLUMN group_id uuid REFERENCES knowledge.source_groups;
-- Re-registration can precede downloading; a missing checksum is explicit, never fabricated.
ALTER TABLE knowledge.source_versions ALTER COLUMN content_sha256 DROP NOT NULL;
ALTER TABLE knowledge.extractions ADD COLUMN config_sha256 text CHECK(config_sha256 ~ '^[0-9a-f]{64}$');
ALTER TABLE knowledge.extractions ADD COLUMN is_active boolean NOT NULL DEFAULT false;
CREATE UNIQUE INDEX active_extraction_idx ON knowledge.extractions(source_version_id) WHERE is_active;
ALTER TABLE knowledge.extractions ADD CHECK(NOT is_active OR status IN ('COMPLETE','PARTIAL'));
ALTER TABLE knowledge.content_units ADD COLUMN artifact_uri text;
ALTER TABLE knowledge.content_units ADD COLUMN start_seconds numeric CHECK(start_seconds>=0);
ALTER TABLE knowledge.content_units ADD COLUMN end_seconds numeric;
ALTER TABLE knowledge.content_units ADD COLUMN page_number integer CHECK(page_number>0);
ALTER TABLE knowledge.content_units ADD COLUMN sheet_name text;
ALTER TABLE knowledge.content_units ADD COLUMN cell_range text;
ALTER TABLE knowledge.content_units ADD CHECK(end_seconds IS NULL OR (start_seconds IS NOT NULL AND end_seconds>=start_seconds));
ALTER TABLE knowledge.content_units ADD UNIQUE(id,extraction_id);
ALTER TABLE knowledge.content_units DROP CONSTRAINT content_units_parent_unit_id_fkey;
ALTER TABLE knowledge.content_units ADD FOREIGN KEY(parent_unit_id,extraction_id) REFERENCES knowledge.content_units(id,extraction_id);
ALTER TABLE knowledge.content_units ADD CHECK(parent_unit_id IS DISTINCT FROM id);
CREATE TABLE analysis.stages (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), run_id uuid NOT NULL REFERENCES analysis.runs,
 stage text NOT NULL CHECK(stage IN ('SOURCE_EMBED','AGENT_A','A_EMBED','AGENT_B','B_EMBED','RETRIEVAL_READY')),
 attempt integer NOT NULL DEFAULT 1 CHECK(attempt>0),
 status text NOT NULL CHECK(status IN ('PENDING','PROCESSING','COMPLETE','PARTIAL','FAILED','BLOCKED')),
 profile_id uuid REFERENCES retrieval.embedding_profiles, started_at timestamptz, completed_at timestamptz,
 details jsonb NOT NULL DEFAULT '{}', UNIQUE(run_id,stage,attempt)
);
CREATE TABLE analysis.record_links (
 from_record_id uuid NOT NULL REFERENCES analysis.records,
 to_record_id uuid NOT NULL REFERENCES analysis.records,
 relationship text NOT NULL CHECK(relationship IN ('ASSESSES','SUPPORTS','CONTRADICTS','SUPERSEDES')),
 PRIMARY KEY(from_record_id,to_record_id,relationship), CHECK(from_record_id<>to_record_id)
);
CREATE TABLE analysis.human_reviews (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), record_id uuid NOT NULL REFERENCES analysis.records,
 reviewer_identity text NOT NULL CHECK(length(trim(reviewer_identity))>0), reviewed_at timestamptz NOT NULL,
 decision text NOT NULL CHECK(decision IN ('CONFIRMED','REJECTED','NEEDS_EVIDENCE')),
 rationale text NOT NULL, evidence_uri text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE analysis.agent_outputs ADD COLUMN contract_schema_sha256 text CHECK(contract_schema_sha256 ~ '^[0-9a-f]{64}$');
ALTER TABLE analysis.agent_outputs ADD COLUMN validation_status text NOT NULL DEFAULT 'NOT_VALIDATED'
 CHECK(validation_status IN ('NOT_VALIDATED','VALID','INVALID'));
ALTER TABLE analysis.agent_outputs ADD COLUMN model_details jsonb NOT NULL DEFAULT '{}';
ALTER TABLE analysis.agent_outputs ADD COLUMN prompt_sha256 text CHECK(prompt_sha256 ~ '^[0-9a-f]{64}$');
ALTER TABLE analysis.agent_outputs ADD CHECK(schema_validated=(validation_status='VALID'));
ALTER TABLE analysis.run_sources ADD COLUMN search_terms jsonb NOT NULL DEFAULT '[]';
ALTER TABLE analysis.run_sources ADD COLUMN reviewed_scope jsonb NOT NULL DEFAULT '{}';
-- Agent proposals cannot be promoted through a bare status UPDATE.
CREATE FUNCTION analysis.require_human_review() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.review_status IN ('CONFIRMED','REJECTED') AND NOT EXISTS
 (SELECT 1 FROM analysis.human_reviews h WHERE h.record_id=NEW.id AND h.decision=NEW.review_status)
 THEN RAISE EXCEPTION 'Attributed human review is required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER attributed_review BEFORE INSERT OR UPDATE ON analysis.records
 FOR EACH ROW EXECUTE FUNCTION analysis.require_human_review();
-- Profiles are immutable: a model, dimensionality or preprocessing change creates a new profile.
CREATE FUNCTION retrieval.immutable_profile() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Embedding profiles are immutable; create a new profile'; END $$;
CREATE TRIGGER immutable_profile BEFORE UPDATE ON retrieval.embedding_profiles
 FOR EACH ROW EXECUTE FUNCTION retrieval.immutable_profile();
ALTER TABLE retrieval.embedding_profiles ADD CHECK(dimensions<=16000);
ALTER TABLE retrieval.content_embeddings ADD COLUMN embedded_text text NOT NULL DEFAULT '';
ALTER TABLE retrieval.analysis_embeddings ADD COLUMN embedded_text text NOT NULL DEFAULT '';
-- Default-free input storage forces callers to record exactly what was embedded.
ALTER TABLE retrieval.content_embeddings ALTER COLUMN embedded_text DROP DEFAULT;
ALTER TABLE retrieval.analysis_embeddings ALTER COLUMN embedded_text DROP DEFAULT;
ALTER TABLE retrieval.content_embeddings ADD CHECK(length(trim(embedded_text))>0);
ALTER TABLE retrieval.analysis_embeddings ADD CHECK(length(trim(embedded_text))>0);
CREATE VIEW retrieval.active_content AS
 SELECT u.*,v.source_id,v.evidence_role,v.group_id,v.storage_uri,v.applicability
 FROM knowledge.content_units u JOIN knowledge.extractions e ON e.id=u.extraction_id
 JOIN knowledge.source_versions v ON v.id=e.source_version_id
 WHERE e.is_active AND v.lifecycle_status='ACTIVE';
CREATE VIEW retrieval.validated_findings AS
 SELECT r.*,o.agent_role FROM analysis.records r JOIN analysis.agent_outputs o ON o.id=r.agent_output_id
 WHERE o.validation_status='VALID' AND r.review_status<>'REJECTED';
CREATE INDEX object_versions_parent_idx ON knowledge.object_versions(parent_archive_version_id);
CREATE INDEX representations_object_idx ON knowledge.version_representations(object_version_id);
CREATE INDEX record_links_target_idx ON analysis.record_links(to_record_id);
CREATE INDEX source_role_idx ON knowledge.source_versions(evidence_role,lifecycle_status);
CREATE INDEX jobs_status_idx ON knowledge.ingestion_jobs(status);
COMMENT ON TABLE analysis.stages IS 'Stage audit only. Application gates require explicit scope/embedding readiness; this table alone does not execute or enforce the agent pipeline.';
COMMENT ON TABLE knowledge.storage_objects IS 'Append-only identity and archive ancestry. Object moves/renames update display metadata only; member identity uses parent identity plus full normalized path.';

-- v0.3.0 additions derived from the complete supplied Drive-part inventory.
-- Included by 01-schema.sql; proposal for review, NOT an installed migration.
ALTER TABLE knowledge.sources ALTER COLUMN product DROP DEFAULT;
ALTER TABLE knowledge.sources ALTER COLUMN product DROP NOT NULL;
ALTER TABLE knowledge.sources DROP CONSTRAINT sources_source_type_check;
ALTER TABLE knowledge.sources ADD CHECK(source_type IN
 ('ARTICLE','RELEASE_NOTE','RECORDING','TRANSCRIPT','SCREENSHOT','WORKBOOK','SAMPLE_DATA',
  'DOCUMENT','API_REFERENCE','API_SECTION','API_SPEC','API_COLLECTION','CODE_SAMPLE','EDITABLE_CAPTURE','OTHER'));
ALTER TABLE knowledge.storage_objects ADD COLUMN detected_mime_type text;
ALTER TABLE knowledge.storage_objects ADD COLUMN format_details jsonb NOT NULL DEFAULT '{}';
ALTER TABLE knowledge.storage_objects ADD FOREIGN KEY(parent_object_id,group_id)
 REFERENCES knowledge.storage_objects(id,group_id);
ALTER TABLE knowledge.source_groups ADD UNIQUE(id,evidence_role);
ALTER TABLE knowledge.source_versions ALTER COLUMN group_id SET NOT NULL;
ALTER TABLE knowledge.source_versions ADD FOREIGN KEY(group_id,evidence_role)
 REFERENCES knowledge.source_groups(id,evidence_role);
ALTER TABLE knowledge.version_representations ADD COLUMN metadata jsonb NOT NULL DEFAULT '{}';
ALTER TABLE knowledge.source_versions ADD UNIQUE(id,source_id);
ALTER TABLE knowledge.source_links ADD COLUMN to_version_id uuid;
ALTER TABLE knowledge.source_links ADD FOREIGN KEY(to_version_id,to_source_id)
 REFERENCES knowledge.source_versions(id,source_id);
ALTER TABLE knowledge.ingestion_jobs DROP CONSTRAINT ingestion_jobs_operation_check;
ALTER TABLE knowledge.ingestion_jobs ADD CHECK(operation IN
 ('ENUMERATE','EXTRACT','CONVERT','RENDER','OCR','TRANSCRIBE','DESCRIBE','CHUNK','EMBED','VALIDATE'));

-- One batch represents a declared inventory/scope, not an assumption that all files were supplied.
CREATE TABLE knowledge.intake_batches (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), batch_key text UNIQUE NOT NULL,
 manifest_object_version_id uuid REFERENCES knowledge.object_versions,
 declared_scope jsonb NOT NULL DEFAULT '{}', discovered_at timestamptz NOT NULL DEFAULT now(),
 scan_status text NOT NULL CHECK(scan_status IN ('PENDING','PROCESSING','COMPLETE','PARTIAL','FAILED')),
 manifest_reconciliation text NOT NULL CHECK(manifest_reconciliation IN
 ('NOT_CHECKED','MATCHES_SUPPLIED_PARTS','MISMATCH','NO_MANIFEST')),
 notes jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE knowledge.intake_entries (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), batch_id uuid NOT NULL REFERENCES knowledge.intake_batches,
 group_id uuid NOT NULL REFERENCES knowledge.source_groups, entry_key text NOT NULL,
 container_name text, member_path text NOT NULL, expected_bytes bigint CHECK(expected_bytes>=0),
 expected_sha256 text CHECK(expected_sha256 ~ '^[0-9a-f]{64}$'),
 observed_object_version_id uuid REFERENCES knowledge.object_versions,
 presence_status text NOT NULL CHECK(presence_status IN ('PRESENT','EXCLUDED','MISSING','UNREADABLE')),
 review_status text NOT NULL CHECK(review_status IN
 ('INVENTORIED','STRUCTURE_CHECKED','SAMPLED','CONTENT_REVIEWED','NEEDS_CONVERSION','BLOCKED')),
 reason text, details jsonb NOT NULL DEFAULT '{}', UNIQUE(batch_id,entry_key),
 CHECK(presence_status<>'PRESENT' OR observed_object_version_id IS NOT NULL),
 CHECK(presence_status='PRESENT' OR reason IS NOT NULL)
);

-- Reproducible representations sit between original versions and retrieval chunks.
ALTER TABLE knowledge.extractions ADD UNIQUE(id,source_version_id);
CREATE TABLE knowledge.artifacts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_version_id uuid NOT NULL REFERENCES knowledge.source_versions,
 extraction_id uuid NOT NULL, origin_object_version_id uuid REFERENCES knowledge.object_versions,
 parent_artifact_id uuid, artifact_key text NOT NULL,
 artifact_kind text NOT NULL CHECK(artifact_kind IN
 ('EXTRACTED_TEXT','RENDERED_IMAGE','VIDEO_FRAME','TRANSCRIPT','STRUCTURED_DATA','CONVERTED_DOCUMENT','TRANSCODED_MEDIA')),
 mime_type text NOT NULL, storage_uri text, inline_data jsonb,
 sha256 text CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 status text NOT NULL CHECK(status IN ('PENDING','READY','EMPTY','BLOCKED','FAILED','UNAVAILABLE')),
 locator jsonb NOT NULL DEFAULT '{}', metadata jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(extraction_id,artifact_key), UNIQUE(id,source_version_id),
 FOREIGN KEY(extraction_id,source_version_id) REFERENCES knowledge.extractions(id,source_version_id),
 FOREIGN KEY(parent_artifact_id,source_version_id) REFERENCES knowledge.artifacts(id,source_version_id),
 CHECK(parent_artifact_id IS DISTINCT FROM id),
 CHECK(status<>'READY' OR (sha256 IS NOT NULL AND (storage_uri IS NOT NULL OR inline_data IS NOT NULL)))
);
ALTER TABLE knowledge.extractions ADD COLUMN input_artifact_id uuid;
ALTER TABLE knowledge.extractions ADD FOREIGN KEY(input_artifact_id,source_version_id)
 REFERENCES knowledge.artifacts(id,source_version_id);
ALTER TABLE knowledge.content_units ADD COLUMN artifact_id uuid REFERENCES knowledge.artifacts;
ALTER TABLE knowledge.content_units ADD COLUMN language text;
ALTER TABLE knowledge.content_units ADD COLUMN content_status text NOT NULL DEFAULT 'USABLE'
 CHECK(content_status IN ('USABLE','EMPTY','UNVERIFIED','REDACTED'));

CREATE TABLE knowledge.media_tracks (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_version_id uuid NOT NULL REFERENCES knowledge.source_versions,
 stream_index integer NOT NULL CHECK(stream_index>=0),
 track_type text NOT NULL CHECK(track_type IN ('VIDEO','AUDIO','SUBTITLE','DATA','OTHER')),
 codec text, duration_seconds numeric CHECK(duration_seconds>=0),
 width integer CHECK(width>0), height integer CHECK(height>0),
 sample_rate integer CHECK(sample_rate>0), channels integer CHECK(channels>0),
 frame_rate_numerator bigint, frame_rate_denominator bigint CHECK(frame_rate_denominator>0),
 language text, time_base text, metadata jsonb NOT NULL DEFAULT '{}',
 UNIQUE(source_version_id,stream_index)
);

-- Endpoint definitions are versioned documentary claims, not a live API registry.
CREATE TABLE knowledge.api_operations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), source_version_id uuid NOT NULL REFERENCES knowledge.source_versions,
 operation_key text NOT NULL, method_raw text NOT NULL, path_raw text NOT NULL,
 request_url_raw text, audience_label text, environment_label text,
 api_version_label text, source_locator jsonb NOT NULL,
 raw_definition jsonb NOT NULL, metadata jsonb NOT NULL DEFAULT '{}',
 UNIQUE(source_version_id,operation_key)
);
-- Do NOT add a global UNIQUE(method_raw,path_raw): 27 repeated pairs exist in the supplied export.
CREATE TABLE knowledge.api_examples (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), operation_id uuid NOT NULL REFERENCES knowledge.api_operations,
 example_key text NOT NULL,
 example_kind text NOT NULL CHECK(example_kind IN ('REQUEST','RESPONSE','CODE_SAMPLE','TRYIT_CAPTURE')),
 context text NOT NULL CHECK(context IN ('REFERENCE','TRYIT','OTHER')),
 language text, status_label_raw text, http_status integer CHECK(http_status BETWEEN 100 AND 599),
 content_type text, body_text text, structured_body jsonb,
 payload_status text NOT NULL CHECK(payload_status IN ('PRESENT','EMPTY','NOT_CAPTURED','UNREADABLE')),
 source_object_version_id uuid REFERENCES knowledge.object_versions,
 content_unit_id uuid REFERENCES knowledge.content_units, source_locator jsonb NOT NULL,
 metadata jsonb NOT NULL DEFAULT '{}', UNIQUE(operation_id,example_key), UNIQUE(id,operation_id),
 CHECK(example_kind='RESPONSE' OR (status_label_raw IS NULL AND http_status IS NULL))
);
CREATE TABLE knowledge.api_parameters (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), operation_id uuid NOT NULL REFERENCES knowledge.api_operations,
 response_example_id uuid, parent_parameter_id uuid, parameter_key text NOT NULL,
 location text NOT NULL CHECK(location IN ('HEADER','PATH','QUERY','BODY','RESPONSE')),
 name text NOT NULL, data_type_raw text, required_claim boolean, description text,
 example_value jsonb, ordinal integer NOT NULL CHECK(ordinal>=0),
 source_locator jsonb NOT NULL, raw_definition jsonb NOT NULL,
 UNIQUE(operation_id,parameter_key), UNIQUE(id,operation_id,location),
 FOREIGN KEY(parent_parameter_id,operation_id,location) REFERENCES knowledge.api_parameters(id,operation_id,location),
 FOREIGN KEY(response_example_id,operation_id) REFERENCES knowledge.api_examples(id,operation_id),
 CHECK(parent_parameter_id IS DISTINCT FROM id),
 CHECK(location<>'RESPONSE' OR response_example_id IS NOT NULL)
);
CREATE INDEX intake_entries_presence_idx ON knowledge.intake_entries(batch_id,presence_status,review_status);
CREATE INDEX artifacts_version_idx ON knowledge.artifacts(source_version_id,status);
CREATE INDEX api_operations_lookup_idx ON knowledge.api_operations(method_raw,path_raw);
CREATE INDEX api_parameters_operation_idx ON knowledge.api_parameters(operation_id,location);
CREATE INDEX api_examples_operation_idx ON knowledge.api_examples(operation_id,example_kind,context);
-- Prevent a caller from declaring one embedding input while storing another.
ALTER TABLE retrieval.content_embeddings ADD CHECK
 (input_sha256=encode(sha256(convert_to(embedded_text,'UTF8')),'hex'));
ALTER TABLE retrieval.analysis_embeddings ADD CHECK
 (input_sha256=encode(sha256(convert_to(embedded_text,'UTF8')),'hex'));
-- Empty subtitle/response content is inventoried, but not offered as usable evidence.
CREATE OR REPLACE VIEW retrieval.active_content AS
 SELECT u.id,u.extraction_id,u.parent_unit_id,u.unit_key,u.unit_type,u.heading,u.content_text,
 u.representation_kind,u.locator,u.content_sha256,u.metadata,u.search_text,
 u.artifact_uri,u.start_seconds,u.end_seconds,u.page_number,u.sheet_name,u.cell_range,
 v.source_id,v.evidence_role,v.group_id,v.storage_uri,v.applicability,
 u.artifact_id,u.language,u.content_status
 FROM knowledge.content_units u JOIN knowledge.extractions e ON e.id=u.extraction_id
 JOIN knowledge.source_versions v ON v.id=e.source_version_id
 LEFT JOIN knowledge.artifacts a ON a.id=u.artifact_id
 WHERE e.is_active AND v.lifecycle_status='ACTIVE' AND u.content_status='USABLE'
 AND (u.artifact_id IS NULL OR a.status='READY')
 AND u.content_text ~ '[^[:space:]]';
COMMENT ON TABLE knowledge.api_examples IS 'Captured documentation examples only. Try It capture never proves a request was executed successfully.';
COMMENT ON TABLE knowledge.intake_entries IS 'Accounts for declared exclusions without inventing ingested source records or evidence.';
COMMENT ON TABLE knowledge.artifacts IS 'Private derived representations; image render, OCR, subtitle and transcript provenance remain distinct.';


INSERT INTO knowledge.source_groups(group_key,evidence_role,drive_folder_id,folder_url)
VALUES
 ('current-state','CURRENT_STATE','YOUR_DRIVE_FOLDER_ID_1','https://drive.google.com/drive/folders/YOUR_DRIVE_FOLDER_ID_1'),
 ('existing-assets','EXISTING_ASSET','YOUR_DRIVE_FOLDER_ID_2','https://drive.google.com/drive/folders/YOUR_DRIVE_FOLDER_ID_2')
ON CONFLICT(group_key) DO NOTHING;
DO $verify_install$
DECLARE v_tables integer; v_columns integer; v_fk integer; v_views integer; v_triggers integer;
BEGIN
 SELECT count(*) INTO v_tables FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.relkind='r';
 SELECT count(*) INTO v_columns FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
 JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped;
 SELECT count(*) INTO v_fk FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
 WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.contype='f';
 SELECT count(*) INTO v_views FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.relkind='v';
 SELECT count(*) INTO v_triggers FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
 JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname IN ('knowledge','analysis','retrieval') AND NOT t.tgisinternal;
 IF v_tables<>29 OR v_columns<>301 OR v_fk<>55 OR v_views<>2 OR v_triggers<>5 THEN
  RAISE EXCEPTION 'Installation count mismatch: tables %, columns %, FKs %, views %, triggers %. Transaction will not be committed.',
   v_tables,v_columns,v_fk,v_views,v_triggers;
 END IF;
 IF (SELECT count(*) FROM knowledge.source_groups)<>2 THEN
  RAISE EXCEPTION 'Expected two Drive-root configuration rows.';
 END IF;
 RAISE NOTICE 'Structure checked: 29 tables, 301 fields, 55 foreign keys, 2 views, 5 triggers and 2 Drive roots.';
END
$verify_install$;

COMMIT;
SELECT current_database() AS database_name,
       'SCHEMA INSTALLATION COMMITTED'::text AS result,
       'Run 02-verify.sql next'::text AS next_step;
