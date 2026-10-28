-- Run AFTER installation, in knowledge_poc. Uses synthetic fixtures only.
-- All fixtures are discarded by the final ROLLBACK, including fake review data.
BEGIN;
DO $smoke$
DECLARE
 g uuid; sid uuid; sv uuid; sv2 uuid; ex uuid; ex2 uuid; unit1 uuid;
 profile uuid; obj1 uuid; obj2 uuid; ov1 uuid; ov2 uuid; member uuid;
 rid uuid; output_id uuid; finding uuid; op1 uuid; op2 uuid; param1 uuid;
 token text:=gen_random_uuid()::text;
 input_text text:='Synthetic schema integrity fixture';
 input_hash text; accepted boolean; passed integer:=0;
BEGIN
 IF current_database()<>'knowledge_poc' THEN RAISE EXCEPTION 'Run in knowledge_poc only'; END IF;
 input_hash:=encode(sha256(convert_to(input_text,'UTF8')),'hex');
 SELECT id INTO STRICT g FROM knowledge.source_groups WHERE group_key='current-state';
 INSERT INTO knowledge.sources(source_system,external_namespace,external_key,source_type,title,product)
 VALUES('SCHEMA_TEST_ONLY','synthetic-fixture',token,'ARTICLE','Synthetic rollback-only test','TD') RETURNING id INTO sid;
 INSERT INTO knowledge.source_versions(source_id,revision_key,evidence_role,storage_uri,mime_type,group_id)
 VALUES(sid,'test-1','CURRENT_STATE','smoke://not-a-real-source','text/plain',g) RETURNING id INTO sv;
 INSERT INTO knowledge.source_versions(source_id,revision_key,evidence_role,storage_uri,mime_type,group_id)
 VALUES(sid,'test-2','CURRENT_STATE','smoke://not-a-real-source','text/plain',g) RETURNING id INTO sv2;

 accepted:=false;
 BEGIN
  INSERT INTO knowledge.source_versions(source_id,revision_key,evidence_role,storage_uri,mime_type,group_id)
  VALUES(sid,'wrong-role','EXISTING_ASSET','smoke://fixture','text/plain',g);
  accepted:=true;
 EXCEPTION WHEN foreign_key_violation THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: wrong group/evidence role accepted'; END IF;
 passed:=passed+1;

 INSERT INTO knowledge.extractions(source_version_id,method,processor_version,status,is_active)
 VALUES(sv,'SCHEMA_TEST','test','COMPLETE',true) RETURNING id INTO ex;
 INSERT INTO knowledge.extractions(source_version_id,method,processor_version,status,is_active)
 VALUES(sv2,'SCHEMA_TEST','test','COMPLETE',true) RETURNING id INTO ex2;
 accepted:=false;
 BEGIN
  INSERT INTO knowledge.extractions(source_version_id,method,processor_version,status,is_active)
  VALUES(sv,'SCHEMA_TEST','test','COMPLETE',true);accepted:=true;
 EXCEPTION WHEN unique_violation THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: two selected extractions accepted'; END IF;
 passed:=passed+1;

 INSERT INTO knowledge.content_units(extraction_id,unit_key,unit_type,content_text,representation_kind,locator,content_sha256)
 VALUES(ex,'unit-1','PARAGRAPH',input_text,'SOURCE_TEXT','{}',input_hash) RETURNING id INTO unit1;
 accepted:=false;
 BEGIN
  INSERT INTO knowledge.content_units(extraction_id,parent_unit_id,unit_key,unit_type,content_text,representation_kind,locator,content_sha256)
  VALUES(ex2,unit1,'cross-extraction','PARAGRAPH',input_text,'SOURCE_TEXT','{}',input_hash);accepted:=true;
 EXCEPTION WHEN foreign_key_violation THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: parent from another extraction accepted'; END IF;
 passed:=passed+1;

 INSERT INTO retrieval.embedding_profiles(profile_key,provider,model,model_revision,dimensions,distance_metric,preprocessing_version)
 VALUES('SCHEMA_TEST_'||token,'SYNTHETIC','SYNTHETIC','test',3,'COSINE','test') RETURNING id INTO profile;
 INSERT INTO retrieval.content_embeddings(content_unit_id,profile_id,input_sha256,embedding,embedded_text)
 VALUES(unit1,profile,input_hash,'[1,0,0]'::vector,input_text);
 passed:=passed+1;
 accepted:=false;
 BEGIN
  UPDATE retrieval.content_embeddings SET embedding='[1,0]'::vector WHERE content_unit_id=unit1 AND profile_id=profile;
  accepted:=true;
 EXCEPTION WHEN raise_exception THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: wrong vector dimension accepted'; END IF;
 passed:=passed+1;
 accepted:=false;
 BEGIN
  UPDATE retrieval.content_embeddings SET input_sha256=repeat('0',64) WHERE content_unit_id=unit1 AND profile_id=profile;
  accepted:=true;
 EXCEPTION WHEN check_violation THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: wrong embedded text hash accepted'; END IF;
 passed:=passed+1;
 accepted:=false;
 BEGIN
  UPDATE retrieval.embedding_profiles SET model='CHANGED' WHERE id=profile;accepted:=true;
 EXCEPTION WHEN raise_exception THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: embedding profile mutation accepted'; END IF;
 passed:=passed+1;

 INSERT INTO knowledge.storage_objects(group_id,object_key,object_kind,drive_file_id,title)
 VALUES(g,'TEST-ARCHIVE-1-'||token,'DRIVE_FILE','TEST-DRIVE-1-'||token,'synthetic.zip') RETURNING id INTO obj1;
 INSERT INTO knowledge.storage_objects(group_id,object_key,object_kind,drive_file_id,title)
 VALUES(g,'TEST-ARCHIVE-2-'||token,'DRIVE_FILE','TEST-DRIVE-2-'||token,'synthetic-2.zip') RETURNING id INTO obj2;
 INSERT INTO knowledge.object_versions(object_id,version_key) VALUES(obj1,'test') RETURNING id INTO ov1;
 INSERT INTO knowledge.object_versions(object_id,version_key) VALUES(obj2,'test') RETURNING id INTO ov2;
 INSERT INTO knowledge.storage_objects(group_id,object_key,object_kind,parent_object_id,member_path,title)
 VALUES(g,'TEST-MEMBER-'||token,'ARCHIVE_MEMBER',obj1,'fixture.txt','fixture.txt') RETURNING id INTO member;
 accepted:=false;
 BEGIN
  INSERT INTO knowledge.object_versions(object_id,version_key,parent_archive_version_id,archive_entry_index)
  VALUES(member,'wrong-parent',ov2,0);accepted:=true;
 EXCEPTION WHEN raise_exception THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: mismatched archive parent accepted'; END IF;
 passed:=passed+1;
 INSERT INTO knowledge.object_versions(object_id,version_key,parent_archive_version_id,archive_entry_index)
 VALUES(member,'correct-parent',ov1,0);
 passed:=passed+1;

 INSERT INTO analysis.runs(run_key,module,topic,question,contract_version,agent_a_version,agent_b_version,status)
 VALUES('SCHEMA_TEST_'||token,'SCHEMA_TEST','SCHEMA_TEST','Synthetic SQL constraint check only',
 'td-doc-review-2.0','2.1.0','2.1.0','COMPLETE') RETURNING id INTO rid;
 INSERT INTO analysis.agent_outputs(run_id,agent_role,output_json)
 VALUES(rid,'CURRENT_STATE','{"synthetic_sql_test_only":true}') RETURNING id INTO output_id;
 INSERT INTO analysis.records(run_id,agent_output_id,record_key,record_type,subject_version_id,topic,statement)
 VALUES(rid,output_id,'test-record','OBSERVATION',sv,'SCHEMA_TEST','Synthetic rollback-only record') RETURNING id INTO finding;
 IF EXISTS(SELECT 1 FROM retrieval.validated_findings WHERE id=finding) THEN
  RAISE EXCEPTION 'FAIL: unvalidated output exposed by validated_findings';
 END IF;
 passed:=passed+1;
 accepted:=false;
 BEGIN
  UPDATE analysis.records SET review_status='CONFIRMED' WHERE id=finding;accepted:=true;
 EXCEPTION WHEN raise_exception THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: confirmation without human-review row accepted'; END IF;
 passed:=passed+1;
 -- This is explicitly a fabricated TEST fixture, not an actual attributed approval.
 -- It exists only in this rollback-only transaction to test the database mechanism.
 INSERT INTO analysis.human_reviews(record_id,reviewer_identity,reviewed_at,decision,rationale,evidence_uri)
 VALUES(finding,'SCHEMA_TEST_FIXTURE_NOT_A_REAL_REVIEW',now(),'CONFIRMED','Synthetic rollback-only integrity check','smoke://synthetic-review');
 UPDATE analysis.records SET review_status='CONFIRMED' WHERE id=finding;
 passed:=passed+1;

 INSERT INTO knowledge.api_operations(source_version_id,operation_key,method_raw,path_raw,source_locator,raw_definition)
 VALUES(sv,'test-operation-1','GET','/synthetic','{}','{}') RETURNING id INTO op1;
 INSERT INTO knowledge.api_operations(source_version_id,operation_key,method_raw,path_raw,source_locator,raw_definition)
 VALUES(sv,'test-operation-2','GET','/synthetic','{}','{}') RETURNING id INTO op2;
 INSERT INTO knowledge.api_parameters(operation_id,parameter_key,location,name,ordinal,source_locator,raw_definition)
 VALUES(op1,'parent','BODY','parent',0,'{}','{}') RETURNING id INTO param1;
 accepted:=false;
 BEGIN
  INSERT INTO knowledge.api_parameters(operation_id,parent_parameter_id,parameter_key,location,name,ordinal,source_locator,raw_definition)
  VALUES(op2,param1,'child','BODY','child',0,'{}','{}');accepted:=true;
 EXCEPTION WHEN foreign_key_violation THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: API parent from another operation accepted'; END IF;
 passed:=passed+1;
 INSERT INTO knowledge.api_examples(operation_id,example_key,example_kind,context,status_label_raw,http_status,payload_status,source_locator)
 VALUES(op1,'raw-label','RESPONSE','REFERENCE','2011',NULL,'NOT_CAPTURED','{}');
 accepted:=false;
 BEGIN
  INSERT INTO knowledge.api_examples(operation_id,example_key,example_kind,context,status_label_raw,http_status,payload_status,source_locator)
  VALUES(op1,'bad-code','RESPONSE','REFERENCE','2011',2011,'NOT_CAPTURED','{}');accepted:=true;
 EXCEPTION WHEN check_violation THEN NULL;
 END;
 IF accepted THEN RAISE EXCEPTION 'FAIL: invalid numeric HTTP status accepted'; END IF;
 passed:=passed+1;
 IF passed<>14 THEN RAISE EXCEPTION 'Unexpected test count: %',passed; END IF;
 RAISE NOTICE 'PASS: all % schema smoke checks completed. The next ROLLBACK removes every synthetic fixture.',passed;
END
$smoke$;
ROLLBACK;
