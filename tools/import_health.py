"""Bounded import phases and restart-safe timeout exclusions. No content/secrets in health logs."""
import contextlib,datetime,faulthandler,functools,json,os,threading,time,uuid
from pathlib import Path
ACTIVE=None
class ServiceUnavailable(RuntimeError):pass

def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 tmp.write_text(json.dumps(data,ensure_ascii=True,default=str),encoding='utf-8');tmp.replace(path)

def read(path):
 try:return json.loads(Path(path).read_text(encoding='utf-8'))
 except (OSError,ValueError):return {}

class Probe:
 def __init__(self,base,cfg,options):
  self.base=Path(base);self.cfg=cfg;self.options=options or {};self.root=Path(cfg['DataRoot']).resolve();self.runtime=self.base/'runtime';self.state_path=self.runtime/'import-state.json';self.skip_path=self.runtime/'import-timeouts.json'
  self.run_id=uuid.UUID(str(self.options['import_run_key'])).hex if self.options.get('import_run_key') else uuid.uuid4().hex;self.trace=self.runtime/'import-traces'/self.run_id;self.trace.mkdir(parents=True)
  self.stack_file=open(self.trace/'python-stack.log','w',encoding='utf-8',buffering=1)
  self.stage_seconds=max(.1,float(cfg.get('ImportStageTimeoutSeconds',180)));self.file_seconds=max(self.stage_seconds,float(cfg.get('ImportFileTimeoutSeconds',1800)));self.beat=max(.05,float(cfg.get('ImportHeartbeatSeconds',10)))
  self.lock=threading.RLock();self.frames=[];self.file=None;self.state='RUNNING';self.stop=threading.Event();self.last_saved=0;self.timed_out=False;self.failure=None;self.log_thread=None
  self.exclusions=read(self.skip_path);self.thread=threading.Thread(target=self.watch,name='import-watchdog',daemon=True)
 def snapshot(self):
  with self.lock:
   top=self.frames[-1] if self.frames else {'stage':'STARTING','started':time.monotonic(),'limit':self.stage_seconds}
   if self.state=='FAILED' and self.failure:top=dict(top,stage=self.failure['stage'],started=self.failure['started']);
   return dict(state=self.state,stage=top['stage'],elapsed_seconds=round(time.monotonic()-top['started'],1),limit_seconds=top['limit'],file=(self.failure or {}).get('file',self.file) if self.state=='FAILED' else self.file,run_id=self.run_id,worker_pid=os.getpid(),updated_at=stamp(),trace_directory=str(self.trace),timeout_exclusions=len(self.exclusions))
 def save(self,force=False):
  if force or time.monotonic()-self.last_saved>=1:
   data=self.snapshot();atomic(self.trace/'state.json',data);atomic(self.state_path,data);self.last_saved=time.monotonic()
 def identify(self,path,stat=None):
  p=Path(path);s=stat or p.stat()
  try:relative=p.resolve().relative_to(self.root).as_posix()
  except ValueError:relative=str(p)
  return {'path':str(p),'relative':relative,'size':s.st_size,'mtime_ns':s.st_mtime_ns,'root':str(self.root)}
 def key(self,info):return info['root']+'|'+info['relative']
 def excluded(self,path):
  forced=set(self.options.get('skip_timeout_paths',[]))
  if self.options.get('retry_timeouts') and str(Path(path)) not in forced:return False
  try:info=self.identify(path)
  except OSError:return False
  old=self.exclusions.get(self.key(info),{})
  same=bool(old and old.get('size')==info['size'] and old.get('mtime_ns')==info['mtime_ns'])
  if same and old.get('sha256'):
   import hashlib
   with file_scope(path):
    with phase('CHECK_TIMEOUT_IDENTITY'):
     digest=hashlib.sha256()
     with open(path,'rb') as source:
      for block in iter(lambda:source.read(1048576),b''):digest.update(block)
     return digest.hexdigest()==old['sha256']
  return same
 def acknowledge(self,path):
  try:key=self.key(self.identify(path))
  except OSError:return
  if key in self.exclusions:self.exclusions.pop(key);atomic(self.skip_path,self.exclusions)
 def watch(self):
  next_beat=time.monotonic()+self.beat
  while not self.stop.wait(min(.1,self.beat)):
   now=time.monotonic()
   with self.lock:
    overdue=next((f for f in reversed(self.frames) if now-f['started']>f['limit']),None)
   if overdue:
    self.state='TIMED_OUT';self.timed_out=True
    with self.lock:
     recoverable=bool(self.file) and overdue['stage'] not in ('SCAN','PROCESS','REPORT_PROGRESS')
     if recoverable:
      entry=dict(self.file,stage=overdue['stage'],at=stamp(),trace_directory=str(self.trace));self.exclusions[self.key(entry)]=entry
    # Persist the reason before terminating blocked I/O. Never mark an embedding as complete here.
    try:
     atomic(self.skip_path,self.exclusions);data=self.snapshot();data.update(stage=overdue['stage'],elapsed_seconds=round(now-overdue['started'],1),limit_seconds=overdue['limit'],recoverable=recoverable);atomic(self.trace/'state.json',data);atomic(self.state_path,data)
     faulthandler.dump_traceback(file=self.stack_file,all_threads=True)
    finally:os._exit(124)
   if now>=next_beat:
    try:self.save(True)
    except Exception as error:
     threading.Thread(target=lambda:print('[import] Health log write failed; stopping safely: '+type(error).__name__,file=__import__('sys').stderr,flush=True),daemon=True).start()
     os._exit(125)
    s=self.snapshot();label=(s['file'] or {}).get('relative','startup')
    # Logging is separate so a full stderr pipe cannot stop the watchdog deadline.
    line=f"[import] still waiting: {label} | {s['stage']} | {s['elapsed_seconds']}s / {s['limit_seconds']}s"
    if self.log_thread is None or not self.log_thread.is_alive():
     self.log_thread=threading.Thread(target=lambda t=line:print(t,file=__import__('sys').stderr,flush=True),daemon=True);self.log_thread.start()
    next_beat=now+self.beat
 def close(self,error=None):
  self.stop.set();self.thread.join(2)
  if self.timed_out:return
  self.state='CANCELLED' if isinstance(error,KeyboardInterrupt) else 'FAILED' if error else 'COMPLETE'
  self.save(True);self.stack_file.close()

@contextlib.contextmanager
def session(base,cfg,options=None):
 global ACTIVE
 if ACTIVE is not None:yield ACTIVE;return
 probe=Probe(base,cfg,options);ACTIVE=probe;probe.save(True);probe.thread.start()
 try:yield probe
 except BaseException as error:probe.close(error);raise
 else:probe.close()
 finally:ACTIVE=None

@contextlib.contextmanager
def phase(name,limit=None):
 probe=ACTIVE
 if probe is None:yield;return
 frame={'stage':name,'started':time.monotonic(),'limit':limit or probe.stage_seconds}
 with probe.lock:probe.frames.append(frame)
 probe.save()
 try:yield
 except BaseException:
  if probe.failure is None:probe.failure=dict(frame,file=probe.file.copy() if probe.file else None)
  raise
 finally:
  with probe.lock:
   if frame in probe.frames:probe.frames.remove(frame)
   # Structural scan/process phases measure silence, not total batch duration.
   for parent in probe.frames:
    if parent['stage'] in ('SCAN','PROCESS'):parent['started']=time.monotonic()
  probe.save()

@contextlib.contextmanager
def file_scope(path,stat=None):
 probe=ACTIVE
 if probe is None:yield;return
 old=probe.file;probe.failure=None;probe.file=probe.identify(path,stat)
 try:
  with phase('FILE',probe.file_seconds):yield
 finally:probe.file=old

def skip_file(path):return bool(ACTIVE and ACTIVE.excluded(path))
def acknowledge(path):
 if ACTIVE:ACTIVE.acknowledge(path)

def traced(name,file_arg=None):
 def decorate(fn):
  @functools.wraps(fn)
  def run(*args,**kwargs):
   if not ACTIVE:return fn(*args,**kwargs)
   if file_arg is not None and ACTIVE.file is None:
    with file_scope(args[file_arg]):
     with phase(name):return fn(*args,**kwargs)
   with phase(name):return fn(*args,**kwargs)
  return run
 return decorate
