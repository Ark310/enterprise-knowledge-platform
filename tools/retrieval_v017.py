"""POC-only alternate chunk search, halfvec HNSW and reproducible three-mode comparison."""
import json,time,uuid,datetime
from pathlib import Path
import worker as w
from transcript_groups import VERSION,CONFIG_HASH
MODES=('old_exact','improved_exact','improved_hnsw')
def validate_mode(mode):
    if mode not in MODES:raise ValueError('Search mode must be '+', '.join(MODES))
    return mode

def index_spec(profile_id,dimensions):
    p=str(uuid.UUID(str(profile_id)));d=int(dimensions)
    if not 1<=d<=4000:raise ValueError('halfvec HNSW requires 1–4000 dimensions; no vectors were truncated')
    return {'profile_id':p,'dimensions':d,'source_index':'td017_content_'+p.replace('-',''),'analysis_index':'td017_analysis_'+p.replace('-','')}

def indexes(db,profile):
    spec=index_spec(profile['id'],profile['dimensions'])
    rows=w.q(db,"select c.relname,i.indisvalid,pg_get_indexdef(i.indexrelid) definition from pg_index i join pg_class c on c.oid=i.indexrelid where c.relname in (%s,%s)",(spec['source_index'],spec['analysis_index'])).fetchall()
    return spec,rows

def grouping_readiness(db,profile,role=None):
    p=str(uuid.UUID(str(profile['id'])))
    row=w.one(db,f"""select count(*) total_transcripts,count(*) filter(where exists(
      select 1 from knowledge.extractions g where g.source_version_id=v.id
      and g.processor_version=%s and g.config_sha256=%s and g.status='COMPLETE'
      and exists(select 1 from knowledge.content_units u where u.extraction_id=g.id and u.unit_type='PASSAGE')
      and not exists(select 1 from knowledge.content_units u where u.extraction_id=g.id and u.unit_type='PASSAGE'
        and not exists(select 1 from retrieval.content_embeddings e where e.content_unit_id=u.id and e.profile_id='{p}'::uuid))
    )) ready_transcripts from knowledge.source_versions v where v.lifecycle_status='ACTIVE'
      and lower(v.storage_uri) like '%%.srt' and (%s::text is null or v.evidence_role=%s)""",(VERSION,CONFIG_HASH,role,role))
    return dict(row,pending_transcripts=row['total_transcripts']-row['ready_transcripts'])

def derived_search(db,profile,queryvec,mode):
    spec=index_spec(profile['id'],profile['dimensions']);ann=mode=='improved_hnsw'
    distance=f"e.embedding::halfvec({spec['dimensions']}) <=> %s::halfvec({spec['dimensions']})" if ann else 'e.embedding <=> %s::vector'
    w.q(db,'SET LOCAL enable_indexscan='+('on' if ann else 'off'))
    if ann:
        w.q(db,'SET LOCAL enable_seqscan=off');w.q(db,'SET LOCAL enable_sort=off')
    sql=f"""select e.record_id,{distance} distance from retrieval.analysis_embeddings e
      where e.profile_id='{spec['profile_id']}'::uuid and exists(select 1 from analysis.records r
      join analysis.agent_outputs o on o.id=r.agent_output_id where r.id=e.record_id
      and o.validation_status='VALID' and r.review_status<>'REJECTED' OFFSET 0)
      order by {distance} limit 100"""
    plan=w.one(db,'EXPLAIN (FORMAT JSON) '+sql,(queryvec,queryvec))['QUERY PLAN'];ids=[x['record_id'] for x in w.q(db,sql,(queryvec,queryvec)).fetchall()]
    w.q(db,'SET LOCAL enable_seqscan=on');w.q(db,'SET LOCAL enable_sort=on')
    rows=w.q(db,"""select r.id,r.run_id,r.record_key,r.statement,r.details,r.review_status,
      exists(select 1 from analysis.run_sources rs join knowledge.source_versions sv on sv.id=rs.source_version_id
      where rs.run_id=r.run_id and sv.lifecycle_status<>'ACTIVE') evidence_superseded
      from analysis.records r join retrieval.analysis_embeddings e on e.record_id=r.id and e.profile_id=%s
      where r.id=any(%s::uuid[]) order by e.embedding <=> %s::vector,r.id limit 8""",(profile['id'],ids,queryvec)).fetchall() if ids else []
    return rows,{'hnsw_index_used':spec['analysis_index'] in plan_indexes(plan),'query_plan':plan,'candidate_count':len(ids)}

def health(db,cfg):
    profile=w.model_profile(db,cfg);spec,rows=indexes(db,profile)
    dims=w.q(db,'select vector_dims(embedding) dimensions,count(*) count from retrieval.content_embeddings where profile_id=%s group by 1',(profile['id'],)).fetchall()
    if any(x['dimensions']!=profile['dimensions'] for x in dims):raise ValueError('Stored dimensions disagree with embedding profile')
    return {'profile_id':str(profile['id']),'model':profile['model'],'dimensions':profile['dimensions'],'stored_vectors':dims,'indexes':rows,'hnsw_ready':len(rows)==2 and all(x['indisvalid'] and 'USING hnsw' in x['definition'] and f"halfvec({spec['dimensions']})" in x['definition'] for x in rows),'pgvector':w.one(db,"select extversion from pg_extension where extname='vector'")['extversion'],'grouped_transcripts':grouping_readiness(db,profile)}

def build_indexes(db,cfg):
    w.require_db(db);profile=w.model_profile(db,cfg);spec=index_spec(profile['id'],profile['dimensions']);db.commit()
    if w.one(db,"select to_regtype('halfvec') is not null ok")['ok'] is not True:raise ValueError('Installed pgvector lacks halfvec. Existing data was not changed; install pgvector 0.8+ first.')
    for table in ('content_embeddings','analysis_embeddings'):
        mismatch=w.one(db,f'select exists(select 1 from retrieval.{table} where profile_id=%s and vector_dims(embedding)<>%s) bad',(profile['id'],profile['dimensions']))['bad']
        if mismatch:raise ValueError('Stored vectors have incompatible dimensions')
    if not w.one(db,'select pg_try_advisory_lock(107010) ok')['ok']:raise ValueError('Import worker active. Finish /process before building indexes.')
    db.commit();db.autocommit=True
    try:
        for table,key in [('content_embeddings','source_index'),('analysis_embeddings','analysis_index')]:
            name=spec[key]
            existing=w.one(db,'select i.indisvalid from pg_index i join pg_class c on c.oid=i.indexrelid where c.relname=%s',(name,))
            if existing and not existing['indisvalid']:w.q(db,f'DROP INDEX CONCURRENTLY retrieval.{name}')
            w.progress('Building/verifying HNSW: '+name+'; may take several minutes on the first upgrade')
            w.q(db,f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON retrieval.{table} USING hnsw ((embedding::halfvec({spec['dimensions']})) halfvec_cosine_ops) WITH (m=16,ef_construction=64) WHERE profile_id='{spec['profile_id']}'::uuid")
            w.q(db,f'ANALYZE retrieval.{table}')
    finally:
        w.q(db,'select pg_advisory_unlock(107010)');db.autocommit=False
    return health(db,cfg)

def base_sql(mode,profile):
    """Full alternate extraction is selected only after every passage has this profile's vector."""
    validate_mode(mode);p=str(uuid.UUID(str(profile['id'])))
    choice='e.is_active'
    if mode!='old_exact':
        # Profile-scoped readiness avoids switching to a partially embedded replacement.
        grouped=f"g.processor_version='{VERSION}' AND g.config_sha256='{CONFIG_HASH}' AND g.status='COMPLETE' AND EXISTS(select 1 from knowledge.content_units gu where gu.extraction_id=g.id and gu.unit_type='PASSAGE') AND NOT EXISTS(select 1 from knowledge.content_units gu where gu.extraction_id=g.id and gu.unit_type='PASSAGE' AND NOT EXISTS(select 1 from retrieval.content_embeddings ge where ge.content_unit_id=gu.id and ge.profile_id='{p}'::uuid))"
        choice=f"((e.processor_version='{VERSION}' AND e.config_sha256='{CONFIG_HASH}' AND e.status='COMPLETE' AND ({grouped.replace('g.','e.')})) OR (e.is_active AND NOT EXISTS(select 1 from knowledge.extractions g where g.source_version_id=v.id AND {grouped})))"
    return f"""select u.*,v.source_id,v.id version_id,v.evidence_role,v.storage_uri,s.title,s.product
    from knowledge.content_units u join knowledge.extractions e on e.id=u.extraction_id
    join knowledge.source_versions v on v.id=e.source_version_id join knowledge.sources s on s.id=v.source_id
    where v.lifecycle_status='ACTIVE' AND u.unit_type<>'SECTION' AND u.content_status='USABLE'
    AND {choice} AND (%s::text IS NULL OR v.evidence_role=%s)"""

def queries(mode,profile):
    spec=index_spec(profile['id'],profile['dimensions']);base=base_sql(mode,profile)
    distance='e.embedding <=> %s::vector'
    if mode=='improved_hnsw':distance=f"e.embedding::halfvec({spec['dimensions']}) <=> %s::halfvec({spec['dimensions']})"
    # No materialized/ranked wrapper before the ordered ANN scan. EXISTS checks eligibility per candidate.
    semantic=f"""WITH base AS NOT MATERIALIZED ({base}) SELECT e.content_unit_id id,{distance} distance
    FROM retrieval.content_embeddings e WHERE e.profile_id='{spec['profile_id']}'::uuid
    AND EXISTS(select 1 from base b where b.id=e.content_unit_id OFFSET 0) ORDER BY {distance},e.content_unit_id LIMIT %s"""
    # HNSW needs ORDER BY distance alone; UUID tie-break is applied after candidate retrieval.
    if mode=='improved_hnsw':semantic=semantic.replace(f'ORDER BY {distance},e.content_unit_id',f'ORDER BY {distance}')
    lexical=f"""WITH base AS NOT MATERIALIZED ({base}) select id,ts_rank_cd(search_text,plainto_tsquery('simple',%s)) score from base where search_text @@ plainto_tsquery('simple',%s) order by score desc,id limit %s"""
    return base,semantic,lexical

def plan_indexes(plan):
    found=[]
    def visit(x):
        if isinstance(x,dict):
            if 'Index Name' in x:found.append(x['Index Name'])
            for v in x.values():visit(v)
        elif isinstance(x,list):
            for v in x:visit(v)
    visit(plan);return found

def execute(db,profile,text,queryvec,mode,role,limit,candidates=100,force_ann=False):
    validate_mode(mode);limit=max(1,min(int(limit),80));candidates=max(limit,min(int(candidates),1000))
    base,semantic,lexical=queries(mode,profile);args=(role,role,queryvec,queryvec,candidates)
    start=time.perf_counter()
    # Exact baseline is explicit even after HNSW indexes exist. LOCAL settings end with transaction.
    w.q(db,'SET LOCAL enable_indexscan=off');w.q(db,'SET LOCAL enable_bitmapscan=on')
    lex=w.q(db,lexical,(role,role,text,text,candidates)).fetchall()
    if mode=='improved_hnsw':
        w.q(db,'SET LOCAL enable_indexscan=on');w.q(db,'SET LOCAL hnsw.ef_search=200')
        ext=w.one(db,"select extversion from pg_extension where extname='vector'")['extversion']
        if tuple(int(v) for v in ext.split('.')[:2])>=(0,8):w.q(db,"SET LOCAL hnsw.iterative_scan='strict_order'")
        # Opt-in comparison forces exploration of the indexed path without changing defaults permanently.
        if force_ann:
            w.q(db,'SET LOCAL enable_seqscan=off');w.q(db,'SET LOCAL enable_sort=off')
    plan=w.one(db,'EXPLAIN (FORMAT JSON) '+semantic,args)['QUERY PLAN']
    sem=w.q(db,semantic,args).fetchall()
    actual=plan_indexes(plan);spec=index_spec(profile['id'],profile['dimensions'])
    used=spec['source_index'] in actual
    w.q(db,'SET LOCAL enable_sort=on');w.q(db,'SET LOCAL enable_seqscan=on')
    # Re-sort the ANN candidates with original full precision.
    if sem:
        reranked=w.q(db,'select content_unit_id id,embedding <=> %s::vector distance from retrieval.content_embeddings where profile_id=%s and content_unit_id=any(%s::uuid[]) order by distance,content_unit_id',(queryvec,profile['id'],[x['id'] for x in sem])).fetchall()
    else:reranked=[]
    if mode=='improved_hnsw':
        w.q(db,'SET LOCAL enable_seqscan=on');w.q(db,'SET LOCAL enable_sort=on')
    scores={}
    for rows in (lex,reranked):
        for rank,row in enumerate(rows,1):scores[str(row['id'])]=scores.get(str(row['id']),0)+1/(60+rank)
    ids=sorted(scores,key=lambda uid:(-scores[uid],uid))[:limit]
    rows=w.q(db,f'WITH base AS NOT MATERIALIZED ({base}) select * from base where id=any(%s::uuid[])',(role,role,ids)).fetchall() if ids else []
    lookup={str(r['id']):r for r in rows};passages=[]
    for uid in ids:
        if uid in lookup:
            r=lookup[uid];r['score']=scores[uid];passages.append(r)
    # Adjacent passages remain separate evidence with their own IDs/locators. No synthetic merged quotations.
    neighbours=[];seen=set(ids);budget=6000
    if mode!='old_exact':
        for row in passages:
            if budget<=0:break
            if row['locator'].get('grouping_version')!=VERSION:continue
            near=w.q(db,"select u.*,v.id version_id,v.evidence_role,v.storage_uri,s.title,s.product from knowledge.content_units u join knowledge.extractions e on e.id=u.extraction_id join knowledge.source_versions v on v.id=e.source_version_id join knowledge.sources s on s.id=v.source_id where u.extraction_id=%s and u.unit_type='PASSAGE' and u.unit_key ~ '^[0-9]+$' and abs(u.unit_key::integer-%s)<=1 order by u.start_seconds,u.unit_key",(row['extraction_id'],int(row['unit_key']))).fetchall()
            for n in near:
                if str(n['id']) not in seen and len(n['content_text'])<=budget:
                    n['context_for']=str(row['id']);neighbours.append(n);seen.add(str(n['id']));budget-=len(n['content_text'])
    elapsed=(time.perf_counter()-start)*1000
    return {'passages':passages,'neighbour_context':neighbours,'semantic_ids':[str(x['id']) for x in reranked], 'diagnostics':{'mode':mode,'milliseconds':round(elapsed,2),'semantic_candidates':len(sem),'final_count':len(passages),'hnsw_index_used':used,'access_path':'HNSW' if used else 'EXACT_OR_OTHER_PLAN','index_names':actual,'query_plan':plan,'requested_ann_path':force_ann,'candidate_budget':candidates,'profile_id':str(profile['id']),'dimensions':profile['dimensions']}}

def overlap(reference,candidate):
    shared=len(set(reference)&set(candidate))
    return {'shared':shared,'reference_count':len(reference),'candidate_count':len(candidate),'recall':shared/len(reference) if reference else None}

def search(db,cfg,text,role=None,limit=20):
    w.require_db(db);profile=w.model_profile(db,cfg);queryvec=w.vector(w.embed(cfg,text,True));db.commit()
    configured=validate_mode(cfg.get('SearchMode','improved_hnsw'));spec,ready=indexes(db,profile)
    if configured=='improved_hnsw' and not any(x['relname']==spec['source_index'] and x['indisvalid'] for x in ready):raise ValueError('v0.17 HNSW source index is not ready. Run Build-Search-Indexes.cmd once, then retry. No fallback was labelled HNSW.')
    data=execute(db,profile,text,queryvec,configured,role,limit,cfg.get('SearchCandidateBudget',100),force_ann=configured=='improved_hnsw')
    w.progress(f"Search {configured}: {data['diagnostics']['access_path']}; {len(data['passages'])} ranked passages; original-vector reranking")
    # Context is passed as separate citable units so existing B validators can verify exact excerpts.
    data['passages']+=data['neighbour_context']
    data['derived_findings'],data['derived_search_diagnostics']=derived_search(db,profile,queryvec,configured)
    data['grouped_transcripts']=grouping_readiness(db,profile,role)
    data['coverage']='Bounded hybrid search. Neighbours retain separate citations. Video is sampled, not continuously watched; no corpus-wide absence claim.'
    return data

def compare(db,cfg,text,role=None,limit=20):
    w.require_db(db);profile=w.model_profile(db,cfg);queryvec=w.vector(w.embed(cfg,text,True));db.commit()
    spec,ready=indexes(db,profile);db.commit()
    if not any(x['relname']==spec['source_index'] and x['indisvalid'] for x in ready):raise ValueError('Build-Search-Indexes.cmd must succeed before comparison')
    w.q(db,'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
    readiness=grouping_readiness(db,profile,role)
    if readiness['total_transcripts'] and not readiness['ready_transcripts']:
        raise ValueError('No grouped transcripts are ready for this profile. Run /process, wait for completion, then /compare. Old-chunk fallback is not a valid chunking comparison.')
    # All modes share one snapshot and one query embedding. Neighbour retrieval is excluded from top-k metrics.
    results={m:execute(db,profile,text,queryvec,m,role,limit,cfg.get('SearchCandidateBudget',100),m=='improved_hnsw') for m in MODES}
    exact=results['improved_exact'];ann=results['improved_hnsw'];k=max(1,min(int(limit),80))
    report={'grouped_transcripts':readiness,'chunking_comparison_ready':readiness['ready_transcripts']>0,'query':text,'role':role,'profile_id':str(profile['id']),'dimensions':profile['dimensions'],'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'modes':results,'ann_semantic_recall_at_k':overlap(exact['semantic_ids'][:k],ann['semantic_ids'][:k]),'hybrid_top_k_overlap':overlap([str(x['id']) for x in exact['passages']],[str(x['id']) for x in ann['passages']]),'old_vs_improved_source_overlap':overlap(list({str(x['version_id']) for x in results['old_exact']['passages']}),list({str(x['version_id']) for x in exact['passages']})),'notes':['One query embedding and repeatable-read snapshot. Timings exclude query embedding and agent reasoning; one warm run is not a latency benchmark.','old_exact versus improved_exact changes chunking. Compare source/version coverage; different chunk IDs are expected.','ANN recall compares semantic neighbours of the SAME improved corpus only; hybrid overlap is separate.','If hnsw_index_used is false, this run is not evidence of ANN performance. Query plans are included.','No answer-quality or SME truth score is inferred from overlap.']}
    db.commit();folder=w.BASE/'runtime/comparisons';folder.mkdir(parents=True,exist_ok=True);stem=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    path=folder/(stem+'.json');path.write_text(w.j(report),encoding='utf-8')
    lines=['# Search comparison',text,'','| Mode | Database ms | Matches | HNSW used |','|---|---:|---:|---|']
    for m,r in results.items():
        d=r['diagnostics'];lines.append(f"| {m} | {d['milliseconds']} | {len(r['passages'])} | {d['hnsw_index_used']} |")
    for m,r in results.items():
        lines.extend(['',f'## {m} evidence']+[f"- {p['title']} [{p['version_id']}] {w.j(p['locator'])}: {p['content_text'][:400]}" for p in r['passages']])
    lines+=['','Semantic ANN recall@k: '+str(report['ann_semantic_recall_at_k']['recall'])]+report['notes']
    md=folder/(stem+'.md');md.write_text('\n'.join(lines),encoding='utf-8')
    return {'grouped_transcripts':readiness,'chunking_comparison_ready':readiness['ready_transcripts']>0,'report_json':str(path),'report_markdown':str(md),'modes':{m:r['diagnostics'] for m,r in results.items()},'ann_semantic_recall_at_k':report['ann_semantic_recall_at_k'],'hybrid_top_k_overlap':report['hybrid_top_k_overlap'],'old_vs_improved_source_overlap':report['old_vs_improved_source_overlap'],'notes':report['notes']}
