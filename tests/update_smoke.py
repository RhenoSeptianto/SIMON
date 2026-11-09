"""Actual SIMON HTTPS/Git/SQLite update and rollback smoke; isolated, no Windows tasks installed."""
import os,sys,tempfile,socket,subprocess,sqlite3,json,time,ssl,urllib.request,shutil,uuid,hashlib,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.update_worker import Job,write_json,read_json,extract_commit,command,WindowsDriver
from tools.package_source import source_files
from tools.server_setup import generate_tls
import httpx

sandbox=Path(tempfile.mkdtemp(prefix='simon-update-smoke-'));repo=sandbox/'repo';repo.mkdir()
git=ROOT.parent/'.tools'/'MinGit-2.56.0.4'/'cmd'/'git.exe'
if not git.exists():
 git=shutil.which('git')
 if not git:raise SystemExit('Git diperlukan untuk smoke test')
def g(*args):return command([git,*args],cwd=repo)
for file in source_files(ROOT):
 target=repo/file.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
g('init','-b','main');g('config','user.name','SIMON Test');g('config','user.email','test@example.invalid');g('add','.');g('commit','-m','old server');old=g('rev-parse','HEAD')
(repo/'VERSION').write_text('9.9.9-test\n');g('commit','-am','good release');good=g('rev-parse','HEAD')
with (repo/'backend'/'main.py').open('a',encoding='utf-8') as file:
 file.write('''
# Deliberate fixture: fresh-DB preflight passes, existing-DB migration fails.
with DB() as _check: _existing_device=_check.query(Device).first() is not None
if _existing_device:
 with engine.begin() as _connection:
  _connection.execute(text('CREATE TABLE simulated_failed_migration(id INTEGER)'))
  _connection.execute(text("UPDATE devices SET hostname='DAMAGED'"))
 raise RuntimeError('Deliberate existing-database migration failure')
''')
g('commit','-am','bad existing database migration');bad=g('rev-parse','HEAD')
data=sandbox/'data';data.mkdir();generate_tls(data/'tls')
folder=data/'updater';folder.mkdir();config={'repo':str(repo),'git':str(git),'database':str(data/'siams.db'),'folder':str(folder),'data':str(data)}
s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
url=f'https://127.0.0.1:{port}';config['health_url']=url+'/api/health';context=ssl.create_default_context(cafile=str(data/'tls'/'ca.crt'))
class ProcessDriver:
 def __init__(self):self.action=None;self.process=None
 def current(self):return dict(self.action)
 def prepare(self,request):
  release=sandbox/'releases'/request['id'];extract_commit(config,request['target'],release)
  check=sandbox/'checks'/request['id'];check.mkdir(parents=True)
  env={**os.environ,'SIAMS_DATA':str(check),'SIAMS_BUILD_SHA':request['target']};env.pop('DATABASE_URL',None)
  command([sys.executable,'-c',"from fastapi.testclient import TestClient;from backend.main import app;assert TestClient(app).get('/api/health').status_code==200"],cwd=release,env=env,timeout=45)
  return {'root':str(release),'python':sys.executable,'arguments':'test HTTPS runner','sha':request['target']}
 def configure(self,action):self.action=dict(action)
 def start(self):
  env={**os.environ,'SIAMS_DATA':str(data),'DATABASE_URL':'sqlite:///'+str(data/'siams.db'),'SIAMS_BUILD_SHA':self.action['sha'],'SIAMS_PRODUCTION':'1'}
  args=[self.action['python'],'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',str(port),'--ssl-keyfile',str(data/'tls'/'server.key'),'--ssl-certfile',str(data/'tls'/'server.crt'),'--no-access-log']
  self.process=subprocess.Popen(args,cwd=self.action['root'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 def stop(self):
  if self.process and self.process.poll() is None:self.process.terminate();self.process.wait(timeout=10)
 def healthy(self,sha=None):
  for _ in range(60):
   if self.process.poll() is not None:raise RuntimeError('Candidate process exited')
   try:
    with urllib.request.urlopen(url+'/api/health',context=context,timeout=1) as response:payload=json.load(response)
    if payload['ok'] and (sha is None or payload['version']==sha):return
   except OSError:pass
   time.sleep(.1)
  raise RuntimeError('HTTPS health timeout')

driver=ProcessDriver()
try:
 driver.configure(driver.prepare({'id':'initial','target':old}));driver.start();driver.healthy(old)
 salt=secrets.token_hex(16);password=salt+':'+hashlib.scrypt(b'qa',salt=salt.encode(),n=16384,r=8,p=1).hex()
 with sqlite3.connect(data/'siams.db') as db:db.execute('insert into users(name,username,password,role,active,stores) values(?,?,?,?,?,?)',('Smoke Admin','smokeadmin',password,'super_admin',1,'[]'))
 uid=str(uuid.uuid4())
 with httpx.Client(base_url=url,verify=context,timeout=10) as client:
  client.post('/api/agent/enroll',json={'uuid':uid,'claim':'x'*64,'inventory':{'hostname':'PRESERVED-PC','store_code':'TEST-001','bios_serial':'SMOKE-SERIAL'}}).raise_for_status()
  client.post('/api/login',json={'username':'smokeadmin','password':'qa'}).raise_for_status()
  write_json(folder/'current.json',{'sha':old,'health_sha':old,'root':driver.action['root'],'python':sys.executable})
  Job(config).run({'id':'good','target':good},driver)
  assert read_json(folder/'status.json')['state']=='success';driver.healthy(good);WindowsDriver(config).healthy(good)
  response=client.get('/api/devices');response.raise_for_status();assert response.json()['items'][0]['hostname']=='PRESERVED-PC'
  assert client.get('/api/system/update/status').json()['version']=='9.9.9-test'
  good_action=driver.current()
  print('PASS: actual SIMON Git release/HTTPS update succeeds; account/session/device preserved and new web version served.',flush=True)
  Job(config).run({'id':'bad','target':bad},driver)
  assert read_json(folder/'status.json')['state']=='rolled_back' and driver.current()==good_action;driver.healthy(good);WindowsDriver(config).healthy(good)
  response=client.get('/api/devices');response.raise_for_status();assert response.json()['items'][0]['hostname']=='PRESERVED-PC'
  with sqlite3.connect(data/'siams.db') as db:assert db.execute("select count(*) from sqlite_master where name='simulated_failed_migration'").fetchone()[0]==0
  assert not (folder/'maintenance.json').exists()
  print('PASS: candidate passed fresh-DB preflight but damaged existing DB and crashed; previous SIMON, data/schema, login session and HTTPS restored.',flush=True)
  print('Temporary test directory:',sandbox,flush=True)
finally:driver.stop()
