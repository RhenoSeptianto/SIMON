from datetime import datetime,timezone,timedelta
import pytest
from agent.schedule import StorageSchedule,next_storage_run,WIB

def at(day,hour,minute=0,second=0):
 return datetime(2026,11,day,hour,minute,second,tzinfo=WIB).timestamp()

@pytest.mark.parametrize('started,target',[
 (at(6,8),at(6,16)),
 (at(6,15,59,59),at(6,16)),
 (at(6,16),at(7,16)),
 (at(6,21),at(7,16)),
])
def test_next_run_uses_wib(started,target):
 assert next_storage_run(started)==target

def test_startup_then_only_at_1600():
 schedule=StorageSchedule(at(6,8))
 assert schedule.is_due(at(6,8))
 schedule.mark_attempt(at(6,8))
 for hour in (9,10,12,15): assert not schedule.is_due(at(6,hour))
 assert not schedule.is_due(at(6,15,59,59))
 assert schedule.is_due(at(6,16))
 schedule.mark_attempt(at(6,16))
 assert not schedule.is_due(at(6,16,0,10))
 assert not schedule.is_due(at(7,15,59,59))
 assert schedule.is_due(at(7,16))

def test_late_start_and_resume_do_not_replay_missed_days():
 schedule=StorageSchedule(at(6,19))
 assert schedule.is_due(at(6,19))
 schedule.mark_attempt(at(6,19))
 assert not schedule.is_due(at(7,8))
 assert schedule.is_due(at(9,10))  # Resuming after several sleeping days.
 schedule.mark_attempt(at(9,10))
 assert not schedule.is_due(at(9,10,0,10))
 assert schedule.is_due(at(9,16))

def test_fixed_utc_offset():
 timestamp=datetime(2026,11,6,8,30,tzinfo=timezone.utc).timestamp()
 assert next_storage_run(timestamp)==datetime(2026,11,6,9,tzinfo=timezone.utc).timestamp()

def test_agent_keeps_metrics_interval_and_ignores_old_storage_interval(monkeypatch,tmp_path):
 import agent.main as agent
 calls={'storage':0,'metrics':0}
 clock=[at(6,8)]
 def collect(kind):
  calls[kind]+=1
  return {}
 monkeypatch.setattr(agent,'inventory',lambda:{'hostname':'SCHEDULE-TEST'})
 monkeypatch.setattr(agent,'metrics',lambda:collect('metrics'))
 monkeypatch.setattr(agent,'storage',lambda:collect('storage'))
 monkeypatch.setattr(agent.time,'time',lambda:clock[0])
 monotonic=[0]
 monkeypatch.setattr(agent.time,'monotonic',lambda:monotonic[0])
 monkeypatch.setattr(agent.random,'uniform',lambda a,b:1)
 monkeypatch.setenv('SIAMS_INTERVAL_STORAGE','1')
 monkeypatch.setattr(agent.logging,'basicConfig',lambda **kw:None)
 class Result:
  def raise_for_status(self):pass
  def json(self):return {'status':'approved','credential':'test'}
 class Client:
  def __init__(self,**kwargs):pass
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def post(self,*args,**kwargs):return Result()
 monkeypatch.setattr(agent.httpx,'Client',Client)
 monkeypatch.setattr(agent,'RotatingFileHandler',lambda *a,**kw:None)
 cycles=iter([(at(6,8,5),300),(at(6,16),28800),(at(6,16,5),29100)])
 def sleep(seconds):
  try:clock[0],monotonic[0]=next(cycles)
  except StopIteration:raise KeyboardInterrupt
 monkeypatch.setattr(agent.time,'sleep',sleep)
 monkeypatch.setattr('sys.argv',['agent','--state',str(tmp_path)])
 with pytest.raises(KeyboardInterrupt):agent.run()
 assert calls['storage']==2  # Startup and 16:00, never every 30 minutes.
 assert calls['metrics']==4  # Includes 08:05 and 16:05 independent of SSD.
