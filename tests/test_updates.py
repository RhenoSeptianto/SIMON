import json,sqlite3,time,uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from tools.update_worker import Job,write_json,read_json,copy_database

class Driver:
 def __init__(self,config,fail=None):self.config=config;self.fail=fail;self.action={'root':'old','python':'old-python','arguments':'old-args'};self.running=True;self.starts=[]
 def current(self):return dict(self.action)
 def prepare(self,request):
  if self.fail=='prepare':raise RuntimeError('download failed')
  return {'root':'new','python':'new-python','arguments':'new-args'}
 def stop(self):self.running=False
 def configure(self,action):self.action=dict(action)
 def start(self):
  self.running=True;self.starts.append(self.action['root'])
  if self.action['root']=='new':
   with sqlite3.connect(self.config['database']) as db:db.execute('alter table records add column changed text');db.execute("update records set value='new'")
 def healthy(self,sha=None):
  if self.action['root']=='new' and self.fail in ('health','rollback'):raise RuntimeError('new server is unhealthy')
  if self.action['root']=='old' and self.fail=='rollback' and 'new' in self.starts:raise RuntimeError('old service cannot restart')

@pytest.fixture
def update_config(tmp_path):
 data=tmp_path/'data';data.mkdir();database=data/'siams.db'
 with sqlite3.connect(database) as db:db.execute('create table records(value text)');db.execute("insert into records values('old')")
 folder=data/'updater';folder.mkdir()
 write_json(folder/'current.json',{'sha':'a'*40,'health_sha':'a'*40,'root':'old','python':'old-python'})
 return {'database':str(database),'folder':str(folder),'data':str(data)}

def request():return {'id':uuid.uuid4().hex,'target':'b'*40}

def test_update_success_keeps_backup_and_switches_version(update_config):
 driver=Driver(update_config);job=Job(update_config);job.run(request(),driver)
 folder=Path(update_config['folder']);status=read_json(folder/'status.json')
 assert status['state']=='success' and driver.action['root']=='new' and driver.running
 assert read_json(folder/'current.json')['sha']=='b'*40 and not (folder/'maintenance.json').exists()
 backup=Path(read_json(folder/'journal.json')['backup'])
 with sqlite3.connect(backup) as db:assert db.execute('select value from records').fetchone()[0]=='old'

def test_failed_update_restores_database_schema_and_old_environment(update_config):
 driver=Driver(update_config,'health');Job(update_config).run(request(),driver)
 folder=Path(update_config['folder'])
 assert read_json(folder/'status.json')['state']=='rolled_back'
 assert driver.action=={'root':'old','python':'old-python','arguments':'old-args'} and driver.running
 with sqlite3.connect(update_config['database']) as db:
  assert db.execute('select value from records').fetchone()[0]=='old'
  assert [row[1] for row in db.execute('pragma table_info(records)')]==['value']
 assert read_json(folder/'current.json')['sha']=='a'*40 and not (folder/'maintenance.json').exists()

def test_prepare_failure_never_stops_server_or_touches_database(update_config):
 driver=Driver(update_config,'prepare');Job(update_config).run(request(),driver)
 assert driver.running and driver.action['root']=='old' and driver.starts==[]
 assert read_json(Path(update_config['folder'])/'status.json')['state']=='failed'

def test_rollback_failure_stays_in_maintenance_and_does_not_claim_success(update_config):
 driver=Driver(update_config,'rollback')
 with pytest.raises(RuntimeError):Job(update_config).run(request(),driver)
 folder=Path(update_config['folder'])
 assert read_json(folder/'status.json')['state']=='rollback_failed' and (folder/'maintenance.json').exists()
 assert read_json(folder/'journal.json')['phase']!='complete'

def test_boot_recovers_interrupted_schema_change(update_config):
 folder=Path(update_config['folder']);driver=Driver(update_config)
 previous=driver.current();backup=folder/'before.db';copy_database(update_config['database'],backup)
 write_json(folder/'journal.json',{'phase':'installing','backup':str(backup),'previous_action':previous,'previous_sha':'a'*40,'previous_current':read_json(folder/'current.json')})
 write_json(folder/'maintenance.json',{})
 driver.configure({'root':'new','python':'new-python','arguments':'new'});driver.start()
 Job(update_config).recover(driver)
 assert read_json(folder/'status.json')['state']=='rolled_back' and driver.action==previous
 with sqlite3.connect(update_config['database']) as db:assert db.execute('select value from records').fetchone()[0]=='old'


def test_update_endpoints_require_super_admin_and_csrf_and_queue_once(tmp_path,monkeypatch):
 import backend.main as backend
 import backend.updates as updates
 from types import SimpleNamespace
 data=tmp_path/'data';base=data/'updater';base.mkdir(parents=True)
 monkeypatch.setattr(backend,'DATA',data)
 write_json(base/'config.json',{'database':str(Path(backend.engine.url.database).resolve()),'folder':str(base)})
 (base/'worker.py').write_text('# fixture');(base/'task-control.ps1').write_text('# fixture');write_json(base/'installed.json',{})
 write_json(base/'checked.json',{'latest':'b'*40,'available':True,'checked_at':time.time()})
 with backend.DB() as db:
  db.add_all([backend.User(name='Admin',username='updateadmin',password=backend.password('1'),role='super_admin',active=1),backend.User(name='TS',username='updatets',password=backend.password('1'),role='ts',active=1)]);db.commit()
 c=TestClient(backend.app)
 assert c.get('/api/system/update/status').status_code==401
 c.post('/api/login',json={'username':'updatets','password':'1'})
 for endpoint in ('status','log'):assert c.get('/api/system/update/'+endpoint).status_code==403
 assert c.post('/api/system/update/start',headers={'X-SIAMS-Request':'1'},json={'target':'b'*40}).status_code==403
 c.post('/api/login',json={'username':'updateadmin','password':'1'})
 assert c.post('/api/system/update/start',json={'target':'b'*40}).status_code==403
 calls=[]
 monkeypatch.setattr(updates.subprocess,'run',lambda args,**kw:(calls.append(args) or SimpleNamespace(returncode=0,stdout='',stderr='')))
 assert c.post('/api/system/update/start',headers={'X-SIAMS-Request':'1'},json={'target':'b'*40}).status_code==200
 queued=read_json(base/'status.json')
 assert queued['state']=='queued' and queued['started_at']<=queued['updated_at']
 assert calls==[['schtasks.exe','/Run','/TN','SIMONUpdater']]
 assert c.post('/api/system/update/start',headers={'X-SIAMS-Request':'1'},json={'target':'b'*40}).status_code==409
 write_json(base/'maintenance.json',{})
 assert c.post('/api/agent/enroll',json={}).status_code==503
 assert c.get('/api/system/update/status').status_code==200
 assert c.get('/api/health').status_code==200
 assert c.get('/api/me').status_code==200
 assert not (base/'backups').exists() # Web only queues; worker alone changes versions/database.

@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows worker file lock')
@pytest.mark.parametrize('outcome',['success','rolled_back'])
def test_completed_transaction_after_power_loss_never_reapplies_update(update_config,monkeypatch,outcome):
 import tools.update_worker as updater
 folder=Path(update_config['folder']);job_id=uuid.uuid4().hex
 current='b'*40 if outcome=='success' else 'a'*40
 write_json(folder/'current.json',{'sha':current})
 write_json(folder/'journal.json',{'phase':'complete','outcome':outcome,'target':'b'*40,'job_id':job_id})
 write_json(folder/'request.json',{'id':job_id,'target':'b'*40})
 write_json(folder/'status.json',{'state':'rolling_back' if outcome=='rolled_back' else 'verifying','job_id':job_id})
 write_json(folder/'maintenance.json',{})
 driver=Driver(update_config);monkeypatch.setattr(updater,'WindowsDriver',lambda c:driver)
 updater.worker(update_config)
 assert read_json(folder/'status.json')['state']==outcome and driver.starts==[]
 assert not (folder/'request.json').exists() and not (folder/'maintenance.json').exists()


def test_real_git_check_and_archive_do_not_overwrite_running_checkout(tmp_path,monkeypatch):
 import shutil
 import tools.update_worker as updater
 git_path=shutil.which('git')
 if not git_path:
  candidate=Path(__file__).resolve().parents[2]/'.tools'/'MinGit-2.56.0.4'/'cmd'/'git.exe'
  if candidate.exists():git_path=str(candidate)
 if not git_path:pytest.skip('Git unavailable')
 def run(*args,cwd=None):return updater.command([git_path,*args],cwd=cwd)
 author=tmp_path/'author';author.mkdir();run('init','-b','main',cwd=author);run('config','user.name','Test',cwd=author);run('config','user.email','test@example.invalid',cwd=author)
 (author/'VERSION').write_text('0.2.0');run('add','VERSION',cwd=author);run('commit','-m','old',cwd=author);old=run('rev-parse','HEAD',cwd=author)
 remote=tmp_path/'remote.git';run('clone','--bare',str(author),str(remote))
 (author/'VERSION').write_text('0.3.0');run('commit','-am','new release',cwd=author);new=run('rev-parse','HEAD',cwd=author);run('push',str(remote),'main',cwd=author)
 checkout=tmp_path/'checkout';run('clone',str(remote),str(checkout));run('checkout','--detach',old,cwd=checkout)
 folder=tmp_path/'updater';folder.mkdir();write_json(folder/'current.json',{'sha':old})
 config={'repo':str(checkout),'git':git_path,'folder':str(folder)}
 monkeypatch.setattr(updater,'assert_repo',lambda c:None) # Local bare fixture, not the live GitHub remote.
 result=updater.check_latest(config)
 assert result['available'] and result['latest']==new and result['latest_version']=='0.3.0'
 assert run('rev-parse','HEAD',cwd=checkout)==old and (checkout/'VERSION').read_text()=='0.2.0'
 destination=tmp_path/'candidate';updater.extract_commit(config,new,destination)
 assert (destination/'VERSION').read_text()=='0.3.0' and not (destination/'.git').exists()


def test_stage_uses_isolated_env_and_explicit_shared_database(tmp_path,monkeypatch):
 import tools.update_worker as updater
 folder=tmp_path/'updater';folder.mkdir()
 config={'folder':str(folder),'repo':str(tmp_path),'git':'git.exe','data':str(tmp_path/'shared-data'),'database':str(tmp_path/'shared-data'/'siams.db')}
 monkeypatch.setattr(updater,'assert_repo',lambda c:None)
 monkeypatch.setattr(updater,'git',lambda *a,**kw:'a'*40)
 def extract(c,sha,release):
  release.mkdir();(release/'requirements.txt').write_text('fastapi')
 monkeypatch.setattr(updater,'extract_commit',extract)
 calls=[]
 monkeypatch.setattr(updater,'command',lambda args,**kw:(calls.append((args,kw)) or ''))
 action=updater.WindowsDriver(config).prepare({'id':'b'*32,'target':'c'*40})
 assert str(folder/'releases') in action['python']
 assert '--database' in action['arguments'] and 'shared-data' in action['arguments']
 smoke=calls[-1][1]['env']
 assert smoke['SIAMS_DATA']!=config['data'] and str(folder/'checks') in smoke['SIAMS_DATA']
 assert 'DATABASE_URL' not in smoke


def test_helper_bootstrap_freezes_initial_source_for_first_rollback(tmp_path):
 import shutil
 from tools.setup_updater import install
 from tools.update_worker import command
 git_path=shutil.which('git')
 if not git_path:
  candidate=Path(__file__).resolve().parents[2]/'.tools'/'MinGit-2.56.0.4'/'cmd'/'git.exe'
  if candidate.exists():git_path=str(candidate)
 if not git_path:pytest.skip('Git unavailable')
 root=tmp_path/'repo';(root/'tools').mkdir(parents=True);(root/'deployment'/'server').mkdir(parents=True);(root/'backend').mkdir()
 (root/'tools'/'update_worker.py').write_text('# helper fixture')
 (root/'deployment'/'server'/'update-task-control.ps1').write_text('# task fixture')
 (root/'backend'/'main.py').write_text('# ORIGINAL APPLICATION')
 def run(*args):return command([git_path,*args],cwd=root)
 run('init','-b','main');run('config','user.name','Test');run('config','user.email','test@example.invalid');run('add','.');run('commit','-m','baseline');run('remote','add','origin','https://github.com/RhenoSeptianto/SIMON.git')
 data=tmp_path/'data';data.mkdir()
 with sqlite3.connect(data/'siams.db') as db:db.execute('create table records(value text)')
 state=tmp_path/'task.json';write_json(state,{'python':'python.exe','root':str(root),'arguments':'-m backend.run_server'})
 install(root,data,git_path,state)
 current=read_json(data/'updater'/'current.json');snapshot=Path(current['root'])
 assert snapshot!=root and '--database' in current['arguments']
 (root/'backend'/'main.py').write_text('# MODIFIED AFTER INSTALL')
 assert (snapshot/'backend'/'main.py').read_text()=='# ORIGINAL APPLICATION'
 assert (data/'updater'/'worker.py').exists() and (data/'updater'/'config.json').exists()

@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows worker lock')
def test_partial_request_after_crash_does_not_stick_or_start_update(update_config,monkeypatch):
 import tools.update_worker as updater
 folder=Path(update_config['folder']);(folder/'request.json').write_text('{')
 driver=Driver(update_config);monkeypatch.setattr(updater,'WindowsDriver',lambda c:driver)
 updater.worker(update_config)
 assert read_json(folder/'status.json')['state']=='failed' and driver.starts==[]
 assert not (folder/'request.json').exists() and list(folder.glob('request-invalid-*.json'))


def test_helper_health_check_rejects_wrong_process_version(monkeypatch):
 import io,hashlib,os
 from tools import server_healthcheck
 monkeypatch.setattr(server_healthcheck.ssl,'create_default_context',lambda **kw:object())
 expected=str(Path('fixture.db').resolve())
 payload={'ok':True,'version':'a'*40,'database_kind':'sqlite','database_id':hashlib.sha256(os.path.normcase(expected).encode()).hexdigest()}
 def response(*args,**kwargs):
  value=io.BytesIO(json.dumps(payload).encode());value.status=200;return value
 monkeypatch.setattr(server_healthcheck.urllib.request,'urlopen',response)
 assert server_healthcheck.check_https('fixture','https://localhost',attempts=1,expected_version='a'*40)==0
 assert server_healthcheck.check_https('fixture','https://localhost',attempts=1,expected_version='b'*40)==1

 assert server_healthcheck.check_https('fixture','https://localhost',attempts=1,expected_database=expected)==0
 assert server_healthcheck.check_https('fixture','https://localhost',attempts=1,expected_database=expected+'.other')==1
 payload['database_kind']='postgresql'
 assert server_healthcheck.check_https('fixture','https://localhost',attempts=1,expected_database=expected)==1
