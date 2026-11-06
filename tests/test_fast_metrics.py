import json,time,uuid
from fastapi.testclient import TestClient
from backend.main import DB,Device,Sample,digest,serialize,app


def test_ten_second_metrics_update_live_but_history_stays_five_minutes():
 token=uuid.uuid4().hex
 with DB() as s:
  d=Device(uuid=str(uuid.uuid4()),hostname='FAST-PC',claim='x',credential=digest(token),status='approved');s.add(d);s.flush();id=d.id;s.commit()
 c=TestClient(app);start=time.time()
 for offset,value in ((0,10),(10,20),(20,30),(299,40),(300,50)):
  response=c.post('/api/agent/report',headers={'Authorization':'Bearer '+token},json={'event_id':str(uuid.uuid4()),'collected_at':start+offset,'kind':'metrics','payload':{'cpu_usage':value,'ram_percent':value}})
  assert response.status_code==200
 with DB() as s:
  assert s.query(Sample).filter_by(device_id=id).count()==2
  latest=json.loads(s.get(Device,id).metrics)
  assert latest['cpu_usage']==50 and latest['ram_percent']==50
  history=s.query(Sample).filter_by(device_id=id).order_by(Sample.collected).all()
  assert [json.loads(row.payload)['cpu_usage'] for row in history]==[10,50]


def test_offline_window_uses_reported_heartbeat_without_breaking_old_agents(monkeypatch):
 monkeypatch.delenv('OFFLINE_SECONDS',raising=False)
 with DB() as s:
  fresh=Device(uuid=str(uuid.uuid4()),hostname='FAST',claim='x',status='approved',last_seen=time.time()-30,inventory=json.dumps({'heartbeat_interval_seconds':10}))
  legacy=Device(uuid=str(uuid.uuid4()),hostname='OLD',claim='x',status='approved',last_seen=time.time()-200)
  s.add_all([fresh,legacy]);s.flush()
  assert serialize(fresh)['online'] and serialize(legacy)['online']
  fresh.last_seen=time.time()-46
  assert not serialize(fresh)['online']
  monkeypatch.setenv('OFFLINE_SECONDS','600')
  assert serialize(fresh)['online']
