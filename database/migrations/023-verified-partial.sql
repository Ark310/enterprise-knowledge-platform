-- Preserve rows and source vectors. Full and partial approvals remain distinct in JSON.
ALTER TABLE knowledge_qa.turns DROP CONSTRAINT IF EXISTS turns_check;
ALTER TABLE knowledge_qa.turns DROP CONSTRAINT IF EXISTS qa_turns_publication_v023;
ALTER TABLE knowledge_qa.turns ADD CONSTRAINT qa_turns_publication_v023 CHECK (
 status <> 'VERIFIED' OR (
 answer IS NOT NULL AND verification IS NOT NULL AND coalesce(
 (verification->>'decision'='PASS' AND answer->>'status'='ANSWER') OR
 (verification->>'decision'='PARTIAL_PASS' AND answer->>'status'='PARTIAL'
 AND verification->>'requested_scope_complete'='false'
 AND jsonb_typeof(answer->'unresolved')='array' AND jsonb_array_length(answer->'unresolved')>0
 AND jsonb_typeof(answer->'claims')='array' AND jsonb_array_length(answer->'claims')>0
 AND jsonb_typeof(answer->'procedure_complete')='boolean'), false)
 ));
