import logging
from agent.main import quiet_transport_logs
from backend.run_server import RoutineTelemetryFilter


def access(path,status):
 return logging.LogRecord('uvicorn.access',logging.INFO,'',0,'%s - "%s %s HTTP/%s" %d',('127.0.0.1:1','POST',path,'1.1',status),None)


def test_agent_suppresses_transport_success_noise_but_keeps_own_logger():
 root=logging.getLogger();httpx=logging.getLogger('httpx');httpcore=logging.getLogger('httpcore')
 previous=(root.level,httpx.level,httpcore.level)
 try:
  root.setLevel(logging.INFO);httpx.setLevel(logging.INFO);httpcore.setLevel(logging.INFO)
  quiet_transport_logs()
  assert root.level==logging.INFO
  assert httpx.level==logging.WARNING and httpcore.level==logging.WARNING
 finally:root.setLevel(previous[0]);httpx.setLevel(previous[1]);httpcore.setLevel(previous[2])


def test_server_only_filters_successful_agent_telemetry_access_lines():
 filter_=RoutineTelemetryFilter()
 assert not filter_.filter(access('/api/agent/report',200))
 assert not filter_.filter(access('/api/agent/report?retry=1',204))
 assert filter_.filter(access('/api/agent/report',401))
 assert filter_.filter(access('/api/agent/report',500))
 assert filter_.filter(access('/api/devices',200))
