"""Opt-in real PostgreSQL tests; disposable fixtures only, never operator data."""
import os,sys,uuid,tempfile,base64,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import worker as w,workspace_ui as ui,knowledge_qa as qa,chat_images
import psycopg
from psycopg.rows import dict_row
from PIL import Image

def run():
 assert os.environ.get('TD_V024_DISPOSABLE')=='YES'
 db=psycopg.connect(os.environ['TD_V024_TEST_DSN'],row_factory=dict_row,prepare_threshold=None)
 assert db.info.dbname=='knowledge_poc'
 checks=[]
 def check(ok,label):assert ok,label;checks.append(label);print('PASS QA24',label,flush=True)
 def reject(fn):
  try:fn()
  except (ValueError,Exception):db.rollback();return True
  return False
 w.migration(db);db.commit()
 with tempfile.TemporaryDirectory() as tmp:
  cfg={'DataRoot':tmp,'WebDataRoot':str(Path(tmp)/'private')}
  def call(op,**kw):return ui.main(db,cfg,op,kw)
  a=call('ui_create',poc=2);aid=str(a['id']);b=call('ui_create',poc=2);bid=str(b['id'])
  call('ui_state',chat_id=aid,context={'qa':{'conversation':{'turns':[{'user_message':'Reset a password'}]}}})
  call('ui_message',id=str(uuid.uuid4()),chat_id=aid,role='user',body='Reset a password',payload={})
  check(call('ui_get',chat_id=aid)['messages'][0]['body']=='Reset a password','messages survive independent reads')
  check(call('ui_get',chat_id=aid)['context']['qa']['conversation']['turns'][0]['user_message']=='Reset a password','intent context persists')
  check(not call('ui_get',chat_id=bid)['messages'] and not call('ui_get',chat_id=bid)['context'],'new chat starts isolated')
  before=w.one(db,'select count(*) n from retrieval.content_embeddings')['n']
  buf=io.BytesIO();Image.new('RGB',(40,30),'teal').save(buf,'PNG')
  upload=call('ui_upload',chat_id=aid,name='private.png',base64=base64.b64encode(buf.getvalue()).decode())
  check(call('ui_asset',chat_id=aid,id=upload['id'])['mime']=='image/png','actual decoded upload is retrievable')
  check(reject(lambda:call('ui_assets',chat_id=bid,ids=[upload['id']])),'cross-chat upload rejected')
  check(reject(lambda:call('ui_asset',chat_id=bid,id=upload['id'])),'cross-chat preview rejected')
  tid=str(uuid.uuid4());qa.begin(db,{'session_id':aid,'turn_id':tid,'question':'What is visible in my image?'})
  evidence=chat_images.attach(db,cfg,{'turn_id':tid,'ids':[upload['id']]})['evidence']
  check(len(evidence)==1 and evidence[0]['kind']=='USER_IMAGE','upload attached as scoped QA evidence')
  w.migration(db);db.commit();check(True,'repeat migration accepts existing image evidence')
  check(w.one(db,'select count(*) n from retrieval.content_embeddings')['n']==before,'upload and QA attach never add corpus vectors')
  path=Path(evidence[0]['path']);path.write_bytes(b'changed')
  check(reject(lambda:call('ui_assets',chat_id=aid,ids=[upload['id']])),'changed image bytes cannot be silently reused')
  article=Path(tmp)/'article.md';article.write_text('Open Settings.\n![Setting](setting.png)')
  Image.new('RGB',(20,20),'green').save(Path(tmp)/'setting.png')
  sv,_=w.register(db,{'path':str(article),'relative':'article.md','role':'EXISTING_ASSET','group':'existing-assets','sha256':w.file_hash(article),'bytes':article.stat().st_size,'modified':'2026-11-09T00:00:00Z'});db.commit()
  p={'version_id':str(sv),'kind':'SOURCE','evidence_id':'S1','file':'article.md','text':'Open Settings.','source_metadata':{'url':'https://example.test/article'}}
  show=call('ui_present',chat_id=aid,evidence=[p]);check(len(show['sources'])==1,'cited article receives an opaque local hyperlink')
  check(call('ui_asset',chat_id=aid,id=show['sources'][0]['id'],text=True)['text'].startswith('Open Settings.'),'source link reads original text')
  check(show['sources'][0]['metadata']['original_url']=='https://example.test/article','original web link retained')
  check(len(call('ui_candidates',chat_id=aid,evidence=[p])['images'])==1,'original linked screenshot discovered without remote fetching')
  article.write_text('Different revision of this article.')
  changed=call('ui_present',chat_id=aid,evidence=[p]);check(not changed['sources'] and changed['unavailable']==['article.md'],'newer file bytes never substituted for cited revision')
  owner=str(uuid.uuid4());call('ui_claim',owner=owner)
  check(reject(lambda:call('ui_claim',owner=str(uuid.uuid4()))),'concurrent process lease rejected')
  call('ui_message',id=str(uuid.uuid4()),chat_id=aid,role='user',body='Pending fixture',payload={'job':owner})
  check(not any(m['payload'].get('status')=='INTERRUPTED' for m in call('ui_get',chat_id=aid)['messages']),'active lease does not mark current job interrupted')
  call('ui_release',owner=owner)
  check(any(m['payload'].get('status')=='INTERRUPTED' for m in call('ui_get',chat_id=aid)['messages']),'interrupted job is explained without replay')
 db.close();print('QA24 checks passed:',len(checks))
if __name__=='__main__':run()
