KNOWLEDGE_POC DATABASE INSTALLATION - APPROVED SCHEMA v0.3.0

TARGET
Database: knowledge_poc
pgAdmin display name: POC - Local PostgreSQL (your chosen display name is fine)
Observed setup: PostgreSQL 17.11; pgvector 0.8.7 enabled in knowledge_poc.

SCREENSHOT REVIEW
1. The earlier installed_version=NULL result was in the separate postgres
   database. That does not indicate an error in knowledge_poc.
2. CREATE EXTENSION completed successfully in knowledge_poc.
3. The extension query returned knowledge_poc / vector / 0.8.7.
4. The vector cast returned [1,2,3]. No error is visible in these checks.

WHAT THIS PACKAGE CREATES
Three application schemas: knowledge, analysis and retrieval.
29 tables: knowledge 18, analysis 8, retrieval 3.
301 table fields, 29 primary keys, 55 foreign-key constraints.
21 explicitly named supporting indexes, plus constraint-created indexes.
2 retrieval views, 4 functions and 5 user triggers.
2 configuration rows for the previously approved Drive roots.

It does not load source assets, generate embeddings, call an AI model, run an
agent, change Windows services, delete existing databases or ingest Drive data.
The approved table/field structure is unchanged; the installation wrapper now
targets your actual database name and adds guards and verification.

STEP 1 - DOWNLOAD AND EXTRACT
Download the installation ZIP onto the computer where pgAdmin is running.
Right-click it and choose Extract All. Keep the extracted SQL files together.

STEP 2 - OPEN THE CORRECT QUERY TOOL
In pgAdmin expand:
Servers > POC - Local PostgreSQL > Databases
Right-click knowledge_poc and choose Query Tool.
The tab/connection should show knowledge_poc/postgres@POC - Local PostgreSQL.
Do not use the Query Tool tab connected to the default postgres database.

STEP 3 - RUN THE READ-ONLY PREFLIGHT
In Query Tool click the open-folder icon (or Ctrl+O).
Open 00-preflight.sql from the extracted package.
Click in the SQL editor, press Ctrl+A to select the entire file, then press F5.
Expected: one row showing knowledge_poc, your PostgreSQL version, vector 0.8.7,
vector_schema public, and existing_project_schemas none.
If an application schema is already listed, do not reinstall. Inspect it first;
if a prior installation exists, run 02-verify.sql to assess that installation.

STEP 4 - CREATE THE TABLES AND RELATIONSHIPS
In the SAME knowledge_poc Query Tool, open 01-install.sql.
Click in the SQL editor, press Ctrl+A, then F5. Run the entire file, including
its BEGIN, preflight guard, structure checks and COMMIT.
Expected final result:
database_name = knowledge_poc
result = SCHEMA INSTALLATION COMMITTED
next_step = Run 02-verify.sql next

A NOTICE that vector already exists and is being skipped is normal.
The installer refuses the wrong database, a missing vector extension, or an
existing project schema. It does not use DROP TABLE or DROP SCHEMA.
Do not rerun it after a successful installation; use the verification file.

IF AN ERROR OCCURS
Stop and retain the FIRST error message. Do not run remaining fragments.
In that Query Tool run:
ROLLBACK;
Then send the first error text. The installer uses a transaction, so a failed
installation does not commit a partial set of project tables.

STEP 5 - VERIFY WHAT WAS CREATED
Open 02-verify.sql in the knowledge_poc Query Tool.
Click in the SQL editor, press Ctrl+A and then F5.
The file returns one grid with 41 rows: twelve overall checks followed by
twenty-nine individual table checks. Every result should be PASS.
The checks do not mutate data.

STEP 6 - RUN THE ROLLBACK-ONLY INTEGRITY TEST
Open 03-smoke-test.sql. Select the ENTIRE file with Ctrl+A, then F5.
Do not run fragments or omit the final ROLLBACK.
The script creates clearly synthetic fixtures, tests 14 integrity conditions,
then discards all fixtures. It does not call an embedding model or read Drive.
In Messages, expect:
PASS: all 14 schema smoke checks completed.
The final ROLLBACK is intentional success cleanup, not an installation failure.
Even the synthetic human-review fixture is removed; it is not a real approval.
If the test errors, run ROLLBACK and send the first error.

STEP 7 - REFRESH THE OBJECT EXPLORER
Right-click knowledge_poc and choose Refresh.
Expand Schemas. You should see analysis, knowledge and retrieval in addition
to public. Their Tables folders contain 8, 18 and 3 tables respectively.
The two retrieval views appear under retrieval > Views.
Foreign keys appear under each relevant table > Constraints.

CHECKPOINT
Send the twelve overall verification checks and the smoke-test PASS message.
Successful Windows checks confirm that the database structure is installed.
The next stage is the manually triggered ingestion application, embedding
model configuration and agent integration. Database installation alone does
not connect ChatGPT or Google Drive to the Windows server.

TEST EVIDENCE
validation-results.json records isolated embedded PostgreSQL/WASM execution:
- PostgreSQL 17.5 with vector 0.8.0.
- PostgreSQL 18.6 with vector 0.8.7.
Both executed the complete installer, exact field/FK manifest checks, all
41 read-only summary/table checks, and 14 smoke checks. Wrong-database,
missing-vector and repeat-install guards also passed. Test fixtures were
confirmed absent after rollback. These tests did NOT run on your Windows
17.11 server; steps 3-6 provide that environment's final verification.

schema-manifest.json is an audit reference, not another file to execute.
