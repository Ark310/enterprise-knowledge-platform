"""Alternate transcript passages; legacy cues and their citation IDs remain untouched."""
import math
import worker as w
VERSION='0.17-transcript-v1'
CONFIG={'target_seconds':30,'max_seconds':60,'max_characters':1800,'pause_seconds':8,'parent_seconds':120}
CONFIG_HASH=w.sha(w.j(CONFIG))

def group_cues(cues,duration_seconds=None):
    result=[];buf=[]
    def flush():
        if not buf:return
        result.append({'text':'\n'.join(c['text'] for c in buf),'start':min(c['start'] for c in buf),'end':max(c['end'] for c in buf),'kind':'SUPPLIED_TRANSCRIPT','locator':{'cue_ids':[c['locator']['cue'] for c in buf],'cue_spans':[dict(c['locator'],start_seconds=c['start'],end_seconds=c['end']) for c in buf],'grouping_version':VERSION}})
        buf.clear()
    previous=-1
    for cue in cues:
        a=float(cue['start']);b=float(cue['end'])
        if not math.isfinite(a+b) or a<0 or b<=a or a<previous:raise ValueError('Invalid or out-of-order transcript timing')
        if duration_seconds is not None and b>float(duration_seconds)+0.25:raise ValueError('Transcript cue exceeds the matching recording duration; fix the SRT, timing was not altered')
        previous=a;text=cue['text']
        if len(text)>CONFIG['max_characters']:
            flush()
            for offset in range(0,len(text),CONFIG['max_characters']):
                part=dict(cue,text=text[offset:offset+CONFIG['max_characters']],locator=dict(cue['locator'],character_start=offset,character_end=min(len(text),offset+CONFIG['max_characters'])))
                buf.append(part);flush()
            continue
        if buf and (a-buf[-1]['end']>CONFIG['pause_seconds'] or b-buf[0]['start']>CONFIG['max_seconds'] or sum(len(c['text'])+1 for c in buf)+len(text)>CONFIG['max_characters']):flush()
        buf.append(cue)
        if b-buf[0]['start']>=CONFIG['target_seconds'] and text.rstrip().endswith(('.','?','!')):flush()
    flush();return result

def ensure_grouped(db,cfg,f,sv,ov,profile):
    """Called under the existing import lock, only for SRTs. Commit checkpoints allow retry."""
    ex=w.one(db,'select id from knowledge.extractions where source_version_id=%s and processor_version=%s and config_sha256=%s order by created_at desc limit 1',(sv,VERSION,CONFIG_HASH))
    if not ex:
        cues=w.srt_units(w.decode(__import__('pathlib').Path(f['path']).read_bytes()))
        path=__import__('pathlib').Path(f['path'])
        videos=[p for p in path.parent.iterdir() if p.is_file() and p.stem.lower()==path.stem.lower() and p.suffix.lower() in w.VIDEO_EXT]
        if len(videos)>1:raise ValueError('More than one matching recording; choose an unambiguous basename')
        pairing={'status':'STANDALONE_TRANSCRIPT','alignment':'No matching local recording; timestamps not checked against media duration'}
        seconds=None
        if videos:
            from module_review import duration
            video=w.safe_path(cfg['DataRoot'],videos[0]);digest=w.file_hash(video);seconds,_=duration(cfg,video)
            vf=dict(f,path=str(video),relative=video.relative_to(__import__('pathlib').Path(cfg['DataRoot'])).as_posix(),sha256=digest,bytes=video.stat().st_size,modified=__import__('datetime').datetime.fromtimestamp(video.stat().st_mtime,__import__('datetime').timezone.utc).isoformat())
            video_sv,video_ov=w.register(db,vf)
            if w.file_hash(video)!=digest:raise ValueError('Recording changed during transcript validation')
            target=w.one(db,'select source_id from knowledge.source_versions where id=%s',(video_sv,))['source_id']
            w.q(db,"insert into knowledge.source_links(from_version_id,to_source_id,target_uri,relationship,resolution_status) values(%s,%s,%s,'TRANSCRIPT_FOR','RESOLVED') on conflict do nothing",(sv,target,video.absolute().as_uri()))
            pairing={'status':'FILENAME_MATCH_BOUNDS_CHECKED','recording_file':vf['relative'],'recording_source_version_id':str(video_sv),'recording_sha256':digest,'duration_seconds':seconds,'alignment':'Filename pairing and duration bounds only; speech alignment is not independently verified'}
        rows=group_cues(cues,duration_seconds=seconds)
        if not rows:raise ValueError('Transcript has no usable cues')
        if w.file_hash(f['path'])!=f['sha256']:raise ValueError('Transcript changed during grouping')
        ex=w.one(db,"insert into knowledge.extractions(source_version_id,method,processor_version,status,config_sha256,is_active) values(%s,'LOCAL_GROUPED_TRANSCRIPT',%s,'PROCESSING',%s,false) returning id",(sv,VERSION,CONFIG_HASH))
        parents={};previous=None
        for n,row in enumerate(rows):
            bucket=int(row['start']//CONFIG['parent_seconds'])
            loc=dict(row['locator'],file=f['relative'],source_version_id=str(sv),start_seconds=row['start'],end_seconds=row['end'],recording=pairing)
            if bucket not in parents:
                parents[bucket]=w.one(db,"insert into knowledge.content_units(extraction_id,unit_key,unit_type,heading,content_text,representation_kind,locator,content_sha256,start_seconds,end_seconds) values(%s,%s,'SECTION',%s,'','SUPPLIED_TRANSCRIPT',%s::jsonb,%s,%s,%s) returning id",(ex['id'],'section:'+str(bucket),__import__('pathlib').Path(f['path']).name,w.j({'file':f['relative'],'source_version_id':str(sv),'section':bucket}),w.sha(''),bucket*120,max((bucket+1)*120,row['end'])))['id']
            uid=w.one(db,"insert into knowledge.content_units(extraction_id,parent_unit_id,unit_key,unit_type,heading,content_text,representation_kind,locator,content_sha256,start_seconds,end_seconds,metadata) values(%s,%s,%s,'PASSAGE',%s,%s,'SUPPLIED_TRANSCRIPT',%s::jsonb,%s,%s,%s,%s::jsonb) returning id",(ex['id'],parents[bucket],str(n),__import__('pathlib').Path(f['path']).name,row['text'],w.j(loc),w.sha(row['text']),row['start'],row['end'],w.j({'grouping':CONFIG})))['id']
            originals=w.q(db,"select u.id from knowledge.content_units u join knowledge.extractions e on e.id=u.extraction_id where e.source_version_id=%s and e.is_active and (u.locator->>'cue')::integer=any(%s::integer[])",(sv,row['locator']['cue_ids'])).fetchall()
            for original in originals:w.q(db,"insert into knowledge.unit_links(from_unit_id,to_unit_id,relationship) values(%s,%s,'DERIVED_FROM') on conflict do nothing",(uid,original['id']))
            if previous:w.q(db,"insert into knowledge.unit_links(from_unit_id,to_unit_id,relationship) values(%s,%s,'NEXT') on conflict do nothing",(previous,uid))
            previous=uid
        db.commit()
    pending=w.q(db,"select u.id,u.content_text from knowledge.content_units u where u.extraction_id=%s and u.unit_type='PASSAGE' and not exists(select 1 from retrieval.content_embeddings e where e.content_unit_id=u.id and e.profile_id=%s)",(ex['id'],profile['id'])).fetchall();db.commit()
    for u in pending:
        v=w.embed(cfg,u['content_text'])
        if len(v)!=profile['dimensions']:raise ValueError('Grouping vector profile mismatch')
        w.q(db,'insert into retrieval.content_embeddings(content_unit_id,profile_id,input_sha256,embedding,embedded_text) values(%s,%s,%s,%s::vector,%s) on conflict do nothing',(u['id'],profile['id'],w.sha(u['content_text']),w.vector(v),u['content_text']));db.commit()
    w.q(db,"update knowledge.extractions set status='COMPLETE' where id=%s",(ex['id'],));db.commit()
    return len(pending)
