"""Outbound-only agent. No remote command or host mutation endpoints."""
import os,json,uuid,secrets,sqlite3,time,random,logging,argparse,sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import httpx
from agent.collectors import inventory,metrics
from agent.sentinel import SentinelWatcher,DEFAULT_XML
from agent.config import load_config,validate_server,tls_context,DEFAULT_SERVER

def run():
 p=argparse.ArgumentParser(); p.add_argument('--server'); p.add_argument('--config'); p.add_argument('--ca-file'); p.add_argument('--once',action='store_true'); p.add_argument('--diagnose',action='store_true'); p.add_argument('--state'); p.add_argument('--store-code'); p.add_argument('--sentinel-xml'); args=p.parse_args()
 try:
  config=load_config(args.config)
  args.server=validate_server(args.server or config.get('server') or os.getenv('SIAMS_SERVER') or (DEFAULT_SERVER if getattr(sys,'frozen',False) else 'http://127.0.0.1:8000'))
  args.state=args.state or config.get('state') or str(Path(os.getenv('PROGRAMDATA',str(Path.home())))/'SIAMS')
  store_code=str(args.store_code or config.get('store_code') or '').strip()
  if len(store_code)>40: raise ValueError('Kode store maksimal 40 karakter')
  sentinel=SentinelWatcher(args.sentinel_xml or config.get('sentinel_xml') or DEFAULT_XML)
  ca_file=args.ca_file or config.get('ca_file')
  verify=tls_context(ca_file) if ca_file and not args.diagnose else None
 except (ValueError,OSError) as error: p.error(str(error))
 state=Path(args.state); state.mkdir(parents=True,exist_ok=True)
 logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',handlers=[RotatingFileHandler(state/'agent.log',maxBytes=1048576,backupCount=3,encoding='utf8'),logging.StreamHandler()])
 identity=state/'identity.json'
 if not identity.exists(): identity.write_text(json.dumps({'uuid':str(uuid.uuid4()),'claim':secrets.token_urlsafe(48)}))
 ident=json.loads(identity.read_text()); queue=sqlite3.connect(state/'queue.db'); queue.execute('create table if not exists queue(id integer primary key,payload text)'); queue.execute('pragma journal_size_limit=1048576')
 if 'kind' not in [row[1] for row in queue.execute('pragma table_info(queue)')]: queue.execute("alter table queue add column kind text not null default ''")
 queue.commit()
 def collect_inventory(): return {**inventory(),'store_code':store_code}
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
 schedule={'heartbeat':120,'metrics':300,'inventory':86400}; due={k:0 for k in schedule}; backoff=5
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
     due[kind]=time.monotonic()+float(os.getenv('SIAMS_INTERVAL_'+kind.upper(),schedule[kind]))*random.uniform(.9,1.1)
    if not ident.get('credential'):
     client.post('/api/agent/enroll',json={**{k:ident[k] for k in ('uuid','claim')},'inventory':collect_inventory()}).raise_for_status()
     r=client.post('/api/agent/claim',json={k:ident[k] for k in ('uuid','claim')}); r.raise_for_status(); result=r.json()
     if result.get('credential'): ident['credential']=result['credential']; identity.write_text(json.dumps(ident))
     elif result.get('status')=='credential_issued' and previous_credential: ident['credential']=previous_credential
     else: logging.info('enrollment_status=%s',result['status']); backoff=300
    if ident.get('credential'):
     for id,payload in queue.execute('select id,payload from queue order by id limit 50').fetchall():
      r=client.post('/api/agent/report',json=json.loads(payload),headers={'Authorization':'Bearer '+ident['credential']}); r.raise_for_status(); queue.execute('delete from queue where id=?',(id,)); queue.commit()
    backoff=5
   except Exception as e:
    logging.warning('transport_failed %s',type(e).__name__); backoff=min(backoff*2,300)
   if args.once: break
   time.sleep(backoff+random.uniform(0,3))
if __name__=='__main__': run()
