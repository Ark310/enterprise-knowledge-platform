CREATE SCHEMA IF NOT EXISTS workspace_ui;
CREATE TABLE IF NOT EXISTS workspace_ui.chats (
 id uuid PRIMARY KEY,poc smallint NOT NULL CHECK(poc IN(1,2)),title text NOT NULL,
 context jsonb NOT NULL DEFAULT '{}'::jsonb,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workspace_ui.messages (
 id uuid PRIMARY KEY,chat_id uuid NOT NULL REFERENCES workspace_ui.chats(id),seq bigint GENERATED ALWAYS AS IDENTITY,
 role text NOT NULL CHECK(role IN('user','assistant','system')),body text NOT NULL,payload jsonb NOT NULL DEFAULT '{}'::jsonb,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS workspace_messages_chat ON workspace_ui.messages(chat_id,seq);
CREATE TABLE IF NOT EXISTS workspace_ui.assets (
 id uuid PRIMARY KEY,chat_id uuid NOT NULL REFERENCES workspace_ui.chats(id),kind text NOT NULL CHECK(kind IN('USER_UPLOAD','SOURCE','SOURCE_IMAGE','FRAME')),
 label text NOT NULL,path text NOT NULL,sha256 text NOT NULL,mime text NOT NULL,metadata jsonb NOT NULL DEFAULT '{}'::jsonb,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS workspace_assets_chat ON workspace_ui.assets(chat_id);
CREATE TABLE IF NOT EXISTS workspace_ui.engine_lock (id smallint PRIMARY KEY CHECK(id=1),owner uuid NOT NULL,expires_at timestamptz NOT NULL);
COMMENT ON SCHEMA workspace_ui IS 'Local browser chat audit and scoped assets. User uploads are never embedded or trusted shared knowledge.';
ALTER TABLE knowledge_qa.evidence ADD COLUMN IF NOT EXISTS workspace_asset_id uuid REFERENCES workspace_ui.assets(id);
ALTER TABLE knowledge_qa.evidence DROP CONSTRAINT IF EXISTS qa_evidence_shape_v020;
ALTER TABLE knowledge_qa.evidence DROP CONSTRAINT IF EXISTS qa_evidence_shape_v024;
ALTER TABLE knowledge_qa.evidence ADD CONSTRAINT qa_evidence_shape_v024 CHECK (
 (content_unit_id IS NOT NULL AND source_version_id IS NOT NULL AND record_id IS NULL AND frame_id IS NULL AND workspace_asset_id IS NULL)
 OR(content_unit_id IS NULL AND source_version_id IS NULL AND record_id IS NOT NULL AND frame_id IS NULL AND workspace_asset_id IS NULL)
 OR(content_unit_id IS NULL AND source_version_id IS NOT NULL AND record_id IS NULL AND frame_id IS NOT NULL AND workspace_asset_id IS NULL)
 OR(content_unit_id IS NULL AND record_id IS NULL AND frame_id IS NULL AND workspace_asset_id IS NOT NULL)
);
