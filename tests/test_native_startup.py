import json,os
from pathlib import Path
import pytest
from agent.user_startup import install

@pytest.mark.skipif(os.name!='nt',reason='Real Windows COM shortcut')
def test_native_install_real_shortcut_migrates_identity_and_keeps_config(tmp_path,monkeypatch):
 import win32com.client
 root=tmp_path/'paket agent';(root/'SIMONAgent').mkdir(parents=True)
 exe=root/'SIMONAgent'/'SIMONAgent.exe';exe.write_bytes(b'fixture')
 (root/'ca.crt').write_text('public ca')
 legacy=tmp_path/'local';state=legacy/'SIMON'/'data';state.mkdir(parents=True)
 (state/'identity.json').write_text('{"uuid":"same-PC-A31","claim":"test-claim"}')
 monkeypatch.setenv('LOCALAPPDATA',str(legacy))
 monkeypatch.setattr('agent.user_startup.conflicting_agent',lambda server:None)
 from types import SimpleNamespace
 class Client:
  def __init__(self,**kwargs):pass
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def post(self,*args,**kwargs):return SimpleNamespace(status_code=200,is_success=True)
 monkeypatch.setattr('httpx.Client',Client)
 monkeypatch.setattr('agent.config.tls_context',lambda *a:True)
 monkeypatch.setattr('agent.collectors.inventory',lambda:{'hostname':'TEST-PC','bios_serial':'TEST-SERIAL'})
 startup=tmp_path/'fake-startup';startup.mkdir()
 install(root,'A31',startup=startup,launch=False)
 link=win32com.client.Dispatch('WScript.Shell').CreateShortCut(str(startup/'SIMON Agent.lnk'))
 assert Path(link.TargetPath)==exe
 assert '--background --config' in link.Arguments and 'powershell' not in link.TargetPath.lower()
 assert json.loads((root/'SIMONAgent'/'data'/'identity.json').read_text())['uuid']=='same-PC-A31'
 install(root,'B32',startup=startup,launch=False)
 assert json.loads((root/'config.json').read_text())['store_code']=='B32'
 assert json.loads((root/'SIMONAgent'/'data'/'identity.json').read_text())['uuid']=='same-PC-A31'
 assert (root/'install-user.log').exists()


def test_user_startup_refuses_running_legacy_service(monkeypatch):
 from agent import user_startup
 monkeypatch.setattr(user_startup,'active_service',lambda:'D:\\old\\SIMONAgent.exe --service')
 assert 'Service SIMONAgent masih aktif' in user_startup.conflicting_agent('https://172.18.123.92:8443')
 assert user_startup.conflicting_agent('https://127.0.0.1:9988') is None


def test_user_startup_detects_legacy_other_folder_same_server(tmp_path,monkeypatch):
 from agent import user_startup
 import psutil
 from types import SimpleNamespace
 monkeypatch.setattr(user_startup,'active_service',lambda:None)
 file=tmp_path/'legacy-config.json';file.write_text(json.dumps({'server':'https://172.18.123.92:8443'}))
 process=SimpleNamespace(pid=987654,info={'pid':987654,'name':'SIMONAgent.exe','cmdline':['D:/old/SIMONAgent.exe','--config',str(file)]})
 monkeypatch.setattr(psutil,'process_iter',lambda *a:[process])
 assert 'Agent lain masih aktif' in user_startup.conflicting_agent('https://172.18.123.92:8443')
 assert user_startup.conflicting_agent('https://another-server:8443') is None

@pytest.mark.skipif(os.name!='nt',reason='Real Windows COM shortcut')
def test_installer_recovers_legacy_copied_identity_without_overwriting_other_pc(tmp_path,monkeypatch):
 from types import SimpleNamespace
 import httpx
 root=tmp_path/'copied';state=root/'SIMONAgent'/'data';state.mkdir(parents=True)
 (root/'SIMONAgent'/'SIMONAgent.exe').write_bytes(b'fixture');(root/'ca.crt').write_text('ca')
 original={'uuid':'11111111-1111-1111-1111-111111111111','claim':'c'*64}
 (state/'identity.json').write_text(json.dumps(original));(state/'queue.db').write_bytes(b'foreign queue')
 monkeypatch.setattr('agent.user_startup.conflicting_agent',lambda server:None)
 monkeypatch.setattr('agent.collectors.inventory',lambda:{'hostname':'NEW-PC','bios_serial':'NEW-SERIAL'})
 monkeypatch.setattr('agent.config.tls_context',lambda *a:True)
 calls=[]
 class Client:
  def __init__(self,**kwargs):pass
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def post(self,path,json):
   calls.append(json)
   if len(calls)==1:return SimpleNamespace(status_code=409,is_success=False,json=lambda:{'detail':{'code':'identity_mismatch','message':'foreign PC'}})
   return SimpleNamespace(status_code=200,is_success=True)
 monkeypatch.setattr(httpx,'Client',Client)
 startup=tmp_path/'startup';startup.mkdir()
 install(root,'NEW-STORE',startup=startup,launch=False)
 assert len(calls)==2 and calls[0]['uuid']==original['uuid'] and calls[1]['uuid']!=original['uuid']
 assert calls[1]['claim']!=original['claim']
 assert (startup/'SIMON Agent.lnk').exists() and not (state/'queue.db').exists()
 assert list(state.parent.glob('data-other-machine-*/queue.db'))
