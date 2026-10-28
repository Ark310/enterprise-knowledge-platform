-- Apply only to installed approved v0.3 schema in knowledge_poc. No data/table drops.
-- Transaction owned by caller (Initialize-Database.cmd).
DO $td$
DECLARE c record;
BEGIN
 IF current_database()<>'knowledge_poc' THEN RAISE EXCEPTION 'Expected knowledge_poc'; END IF;
 IF to_regclass('knowledge.storage_objects') IS NULL THEN RAISE EXCEPTION 'Install approved schema v0.3 first'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='td_local_file_shape_v010' AND conrelid='knowledge.storage_objects'::regclass) THEN
  -- Replace only the old kind enumeration and kind-dependent shape checks.
  FOR c IN SELECT conname FROM pg_constraint WHERE conrelid='knowledge.storage_objects'::regclass AND contype='c'
   AND pg_get_constraintdef(oid) LIKE '%object_kind%' LOOP
   EXECUTE format('ALTER TABLE knowledge.storage_objects DROP CONSTRAINT %I',c.conname);
  END LOOP;
  ALTER TABLE knowledge.storage_objects ADD CONSTRAINT td_object_kind_v010 CHECK(object_kind IN('DRIVE_FILE','ARCHIVE_MEMBER','LOCAL_FILE'));
  ALTER TABLE knowledge.storage_objects ADD CONSTRAINT td_local_file_shape_v010 CHECK(
   (object_kind='DRIVE_FILE' AND drive_file_id IS NOT NULL AND parent_object_id IS NULL AND member_path IS NULL)
   OR(object_kind='ARCHIVE_MEMBER' AND drive_file_id IS NULL AND parent_object_id IS NOT NULL AND member_path IS NOT NULL)
   OR(object_kind='LOCAL_FILE' AND drive_file_id IS NULL AND parent_object_id IS NULL AND member_path IS NULL));
 END IF;
END $td$;
