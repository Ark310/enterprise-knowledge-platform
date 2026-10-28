-- Read-only. Expected: knowledge_poc, PostgreSQL 17.11, vector 0.8.7/public, no project schemas.
SELECT current_database() AS database_name,current_user AS connected_user,version() AS server_version,
 current_setting('server_encoding') AS database_encoding,
 (SELECT e.extversion FROM pg_extension e WHERE e.extname='vector') AS vector_version,
 (SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector') AS vector_schema,
 coalesce((SELECT string_agg(nspname,', ' ORDER BY nspname) FROM pg_namespace
 WHERE nspname IN ('knowledge','analysis','retrieval')),'none') AS existing_project_schemas;
