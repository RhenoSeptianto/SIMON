"""Outbound-only agent. No remote command or host mutation endpoints."""
import os,json,uuid,secrets,sqlite3,time,random,logging,argparse,sys,math
from pathlib import Path
from logging.handlers import RotatingFileHandler
import httpx
from agent.collectors import inventory,metrics
from agent.sentinel import SentinelWatcher,DEFAULT_XML
from agent.config import load_config,validate_server,tls_context,DEFAULT_SERVER

def save_identity(path,data):
 temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
 temporary.write_text(json.dumps(data),encoding='utf-8')
 os.replace(temporary,path)

def run():
 p=argparse.ArgumentParser(); p.add_argument('--server'); p.add_argument('--config'); p.add_argument('--ca-file'); p.add_argument('--once',action='store_true'); p.add_argument('--diagnose',action='store_true'); p.add_argument('--check-connection',action='store_true'); p.add_argument('--background',action='store_true'); p.add_argument('--state'); p.add_argument('--store-code'); p.add_argument('--sentinel-xml'); args=p.parse_args()
 try:
  config=load_config(args.config)
  args.server=validate_server(args.server or config.get('server') or os.getenv('SIAMS_SERVER') or (DEFAULT_SERVER if getattr(sys,'frozen',False) else 'http://127.0.0.1:8000'))
  args.state=args.state or config.get('state') or str(Path(os.getenv('PROGRAMDATA',str(Path.home())))/'SIAMS')
  schedule={name:float(os.getenv('SIAMS_INTERVAL_'+name.upper(),default)) for name,default in {'heartbeat':10,'metrics':10,'inventory':86400}.items()}
  if any(not math.isfinite(value) or value<=0 for value in schedule.values()):raise ValueError('Interval agent harus berupa angka positif')
  store_code=str(args.store_code or config.get('store_code') or '').strip()
  if len(store_code)>40: raise ValueError('Kode store maksimal 40 karakter')
  sentinel=SentinelWatcher(args.sentinel_xml or config.get('sentinel_xml') or DEFAULT_XML)
  ca_file=args.ca_file or config.get('ca_file')
  verify=tls_context(ca_file) if ca_file and not args.diagnose else None
 except (ValueError,OSError) as error: p.error(str(error))
 if args.check_connection:
  try:
   with httpx.Client(verify=verify if verify is not None else True,timeout=10) as probe:
    response=probe.get(args.server+'/');response.raise_for_status()
   print('HTTPS OK: HTTP '+str(response.status_code));return
  except Exception as error:
   print('HTTPS GAGAL: '+str(error));raise SystemExit(1)
 if args.background:
  from agent.user_startup import background
  background(args.state,args.config);return
 state=Path(args.state); state.mkdir(parents=True,exist_ok=True)
 logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',handlers=[RotatingFileHandler(state/'agent.log',maxBytes=1048576,backupCount=3,encoding='utf8')]+([] if os.getenv('SIAMS_WORKER_CAPTURE')=='1' else [logging.StreamHandler()]))
 if not args.once and not args.diagnose:
  from agent.user_startup import single_instance
  if not single_instance(state,args.server):
   logging.info('Agent dengan state yang sama sudah aktif; duplikat dibatalkan.');return
 identity=state/'identity.json'
 from agent.identity import ensure_identity,machine_id
 ident=ensure_identity(state);identity=state/'identity.json'; queue=sqlite3.connect(state/'queue.db'); queue.execute('create table if not exists queue(id integer primary key,payload text)'); queue.execute('pragma journal_size_limit=1048576')
 if 'kind' not in [row[1] for row in queue.execute('pragma table_info(queue)')]: queue.execute("alter table queue add column kind text not null default ''")
 queue.commit()
 def collect_inventory(): return {**inventory(),'machine_id':machine_id(),'store_code':store_code,'heartbeat_interval_seconds':schedule['heartbeat'],'metrics_interval_seconds':schedule['metrics']}
 def enqueue(kind,payload):
  if kind=='storage': queue.execute("delete from queue where kind='storage'")
  queue.execute('insert into queue(payload,kind) values (?,?)',(json.dumps({'event_id':str(uuid.uuid4()),'collected_at':time.time(),'kind':kind,'payload':payload}),kind))
  queue.execute('delete from queue where id not in (select id from queue order by id desc limit 2000)'); queue.commit()
 if args.diagnose:
  for collect in (collect_inventory,metrics,sentinel.read_update):
   try: print(json.dumps(collect(),indent=2))
   except Exception: logging.exception('collection_failed')
  return
 # Reclaim on each start so a database reset can recover without changing UUID.
 previous_credential=ident.pop('credential',None)
 due={k:0 for k in schedule}; backoff=1
 client_options={'base_url':args.server,'timeout':15}
 if verify is not None: client_options['verify']=verify
 with httpx.Client(**client_options) as client:
  while True:
   try:
    # Metadata polling is cheap; only parse/send when XML changes or its status changes.
    try:
     update=sentinel.read_update()
     if update is not None: enqueue('storage',update)
    except Exception: logging.exception('collector_failed kind=sentinel')
    for kind in schedule:
     if time.monotonic()<due[kind]: continue
     try:
      payload={} if kind=='heartbeat' else {'inventory':collect_inventory,'metrics':metrics}[kind]()
      enqueue(kind,payload)
     except Exception: logging.exception('collector_failed kind=%s',kind)
     due[kind]=time.monotonic()+schedule[kind]*random.uniform(.9,1.1)
    if not ident.get('credential'):
     client.post('/api/agent/enroll',json={**{k:ident[k] for k in ('uuid','claim')},'inventory':collect_inventory()}).raise_for_status()
     r=client.post('/api/agent/claim',json={k:ident[k] for k in ('uuid','claim')}); r.raise_for_status(); result=r.json()
     if result.get('credential'): ident['credential']=result['credential']; save_identity(identity,ident)
     elif result.get('status')=='credential_issued' and previous_credential: ident['credential']=previous_credential
     else: logging.info('enrollment_status=%s',result['status']); backoff=300
    if ident.get('credential'):
     for id,payload in queue.execute('select id,payload from queue order by id limit 50').fetchall():
      r=client.post('/api/agent/report',json=json.loads(payload),headers={'Authorization':'Bearer '+ident['credential']}); r.raise_for_status(); queue.execute('delete from queue where id=?',(id,)); queue.commit()
    if ident.get('credential'): backoff=1
   except httpx.HTTPStatusError as error:
    if error.response.status_code==401 and ident.get('credential'):
     # Preserve UUID/claim/store configuration, discard only the invalid token.
     ident.pop('credential',None);previous_credential=None;save_identity(identity,ident)
     due['metrics']=0;due['inventory']=0;sentinel.reset()
     logging.info('device_credential_expired reenrollment_scheduled')
     backoff=5
    else:
     if error.response.status_code==409:
      try: logging.error('store_code_conflict: %s',error.response.json().get('detail','Kode store sudah digunakan.'))
      except ValueError: logging.error('store_code_conflict: kode store sudah digunakan.')
      backoff=150
     logging.warning('transport_failed HTTPStatusError status=%s',error.response.status_code);backoff=min(backoff*2,300)
   except Exception as e:
    logging.warning('transport_failed %s: %s',type(e).__name__,str(e)); backoff=min(backoff*2,300)
   if args.once: break
   time.sleep(backoff+random.uniform(0,0.25))
if __name__=='__main__': run()
