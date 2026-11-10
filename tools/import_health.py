"""Import deadlines are independent of optional, best-effort monitoring files."""
import contextlib,datetime,faulthandler,functools,json,os,threading,time,uuid
from pathlib import Path
ACTIVE=None
class ServiceUnavailable(RuntimeError):pass

def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  tmp.write_text(json.dumps(data,ensure_ascii=True,default=str),encoding='utf-8')
  for attempt in range(3):
   try:tmp.replace(path);return
   except PermissionError:
    if attempt==2:raise
    time.sleep(.01*(attempt+1))
 finally:
  try:tmp.unlink(missing_ok=True)
  except OSError:pass

def read(path):
 try:return json.loads(Path(path).read_text(encoding='utf-8'))
 except (OSError,ValueError):return {}

class Probe:
 def __init__(self,base,cfg,options):
  self.base=Path(base);self.cfg=cfg;self.options=options or {};self.root=Path(cfg['DataRoot']).resolve();self.runtime=self.base/'runtime'
  self.state_path=self.runtime/'import-state.json';self.skip_path=self.runtime/'import-timeouts.json'
  self.run_id=uuid.UUID(str(self.options['import_run_key'])).hex if self.options.get('import_run_key') else uuid.uuid4().hex
  self.trace=self.runtime/'import-traces'/self.run_id
  self.stage_seconds=max(.1,float(cfg.get('ImportStageTimeoutSeconds',180)));self.file_seconds=max(self.stage_seconds,float(cfg.get('ImportFileTimeoutSeconds',1800)))
  self.beat=max(.05,float(cfg.get('ImportHeartbeatSeconds',10)));self.lock=threading.RLock();self.frames=[];self.file=None
  self.state='RUNNING';self.stop=threading.Event();self.last_saved=0;self.timed_out=False;self.failure=None;self.log_thread=None
  self.warning=None;self.warning_count=0;self.exclusions={}
  loaded=threading.Event();box=[]
  def load_exclusions():
   try:box.append(read(self.skip_path))
   finally:loaded.set()
  threading.Thread(target=load_exclusions,daemon=True).start()
  if loaded.wait(.15) and box and isinstance(box[0],dict):self.exclusions=box[0]
  else:self.warn(OSError('timeout map unavailable'),self.skip_path)
  self.io_signal=threading.Event();self.io_stop=threading.Event();self.pending=None;self.pending_exclusions=None;self.terminal=None
  self.checkpoint_done=threading.Event();self.checkpoint_ok=False
  self.writer=threading.Thread(target=self.write_loop,name='import-status-writer',daemon=True)
  self.thread=threading.Thread(target=self.watch,name='import-watchdog',daemon=True)
 def snapshot(self):
  with self.lock:
   top=self.frames[-1] if self.frames else {'stage':self.state,'started':time.monotonic(),'limit':self.stage_seconds}
   if self.state=='FAILED' and self.failure:top=self.failure
   file=(self.failure or {}).get('file',self.file) if self.state=='FAILED' else self.file
   return dict(state=self.state,stage=top['stage'],elapsed_seconds=round(time.monotonic()-top['started'],1),limit_seconds=top['limit'],file=dict(file) if file else None,run_id=self.run_id,worker_pid=os.getpid(),updated_at=stamp(),trace_directory=str(self.trace),timeout_exclusions=len(self.exclusions),monitoring_warning=self.warning)
 def save(self,force=False):
  # Only enqueue snapshots. Disk writes must never run on ingestion or deadline threads.
  with self.lock:
   if force or time.monotonic()-self.last_saved>=1:
    self.pending=self.snapshot();self.last_saved=time.monotonic();self.io_signal.set()
 def warn(self,error,path):
  with self.lock:
   self.warning_count+=1;first=self.warning is None
   self.warning=f'Monitoring status unavailable: {Path(path).name}: {type(error).__name__}'
  if first:self.emit('[import] Monitoring warning (nonfatal): '+self.warning+'. Processing continues; timeout monitor remains active.')
 def emit(self,line):
  if self.log_thread is None or not self.log_thread.is_alive():
   self.log_thread=threading.Thread(target=lambda t=line:print(t,file=__import__('sys').stderr,flush=True),daemon=True);self.log_thread.start()
 def write_loop(self):
  while True:
   self.io_signal.wait(.1);self.io_signal.clear()
   with self.lock:
    terminal=self.terminal;self.terminal=None;data=self.pending;self.pending=None;exclusions=self.pending_exclusions;self.pending_exclusions=None
   if terminal is not None:
    checkpoint,entries=terminal
    try:
     atomic(self.skip_path,entries)
     checkpoint['checkpoint_persisted']=True
     atomic(self.trace/'state.json',checkpoint)
     self.checkpoint_ok=True
    except Exception as error:self.warn(error,self.trace/'state.json')
    try:
     self.trace.mkdir(parents=True,exist_ok=True)
     with (self.trace/'python-stack.log').open('w',encoding='utf-8') as stack:faulthandler.dump_traceback(file=stack,all_threads=True)
    except Exception as error:self.warn(error,self.trace/'python-stack.log')
    # Do not overwrite terminal state with a stale queued RUNNING snapshot.
    data=checkpoint;exclusions=None
   if exclusions is not None:
    try:atomic(self.skip_path,exclusions)
    except Exception as error:self.warn(error,self.skip_path)
   if data is not None:
    for path in (self.trace/'state.json',self.state_path):
     try:atomic(path,data)
     except Exception as error:self.warn(error,path)
   if terminal is not None:self.checkpoint_done.set()
   if self.io_stop.is_set():
    with self.lock:
     if self.pending is None and self.pending_exclusions is None:return
    self.io_signal.set()
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
  with self.lock:
   if key in self.exclusions:
    self.exclusions.pop(key);self.pending_exclusions=dict(self.exclusions);self.io_signal.set()
 def watch(self):
  next_beat=time.monotonic()+self.beat
  while not self.stop.wait(min(.05,self.beat)):
   now=time.monotonic()
   with self.lock:overdue=next((f.copy() for f in reversed(self.frames) if now-f['started']>f['limit']),None)
   if overdue:
    with self.lock:
     self.state='TIMED_OUT';self.timed_out=True
     recoverable=bool(self.file) and overdue['stage'] not in ('SCAN','PROCESS','REPORT_PROGRESS')
     if recoverable:
      entry=dict(self.file,stage=overdue['stage'],at=stamp(),trace_directory=str(self.trace));self.exclusions[self.key(entry)]=entry
     data=self.snapshot();data.update(stage=overdue['stage'],elapsed_seconds=round(now-overdue['started'],1),limit_seconds=overdue['limit'],recoverable=recoverable,checkpoint_persisted=False)
     self.terminal=(dict(data),dict(self.exclusions));self.io_signal.set()
    # Deadline enforcement does not depend on any filesystem or console write completing.
    self.checkpoint_done.wait(.35)
    data['checkpoint_persisted']=self.checkpoint_ok;data['recoverable']=recoverable and self.checkpoint_ok
    report=('TD_IMPORT_FAILURE_JSON:'+json.dumps(data,ensure_ascii=True,default=str)+'\n').encode('utf-8')
    sent=threading.Event()
    def report_failure():
     try:os.write(2,report)
     except OSError:pass
     finally:sent.set()
    threading.Thread(target=report_failure,daemon=True).start();sent.wait(.1)
    os._exit(124)
   if now>=next_beat:
    self.save(True);s=self.snapshot();label=(s['file'] or {}).get('relative','inventory/startup')
    self.emit(f"[import] working: {label} | {s['stage']} | {s['elapsed_seconds']}s / {s['limit_seconds']}s")
    next_beat=now+self.beat
 def close(self,error=None):
  self.stop.set();self.thread.join(.2)
  if self.timed_out:return
  self.state='CANCELLED' if isinstance(error,KeyboardInterrupt) else 'FAILED' if error else 'COMPLETE'
  self.save(True);self.io_stop.set();self.io_signal.set();self.writer.join(.25)

@contextlib.contextmanager
def session(base,cfg,options=None):
 global ACTIVE
 if ACTIVE is not None:yield ACTIVE;return
 probe=Probe(base,cfg,options);ACTIVE=probe;probe.writer.start();probe.thread.start();probe.save(True)
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
