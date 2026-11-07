import json,uuid
import pytest


def test_agent_recovers_401_without_restarting_or_changing_identity(monkeypatch,tmp_path):
 import httpx
 import agent.main as agent
 original={'uuid':str(uuid.uuid4()),'claim':'c'*64,'credential':'old-token'}
 (tmp_path/'identity.json').write_text(json.dumps(original))
 config=tmp_path/'settings.json';config.write_text(json.dumps({'store_code':'00115'}))
 clock=[0];claims=[];enrollments=[];reports=[];sleeps=[]
 class Watcher:
  def __init__(self,path):self.pending=True
  def read_update(self):
   if self.pending:self.pending=False;return {'storage_source':'sentinel','sentinel_status':'missing'}
  def reset(self):self.pending=True
 class Result:
  def __init__(self,payload=None,unauthorized=False):self.payload=payload;self.unauthorized=unauthorized
  def json(self):return self.payload
  def raise_for_status(self):
   if self.unauthorized:
    request=httpx.Request('POST','https://office.invalid/api/agent/report')
    raise httpx.HTTPStatusError('expired',request=request,response=httpx.Response(401,request=request))
 class Client:
  def __init__(self,**kw):pass
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def post(self,path,**kw):
   if path.endswith('/enroll'):enrollments.append(kw['json']);return Result({'status':'approved'})
   if path.endswith('/claim'):
    claims.append(kw['json']);return Result({'credential':'old-token' if len(claims)==1 else 'new-token','status':'approved'})
   reports.append(kw)
   return Result(unauthorized=len(reports)==1)
 monkeypatch.setattr(agent,'SentinelWatcher',Watcher)
 monkeypatch.setattr(agent,'inventory',lambda:{'hostname':'RECOVER-PC'})
 monkeypatch.setattr(agent,'metrics',lambda:{'cpu_usage':10,'ram_percent':40})
 monkeypatch.setattr(agent.httpx,'Client',Client)
 monkeypatch.setattr(agent.logging,'basicConfig',lambda **kw:None)
 monkeypatch.setattr(agent,'RotatingFileHandler',lambda *a,**kw:None)
 monkeypatch.setattr(agent.random,'uniform',lambda a,b:1)
 monkeypatch.setattr(agent.time,'monotonic',lambda:clock[0])
 def sleep(seconds):
  sleeps.append(seconds)
  if len(sleeps)==1:
   saved=json.loads((tmp_path/'identity.json').read_text())
   assert saved['uuid']==original['uuid'] and saved['claim']==original['claim'] and 'credential' not in saved
   assert saved['machine_id']
   clock[0]=10
  else:raise KeyboardInterrupt
 monkeypatch.setattr(agent.time,'sleep',sleep)
 monkeypatch.setattr('sys.argv',['agent','--config',str(config),'--state',str(tmp_path)])
 with pytest.raises(KeyboardInterrupt):agent.run()
 saved=json.loads((tmp_path/'identity.json').read_text())
 assert all(saved[k]==v for k,v in {**original,'credential':'new-token'}.items())
 assert saved['machine_id']
 assert len(enrollments)==2 and all(e['uuid']==original['uuid'] and e['inventory']['store_code']=='00115' for e in enrollments)
 assert all(r['headers']['Authorization']=='Bearer new-token' for r in reports[1:])
 assert not list(tmp_path.glob('*.tmp'))


def test_legacy_deleted_uuid_is_no_longer_blocked():
 from backend.main import DB,DeletedDevice,app
 from fastapi.testclient import TestClient
 uid=str(uuid.uuid4())
 with DB() as s:s.add(DeletedDevice(uuid=uid));s.commit()
 c=TestClient(app)
 assert c.post('/api/agent/enroll',json={'uuid':uid,'claim':'c'*64,'inventory':{'hostname':'RETURN-PC'}}).json()['status']=='approved'
