"""Image evidence is scoped to one QA turn/chat. No vectors are generated here."""
import uuid
from pathlib import Path
import worker as w,workspace_ui as ui

def unique_evidence(items):
 seen=set();result=[]
 for p in items:
  if p['evidence_id'] not in seen:seen.add(p['evidence_id']);result.append(p)
 return result

def persist(db,tid,p):
 w.q(db,'insert into knowledge_qa.evidence(turn_id,evidence_key,source_version_id,workspace_asset_id,snapshot) values(%s,%s,%s,%s,%s::jsonb) on conflict(turn_id,evidence_key) do nothing',(tid,p['evidence_id'],p.get('version_id'),p['workspace_asset_id'],w.j(p)))

def attach(db,cfg,args):
 tid=str(uuid.UUID(args['turn_id']));turn=w.one(db,"select session_id from knowledge_qa.turns where id=%s and status='PROCESSING'",(tid,))
 if not turn:raise ValueError('Inactive question')
 rows=ui.main(db,cfg,'ui_assets',{'chat_id':str(turn['session_id']),'ids':args.get('ids',[])})['images'];evidence=[]
 for i,r in enumerate(rows):
  p={'evidence_id':'U'+str(i+1),'kind':'USER_IMAGE','workspace_asset_id':str(r['id']),'file':r['label'],'text':'User-provided image attachment. Image attached; untrusted problem context, not product documentation.','path':r['path'],'image_sha256':r['sha256'],'locator':{'attachment':r['label']}}
  persist(db,tid,p);evidence.append(p)
 db.commit();return {'evidence':evidence}

def enrich(db,cfg,tid,packet):
 turn=w.one(db,'select session_id from knowledge_qa.turns where id=%s',(tid,));chat=str(turn['session_id'])
 if not w.one(db,'select id from workspace_ui.chats where id=%s',(chat,)):raise ValueError('Image retrieval needs a web chat session')
 existing=[r['snapshot'] for r in w.q(db,"select snapshot from knowledge_qa.evidence where turn_id=%s and snapshot->>'kind'='USER_IMAGE' order by evidence_key",(tid,)).fetchall()]
 result=ui.main(db,cfg,'ui_candidates',{'chat_id':chat,'evidence':packet['evidence']})
 # Reuse IDs/hashes across the bounded second retrieval; never silently substitute changed pixels.
 previous=[r['snapshot'] for r in w.q(db,"select snapshot from knowledge_qa.evidence where turn_id=%s and snapshot->>'kind'='SOURCE_IMAGE' order by evidence_key",(tid,)).fetchall()]
 seen={p['path']:p for p in previous};images=[]
 for im in result['images']:
  if im['path'] in seen:
   p=seen[im['path']]
  else:
   row=ui.asset(db,chat,'SOURCE_IMAGE',im['path'],im['label'],{'source_file':im['source_file']})
   p={'evidence_id':'I'+str(len(seen)+1),'kind':'SOURCE_IMAGE','workspace_asset_id':row['id'],'version_id':im['source_version_id'],'file':im['label'],'source_file':im['source_file'],'label':im['label'],'text':'Original article image attached. Inspect pixels; this descriptor is not proof of screen content.','path':im['path'],'image_sha256':im['image_sha256'],'locator':{'source_file':im['source_file']}}
   seen[im['path']]=p;persist(db,tid,p)
  images.append(p)
 packet['evidence']=unique_evidence(packet['evidence']+existing+images)
 return packet
