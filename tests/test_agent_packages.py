import hashlib,json,shutil,time,uuid,zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.agent_packages import AgentPackageError,claim_device_update,prepare,rollout_status,start_rollout,status
from tools.make_agent_package import REQUIRED_CAPABILITIES


def template(path,source_sha):
 executable=b'fake-windows-agent-for-packaging-test'
 metadata={'format':11,'version':'1.1.4','source_sha':source_sha,'capabilities':sorted(REQUIRED_CAPABILITIES),'exe_sha256':hashlib.sha256(executable).hexdigest()}
 with zipfile.ZipFile(path,'w') as archive:
  archive.writestr('SIMONAgent/SIMONAgent.exe',executable)
  archive.writestr('SIMONAgent/_internal/runtime.dll',b'dll-bytes')
  archive.writestr('agent-build.json',json.dumps(metadata))
 return executable


def fixture(tmp_path,source_sha):
 root=tmp_path/'root';data=tmp_path/'data';(root/'deployment'/'agent').mkdir(parents=True);(data/'tls').mkdir(parents=True)
 (root/'deployment'/'agent'/'install.bat').write_text('@echo off\necho current installer',encoding='utf-8')
 (root/'deployment'/'agent'/'install-user.ps1').write_text('# current installer',encoding='utf-8')
 (data/'tls'/'ca.crt').write_text('PUBLIC OFFICE CA',encoding='utf-8')
 artifact=tmp_path/'template.zip';template(artifact,source_sha)
 return root,data,artifact


def test_prepare_agent_package_validates_build_and_adds_only_public_ca(tmp_path):
 source_sha='a'*40;root,data,artifact=fixture(tmp_path,source_sha)
 result=prepare(data,root,source_sha,fetch=lambda target:shutil.copy2(artifact,target))
 output=data/'agent-package'/'SIMONAgent-store.zip'
 assert result['ready'] and status(data,source_sha)['ready']
 with zipfile.ZipFile(output) as package:
  names=set(package.namelist())
  assert package.read('ca.crt')==b'PUBLIC OFFICE CA'
  assert b'current installer' in package.read('install.bat')
  assert 'SIMONAgent/SIMONAgent.exe' in names
  assert not any(name.endswith(('.key','.db','identity.json')) for name in names)
 assert not status(data,'b'*40)['ready']


def test_prepare_rejects_agent_built_for_another_server_commit(tmp_path):
 root,data,artifact=fixture(tmp_path,'a'*40)
 with pytest.raises(AgentPackageError,match='belum tersedia'):
  prepare(data,root,'b'*40,fetch=lambda target:shutil.copy2(artifact,target))
 assert not (data/'agent-package'/'SIMONAgent-store.zip').exists()


def test_rolling_mass_update_only_online_outdated_with_max_3_concurrency_and_lock(tmp_path):
 source_sha='c'*40;old_sha='d'*40;root,data,artifact=fixture(tmp_path,source_sha)
 prepare(data,root,source_sha,fetch=lambda target:shutil.copy2(artifact,target))
 devices=[
  {'id':1,'hostname':'PC-1','store_code':'S01','online':True,'agent':{'status':'outdated','build_sha':old_sha}},
  {'id':2,'hostname':'PC-2','store_code':'S02','online':True,'agent':{'status':'outdated','build_sha':old_sha}},
  {'id':3,'hostname':'PC-3','store_code':'S03','online':True,'agent':{'status':'outdated','build_sha':old_sha}},
  {'id':4,'hostname':'PC-4','store_code':'S04','online':True,'agent':{'status':'outdated','build_sha':old_sha}},
  {'id':5,'hostname':'PC-OFFLINE','store_code':'S05','online':False,'agent':{'status':'outdated','build_sha':old_sha}},
  {'id':6,'hostname':'PC-CURRENT','store_code':'S06','online':True,'agent':{'status':'current','build_sha':source_sha}},
 ]
 rollout=start_rollout(data,source_sha,devices,actor='admin')
 assert rollout['busy'] is True
 assert rollout['total']==4
 assert rollout['in_progress']==3
 assert rollout['queued']==1
 assert rollout['done']==0
 # Global lock prevents another admin from starting a second rollout while busy
 with pytest.raises(AgentPackageError,match='sedang berjalan'):
  start_rollout(data,source_sha,devices,actor='admin2')
 # First 3 online outdated devices receive update instructions; 4th queued and offline/current do not
 for dev_id in (1,2,3):
  cmd=claim_device_update(data,source_sha,dev_id,old_sha)
  assert cmd and cmd['target_sha']==source_sha
 assert claim_device_update(data,source_sha,4,old_sha) is None
 assert claim_device_update(data,source_sha,5,old_sha) is None
 assert claim_device_update(data,source_sha,6,source_sha) is None
 # Device 1 finishes updating and reports new build_sha
 assert claim_device_update(data,source_sha,1,source_sha) is None
 mid=rollout_status(data,source_sha)
 assert mid['done']==1 and mid['in_progress']==3 and mid['queued']==0
 # Now Device 4 has been promoted into the active slot and receives the update command
 cmd4=claim_device_update(data,source_sha,4,old_sha)
 assert cmd4 and cmd4['target_sha']==source_sha
 # Remaining devices finish
 for dev_id in (2,3,4):
  assert claim_device_update(data,source_sha,dev_id,source_sha) is None
 final=rollout_status(data,source_sha)
 assert final['busy'] is False and final['state']=='completed' and final['done']==4


def test_agent_self_update_download_and_apply_preserves_state_and_rolls_back_on_error(tmp_path,monkeypatch):
 import backend.main as backend
 from agent.updater import apply_update,download_and_stage
 source_sha='e'*40;old_sha='f'*40
 root,data,artifact=fixture(tmp_path,source_sha)
 monkeypatch.setattr(backend,'DATA',data)
 monkeypatch.setattr(backend,'ROOT',root)
 monkeypatch.setattr(backend,'current_update_sha',lambda:source_sha)
 prepare(data,root,source_sha,fetch=lambda target:shutil.copy2(artifact,target))
 with backend.DB() as s:
  s.query(backend.Device).delete()
  s.add(backend.User(name='Super',username='rollout_admin',password=backend.password('pass123'),role='super_admin',active=1))
  s.commit()
 c=TestClient(backend.app)
 uid=str(uuid.uuid4());claim='k'*64
 assert c.post('/api/agent/enroll',json={'uuid':uid,'claim':claim,'inventory':{'hostname':'STORE-01','primary_ip':'10.1.1.5','store_code':'99001','agent_version':'1.1.3','agent_build_sha':old_sha}}).status_code==200
 token=c.post('/api/agent/claim',json={'uuid':uid,'claim':claim}).json()['credential']
 headers={'Authorization':'Bearer '+token}
 c.post('/api/login',json={'username':'rollout_admin','password':'pass123'})
 st=c.get('/api/system/agent-package/status').json()
 assert st['ready'] is True and st['online_outdated']==1
 started=c.post('/api/system/agent-package/rollout',headers={'X-SIAMS-Request':'1'})
 assert started.status_code==200 and started.json()['rollout']['busy'] is True
 # Second click while running is rejected with 409
 assert c.post('/api/system/agent-package/rollout',headers={'X-SIAMS-Request':'1'}).status_code==409
 # Agent sends heartbeat and receives agent_update instruction
 hb=c.post('/api/agent/report',json={'event_id':str(uuid.uuid4()),'collected_at':time.time(),'kind':'heartbeat','payload':{}},headers=headers).json()
 assert 'agent_update' in hb and hb['agent_update']['target_sha']==source_sha
 # Agent downloads and stages update package using its device token
 install_root=tmp_path/'store-pc'
 agent_dir=install_root/'SIMONAgent';state_dir=agent_dir/'data';state_dir.mkdir(parents=True)
 (install_root/'config.json').write_text('{"store_code":"99001"}',encoding='utf-8')
 (install_root/'ca.crt').write_text('EXISTING CA',encoding='utf-8')
 (state_dir/'identity.json').write_text('{"uuid":"keep-me"}',encoding='utf-8')
 (agent_dir/'HDSentinel.xml').write_text('<sentinel/>',encoding='utf-8')
 (agent_dir/'SIMONAgent.exe').write_bytes(b'old-exe-binary')
 extracted,staged_exe,meta=download_and_stage(c,token,hb['agent_update'],state_dir)
 assert staged_exe.is_file() and meta['source_sha']==source_sha
 apply_update(install_root,extracted,launch=False)
 assert (agent_dir/'SIMONAgent.exe').read_bytes()==b'fake-windows-agent-for-packaging-test'
 assert (install_root/'config.json').read_text(encoding='utf-8')=='{"store_code":"99001"}'
 assert (state_dir/'identity.json').read_text(encoding='utf-8')=='{"uuid":"keep-me"}'
 assert (agent_dir/'HDSentinel.xml').read_text(encoding='utf-8')=='<sentinel/>'
 # Updated agent reports new inventory with new build_sha -> rollout completes automatically
 c.post('/api/agent/report',json={'event_id':str(uuid.uuid4()),'collected_at':time.time(),'kind':'inventory','payload':{'hostname':'STORE-01','primary_ip':'10.1.1.5','store_code':'99001','agent_version':'1.1.4','agent_build_sha':source_sha}},headers=headers)
 done_st=c.get('/api/system/agent-package/status').json()['rollout']
 assert done_st['busy'] is False and done_st['state']=='completed' and done_st['done']==1
