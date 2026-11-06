"""Run built executable against a temporary HTTPS server, not the operational DB."""
import os,sys,tempfile,subprocess,socket,time,json,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.server_setup import generate_tls
import httpx
from agent.config import tls_context

def main():
 exe=ROOT/'release'/'SIMONAgent'/'SIMONAgent'/'SIMONAgent.exe'
 if not exe.exists():raise SystemExit('Build executable first: python -m tools.build_agent')
 sandbox=Path(tempfile.mkdtemp(prefix='simon-frozen-'));tls=sandbox/'tls';generate_tls(tls)
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 url=f'https://127.0.0.1:{port}';env=os.environ.copy();env['SIAMS_DATA']=str(sandbox/'db');env['SIAMS_PRODUCTION']='1'
 server=subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',str(port),'--ssl-keyfile',str(tls/'server.key'),'--ssl-certfile',str(tls/'server.crt'),'--no-access-log'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
 try:
  for _ in range(100):
   try:
    if httpx.get(url,verify=tls_context(str(tls/'ca.crt'))).status_code==200:break
   except httpx.HTTPError:pass
   time.sleep(.1)
  else:raise RuntimeError('HTTPS test server not ready')
  subprocess.run([sys.executable,'-m','tools.server_healthcheck','--ca',str(tls/'ca.crt'),'--url',url],cwd=ROOT,check=True,timeout=15)
  xml=sandbox/'HDSentinel.xml'
  xml.write_text('<Hard_Disk_Sentinel><Physical_Disk_Information_Disk_0><Hard_Disk_Summary><Hard_Disk_Model_ID>Smoke SSD</Hard_Disk_Model_ID><Hard_Disk_Serial_Number>SMOKE-SSD-1</Hard_Disk_Serial_Number><Health>95 %</Health><Performance>100 %</Performance><Current_Temperature>37 C</Current_Temperature></Hard_Disk_Summary></Physical_Disk_Information_Disk_0></Hard_Disk_Sentinel>')
  config=sandbox/'agent-config.json';config.write_text(json.dumps({'server':url,'ca_file':str(tls/'ca.crt'),'state':str(sandbox/'state'),'sentinel_xml':str(xml),'store_code':'00115'}))
  command=[str(exe),'--config',str(config),'--once']
  for _ in range(2):subprocess.run(command,check=True,timeout=120,capture_output=True,text=True)
  with sqlite3.connect(sandbox/'db'/'siams.db') as db:
   assert db.execute('select count(*) from devices').fetchone()[0]==1
   status,metrics=db.execute('select status,metrics from devices').fetchone()
   assert status=='approved'
   payload=json.loads(metrics);assert 'cpu_usage' in payload and 'ram_total' in payload
   assert len(payload['disks'])==1 and payload['disks'][0]['source']=='sentinel'
   assert db.execute('select store_code from devices').fetchone()[0]=='00115'
   assert db.execute('select count(*) from telemetry').fetchone()[0]==2
  # Exercise delete/re-enroll while the SAME executable process keeps running.
  import hashlib,secrets
  salt=secrets.token_hex(16);hashed=salt+':'+hashlib.scrypt(b'smoke-pass',salt=salt.encode(),n=16384,r=8,p=1).hex()
  with sqlite3.connect(sandbox/'db'/'siams.db') as db:
   db.execute("insert into users(name,username,password,role,active,stores) values(?,?,?,?,?,?)",('Smoke Admin','smokeadmin',hashed,'super_admin',1,'[]'))
  worker=subprocess.Popen(command[:-1],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
  try:
   for _ in range(45):
    with sqlite3.connect(sandbox/'db'/'siams.db') as db: samples=db.execute('select count(*) from telemetry').fetchone()[0]
    if samples>=3:break
    time.sleep(1)
   else:raise RuntimeError('Live agent did not send startup metrics')
   time.sleep(1)
   with httpx.Client(base_url=url,verify=tls_context(str(tls/'ca.crt')),timeout=10) as client:
    assert client.post('/api/login',json={'username':'smokeadmin','password':'smoke-pass'}).status_code==200
    before=client.get('/api/devices').json()['items'][0]
    assert client.delete('/api/devices/'+str(before['id']),headers={'X-SIAMS-Request':'1'}).status_code==200
    xml.write_text(xml.read_text()+'\n')  # Simulate the next Sentinel export.
    for _ in range(45):
     records=client.get('/api/devices').json()['items']
     if records and records[0]['metrics'].get('storage_source')=='sentinel' and records[0]['metrics'].get('cpu_usage') is not None:
      after=records[0];break
     time.sleep(1)
    else:raise RuntimeError('Agent did not reenroll after delete')
    assert worker.poll() is None
    assert after['uuid']==before['uuid'] and after['store_code']=='00115'
    with sqlite3.connect(sandbox/'db'/'siams.db') as db:
     assert db.execute('select count(*) from devices').fetchone()[0]==1
     assert db.execute('select count(*) from telemetry').fetchone()[0]==1
    print('PASS: running EXE reenrolls automatically after dashboard delete with the same UUID/store code; only new CPU history remains.')
  finally:
   worker.terminate();worker.wait(timeout=15)
  print('PASS: built exe starts, validates office-style CA, enrolls, reports Windows inventory/CPU/RAM and Sentinel fixture without disk history, carries store code, and preserves one UUID across restarts.')
  print('EXE:',exe)
  print('ZIP bytes:',(ROOT/'release'/'SIMONAgent-template.zip').stat().st_size)
 finally:
  server.terminate();server.wait(timeout=15)
if __name__=='__main__':main()
