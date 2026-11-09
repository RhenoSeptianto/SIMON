"""Standalone updater worker. Copied outside releases; uses only the Python standard library."""
import argparse,contextlib,hashlib,json,os,re,sqlite3,ssl,subprocess,sys,tarfile,time,urllib.request,uuid
from pathlib import Path

BUSY={'queued','preparing','stopping','backup','installing','verifying','rolling_back'}
TERMINAL={'success','failed','rolled_back','rollback_failed'}

def read_json(path,default=None):
 try:return json.loads(Path(path).read_text(encoding='utf-8-sig'))
 except FileNotFoundError:return {} if default is None else default

def write_json(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 for attempt in range(20):
  try:temporary.replace(path);break
  except PermissionError:
   if attempt==19:raise
   time.sleep(.05)

def command(args,cwd=None,timeout=60,env=None):
 result=subprocess.run([str(a) for a in args],cwd=cwd,env=env or {**os.environ,'GIT_TERMINAL_PROMPT':'0'},capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if result.returncode:raise RuntimeError((result.stderr or result.stdout or 'Perintah gagal')[-2500:].strip())
 return result.stdout.strip()

def git(config,*args,timeout=60):return command([config['git'], '-c','safe.directory='+config['repo'],*args],cwd=config['repo'],timeout=timeout)

def assert_repo(config):
 remote=git(config,'remote','get-url','origin')
 if remote.rstrip('/').removesuffix('.git').casefold()!='https://github.com/rhenoseptianto/simon':raise ValueError('Remote origin harus https://github.com/RhenoSeptianto/SIMON.git')
 if git(config,'status','--porcelain','--untracked-files=no'):raise ValueError('Ada perubahan source lokal yang belum disimpan. Update dibatalkan tanpa menimpa file.')

def check_latest(config):
 assert_repo(config)
 git(config,'fetch','--no-tags','origin','main',timeout=90)
 latest=git(config,'rev-parse','FETCH_HEAD')
 current=read_json(Path(config['folder'])/'current.json').get('sha') or git(config,'rev-parse','HEAD')
 if not re.fullmatch('[0-9a-f]{40}',latest):raise ValueError('Commit Git tidak valid')
 try:version=git(config,'show',latest+':VERSION')
 except RuntimeError:version=latest[:8]
 notes=git(config,'log','--format=%h %s','-8',current+'..'+latest) if current!=latest else ''
 result={'current':current,'latest':latest,'available':current!=latest,'latest_version':version[:60],'changes':notes.splitlines(),'checked_at':time.time()}
 write_json(Path(config['folder'])/'checked.json',result)
 return result

def copy_database(source,target):
 source=Path(source);target=Path(target)
 if not source.is_file():raise RuntimeError('Database SQLite sumber tidak ditemukan: '+str(source))
 with contextlib.closing(sqlite3.connect(source)) as src,contextlib.closing(sqlite3.connect(target)) as dst:
  src.backup(dst)
  if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Pemeriksaan backup database gagal')

def extract_commit(config,sha,target):
 target=Path(target);target.mkdir(parents=True,exist_ok=False)
 archive=target.parent/(target.name+'.tar')
 with archive.open('wb') as output:
  process=subprocess.run([config['git'],'-c','safe.directory='+config['repo'],'archive','--format=tar',sha],cwd=config['repo'],stdout=output,stderr=subprocess.PIPE,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if process.returncode:raise RuntimeError('Gagal mengekstrak commit: '+process.stderr.decode(errors='replace')[-1000:])
 with tarfile.open(archive) as package:
  members=package.getmembers()
  for member in members:
   if not (target/member.name).resolve().is_relative_to(target.resolve()) or not (member.isfile() or member.isdir()):raise RuntimeError('Arsip Git berisi path/link yang tidak diizinkan')
  package.extractall(target,members=members,filter='data')
 archive.unlink()

class WindowsDriver:
 def __init__(self,config):self.config=config
 def task(self,operation,action=None):
  c=self.config;args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path(c['folder'])/'task-control.ps1'),'-Operation',operation]
  if action:args+=['-Python',action['python'],'-Root',action['root'],'-Arguments',action['arguments']]
  output=command(args,timeout=90)
  return json.loads(output) if operation=='Get' else None
 def current(self):
  action=self.task('Get')
  if not Path(action.get('python','')).is_file() or not Path(action.get('root','')).is_dir() or 'backend.run_server' not in action.get('arguments',''):raise RuntimeError('Konfigurasi task server lama tidak dapat dipulihkan dengan aman. Periksa setup server.')
  return action
 def stop(self):self.task('Stop')
 def configure(self,action):self.task('Set',action)
 def start(self):self.task('Start')
 def prepare(self,request):
  c=self.config;sha=request['target'];assert_repo(c)
  git(c,'fetch','--no-tags','origin','main',timeout=90)
  git(c,'merge-base','--is-ancestor',sha,'FETCH_HEAD')
  old=read_json(Path(c['folder'])/'current.json').get('sha') or git(c,'rev-parse','HEAD')
  git(c,'merge-base','--is-ancestor',old,sha)
  release=Path(c['folder'])/'releases'/(sha[:12]+'-'+request['id'][:8])
  release.parent.mkdir(parents=True,exist_ok=True);extract_commit(c,sha,release)
  python=release/'.venv'/'Scripts'/'python.exe'
  command([sys.executable,'-m','venv',str(release/'.venv')],timeout=180)
  command([python,'-m','pip','install','--disable-pip-version-check','-r',str(release/'requirements.txt')],cwd=release,timeout=1200)
  command([python,'-m','pip','check'],cwd=release,timeout=90)
  smoke=Path(c['folder'])/'checks'/request['id'];smoke.mkdir(parents=True,exist_ok=True)
  env={**os.environ,'SIAMS_DATA':str(smoke),'SIAMS_BUILD_SHA':sha};env.pop('DATABASE_URL',None)
  code="from fastapi.testclient import TestClient;from backend.main import app;c=TestClient(app);r=c.get('/api/health');assert r.status_code==200 and r.json()['ok'];assert c.get('/api/system/update/status').status_code==401;assert c.get('/static/updates.js').status_code==200"
  command([python,'-c',code],cwd=release,timeout=120,env=env)
  return {'python':str(python),'root':str(release),'arguments':subprocess.list2cmdline(['-m','backend.run_server','--data',c['data'],'--database',c['database'],'--version',sha])}
 def healthy(self,sha=None):
  c=self.config;context=ssl.create_default_context(cafile=str(Path(c['data'])/'tls'/'ca.crt'))
  for _ in range(40):
   try:
    with urllib.request.urlopen(c.get('health_url','https://127.0.0.1:8443/api/health'),context=context,timeout=3) as response:payload=json.load(response)
    database_id=hashlib.sha256(os.path.normcase(str(Path(c['database']).resolve())).encode()).hexdigest()
    if payload.get('ok') and payload.get('database_kind')=='sqlite' and payload.get('database_id')==database_id and (sha is None or payload.get('version')==sha):return
   except Exception:pass
   time.sleep(1)
  raise RuntimeError('SIMON tidak lolos pemeriksaan HTTPS/versi setelah dinyalakan')

class Job:
 def __init__(self,config):
  self.config=config;self.folder=Path(config['folder']);self.folder.mkdir(parents=True,exist_ok=True)
 def status(self,state,message,**extra):
  previous=read_json(self.folder/'status.json')
  previous.update(state=state,message=message,updated_at=time.time(),**extra);write_json(self.folder/'status.json',previous)
  path=self.folder/'update.log'
  if path.exists() and path.stat().st_size>3*1024*1024:path.replace(self.folder/'update.previous.log')
  with path.open('a',encoding='utf-8') as stream:stream.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+state+' '+message+'\n')
 def rollback(self,journal,driver,cause):
  self.status('rolling_back','Update gagal. Memulihkan versi sebelumnya.',error=str(cause))
  try:
   driver.stop()
   if journal.get('backup') and Path(journal['backup']).is_file():copy_database(journal['backup'],self.config['database'])
   driver.configure(journal['previous_action']);driver.start();driver.healthy(journal.get('previous_sha'))
   write_json(self.folder/'current.json',journal['previous_current'])
   journal.update(phase='complete',outcome='rolled_back',error=str(cause));write_json(self.folder/'journal.json',journal)
   self.status('rolled_back','Update gagal, versi sebelumnya berhasil dipulihkan.',error=str(cause))
   (self.folder/'maintenance.json').unlink(missing_ok=True)
  except Exception as failure:
   self.status('rollback_failed','Pemulihan belum berhasil. Akses perubahan data tetap dihentikan; periksa log.',error=str(cause),rollback_error=str(failure))
   raise
 def run(self,request,driver):
  self.status('preparing','Menyiapkan versi baru. Versi lama masih berjalan.',job_id=request['id'],target=request['target'],error=None,rollback_error=None)
  journal=None
  try:
   action=driver.prepare(request)
   previous=read_json(self.folder/'current.json')
   driver.healthy(previous.get('health_sha'))
   journal={'phase':'stopping','previous_action':driver.current(),'previous_sha':previous.get('health_sha'),'previous_current':previous,'job_id':request['id'],'target':request['target']}
   write_json(self.folder/'journal.json',journal)
   write_json(self.folder/'maintenance.json',{'job_id':request['id']})
   self.status('stopping','Menghentikan server sementara untuk backup dan pemasangan.')
   driver.stop()
   self.status('backup','Membuat backup database sebelum perubahan.')
   backup=self.folder/'backups'/request['id'];backup.mkdir(parents=True,exist_ok=True)
   temporary=backup/'database.tmp';copy_database(self.config['database'],temporary);temporary.replace(backup/'database.db')
   journal.update(backup=str(backup/'database.db'),phase='installing');write_json(self.folder/'journal.json',journal)
   self.status('installing','Memasang dan menjalankan versi baru.')
   driver.configure(action);driver.start()
   self.status('verifying','Memeriksa server dan versi baru lewat HTTPS.')
   driver.healthy(request['target'])
   write_json(self.folder/'current.json',{'sha':request['target'],'health_sha':request['target'],'root':action['root'],'python':action['python'],'arguments':action['arguments'],'installed_at':time.time()})
   # Mark the transaction complete before reopening writes; boot recovery must not undo a completed update.
   journal.update(phase='complete',outcome='success');write_json(self.folder/'journal.json',journal)
   self.status('success','Update berhasil. Server sudah siap digunakan.',current=request['target'])
   (self.folder/'maintenance.json').unlink(missing_ok=True)
  except Exception as error:
   if journal:self.rollback(journal,driver,error)
   else:self.status('failed','Update dibatalkan. Versi lama tetap berjalan.',error=str(error))
 def recover(self,driver):
  journal=read_json(self.folder/'journal.json')
  if journal and journal.get('phase')!='complete':self.rollback(journal,driver,'Proses update sebelumnya terputus; pemulihan saat startup.')
  elif journal.get('phase')=='complete':(self.folder/'maintenance.json').unlink(missing_ok=True)

def worker(config):
 folder=Path(config['folder']);folder.mkdir(parents=True,exist_ok=True)
 # OS file lock is released even on crash; a leftover file never permanently blocks recovery.
 import msvcrt
 with (folder/'worker.lock').open('a+b') as lock:
  lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
  try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:return
  job=Job(config);driver=WindowsDriver(config)
  existing=read_json(folder/'journal.json')
  if existing and existing.get('phase')!='complete':
   job.recover(driver);(folder/'request.json').unlink(missing_ok=True);return
  try:request=read_json(folder/'request.json')
  except (ValueError,UnicodeError):
   (folder/'request.json').replace(folder/('request-invalid-'+str(time.time_ns())+'.json'))
   job.status('failed','Antrean update terputus/tidak valid. Versi lama tidak diubah; klik Cek update kembali.');return
  if existing.get('phase')=='complete':
   status=read_json(folder/'status.json')
   interrupted=(request and existing.get('job_id')==request.get('id')) or (not request and status.get('job_id')==existing.get('job_id') and status.get('state') in BUSY)
   if interrupted:
    outcome=existing.get('outcome','success' if read_json(folder/'current.json').get('sha')==existing.get('target') else 'rolled_back')
    job.status(outcome,'Update berhasil. Server sudah siap digunakan.' if outcome=='success' else 'Update gagal, versi sebelumnya berhasil dipulihkan.',error=existing.get('error'))
    (folder/'maintenance.json').unlink(missing_ok=True)
    (folder/'request.json').unlink(missing_ok=True);return
   (folder/'maintenance.json').unlink(missing_ok=True)
  if not request:
   if read_json(folder/'status.json').get('state') in BUSY:job.status('failed','Pekerjaan sebelumnya terputus sebelum pemasangan. Periksa log lalu Cek update kembali.')
   return
  try:
   if not re.fullmatch('[0-9a-f]{32}',request.get('id','')):raise ValueError('ID update tidak valid')
   if not re.fullmatch('[0-9a-f]{40}',request.get('target','')):raise ValueError('Commit update tidak valid')
   status=read_json(folder/'status.json')
   if status.get('job_id')==request['id'] and status.get('state') in TERMINAL:return
   job.run(request,driver)
  except Exception as error:
   if read_json(folder/'status.json').get('state')!='rollback_failed':job.status('failed','Helper gagal menjalankan pekerjaan. Periksa log.',error=str(error))
   raise
  finally:(folder/'request.json').unlink(missing_ok=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);args=parser.parse_args()
 worker(read_json(args.config))
