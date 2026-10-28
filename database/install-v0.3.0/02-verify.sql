-- Read-only: one result grid with 12 summary checks followed by 29 table checks.
WITH checks(sort_order,check_name,expected,actual) AS (VALUES
 (1,'Target database','knowledge_poc',current_database()),
 (2,'PostgreSQL 17 or newer','true',(current_setting('server_version_num')::integer>=170000)::text),
 (3,'Vector enabled','true',EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')::text),
 (4,'Project schemas','3',(SELECT count(*) FROM pg_namespace WHERE nspname IN ('knowledge','analysis','retrieval'))::text),
 (5,'Base tables','29',(SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.relkind='r')::text),
 (6,'Table columns','301',(SELECT count(*) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped)::text),
 (7,'Primary keys','29',(SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.contype='p')::text),
 (8,'Foreign keys','55',(SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.contype='f')::text),
 (9,'Views','2',(SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.relkind='v')::text),
 (10,'Functions','4',(SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('knowledge','analysis','retrieval') AND p.prokind='f')::text),
 (11,'User triggers','5',(SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('knowledge','analysis','retrieval') AND NOT t.tgisinternal)::text),
 (12,'Drive-root configuration rows','2',(SELECT count(*) FROM knowledge.source_groups)::text)
), expected_tables(schema_name,table_name,expected_columns) AS (VALUES
 ('knowledge','sources',10),
 ('knowledge','source_versions',16),
 ('knowledge','extractions',10),
 ('knowledge','content_units',21),
 ('knowledge','source_links',7),
 ('analysis','runs',11),
 ('analysis','run_sources',6),
 ('analysis','agent_outputs',11),
 ('analysis','records',16),
 ('analysis','record_evidence',5),
 ('retrieval','embedding_profiles',8),
 ('retrieval','content_embeddings',6),
 ('retrieval','analysis_embeddings',6),
 ('knowledge','source_groups',8),
 ('knowledge','storage_objects',15),
 ('knowledge','object_versions',14),
 ('knowledge','version_representations',4),
 ('knowledge','ingestion_jobs',10),
 ('knowledge','unit_links',4),
 ('analysis','stages',9),
 ('analysis','record_links',3),
 ('analysis','human_reviews',8),
 ('knowledge','intake_batches',8),
 ('knowledge','intake_entries',13),
 ('knowledge','artifacts',15),
 ('knowledge','media_tracks',15),
 ('knowledge','api_operations',12),
 ('knowledge','api_examples',16),
 ('knowledge','api_parameters',14)
), actual_tables AS (
 SELECT n.nspname AS schema_name,c.relname AS table_name,count(a.attnum) AS actual_columns
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
 WHERE n.nspname IN ('knowledge','analysis','retrieval') AND c.relkind='r'
 GROUP BY n.nspname,c.relname
), results AS (
 SELECT 0 AS section,sort_order,check_name,expected,actual FROM checks
 UNION ALL
 SELECT 1,row_number() OVER (ORDER BY e.schema_name,e.table_name)::integer,
 e.schema_name||'.'||e.table_name||' fields',e.expected_columns::text,
 coalesce(a.actual_columns,0)::text
 FROM expected_tables e LEFT JOIN actual_tables a USING(schema_name,table_name)
)
SELECT check_name,expected,actual,CASE WHEN actual=expected THEN 'PASS' ELSE 'FAIL' END AS result
FROM results ORDER BY section,sort_order;
