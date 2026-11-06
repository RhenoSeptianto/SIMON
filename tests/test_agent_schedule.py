import json,sqlite3
import pytest

def test_agent_watches_sentinel_and_keeps_metrics_interval(monkeypatch,tmp_path):
 import agent.main as agent
 calls={'xml':0,'metrics':0};clock=[0]
 def metric():calls['metrics']+=1;return {'cpu_usage':10}
 class Watcher:
  def __init__(self,path):pass
  def read_update(self):
   calls['xml']+=1
   return {'storage_source':'sentinel','sentinel_status':'fresh','disks':[{'serial_number':str(calls['xml'])}]} if calls['xml']!=2 else None
 monkeypatch.setattr(agent,'SentinelWatcher',Watcher)
 monkeypatch.setattr(agent,'inventory',lambda:{'hostname':'TEST'})
 monkeypatch.setattr(agent,'metrics',metric)
 monkeypatch.setattr(agent.time,'monotonic',lambda:clock[0])
 monkeypatch.setattr(agent.random,'uniform',lambda a,b:1)
 monkeypatch.setattr(agent.logging,'basicConfig',lambda **kw:None)
 monkeypatch.setattr(agent,'RotatingFileHandler',lambda *a,**kw:None)
 class Client:
  def __init__(self,**kw):pass
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def post(self,*args,**kw):raise ConnectionError('offline fixture')
 monkeypatch.setattr(agent.httpx,'Client',Client)
 cycles=iter([10,300])
 def sleep(seconds):
  try:clock[0]=next(cycles)
  except StopIteration:raise KeyboardInterrupt
 monkeypatch.setattr(agent.time,'sleep',sleep)
 config=tmp_path/'test-config.json';config.write_text(json.dumps({'store_code':'00115'}))
 monkeypatch.setattr('sys.argv',['agent','--config',str(config),'--state',str(tmp_path)])
 with pytest.raises(KeyboardInterrupt):agent.run()
 assert calls=={'xml':3,'metrics':3}
 with sqlite3.connect(tmp_path/'queue.db') as db:
  rows=[json.loads(row[0]) for row in db.execute('select payload from queue')]
 assert len([r for r in rows if r['kind']=='storage'])==1
 assert next(r for r in rows if r['kind']=='storage')['payload']['disks'][0]['serial_number']=='3'
 assert next(r for r in rows if r['kind']=='inventory')['payload']['store_code']=='00115'
