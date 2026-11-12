"""Download the fixed GitHub agent asset, wrap it with the office public CA, and coordinate rolling mass updates."""
import hashlib,json,re,threading,time
from pathlib import Path
import httpx
from tools.make_agent_package import make_package,REQUIRED_CAPABILITIES
from tools.update_worker import read_json,write_json

ASSET_URL='https://github.com/RhenoSeptianto/SIMON/releases/download/agent-latest/SIMONAgent-template.zip'
MAX_TEMPLATE_BYTES=100*1024*1024
ROLLOUT_MAX_CONCURRENT=3
ROLLOUT_DEVICE_TIMEOUT=120
_ROLLOUT_LOCK=threading.Lock()

class AgentPackageError(Exception):pass

def folder(data):return Path(data)/'agent-package'
def rollout_file(data):return folder(data)/'rollout.json'

def _device_build_sha(dev):
 if isinstance(dev,dict):
  inv=dev.get('inventory') or {}
  agent=dev.get('agent') or {}
  return str(agent.get('build_sha') or inv.get('agent_build_sha') or '').strip().lower()
 try:
  inv=json.loads(getattr(dev,'inventory','{}') or '{}')
  return str(inv.get('agent_build_sha') or '').strip().lower()
 except Exception:
  return ''

def _sync_rollout_unlocked(data,current_sha='',devices=None):
 path=rollout_file(data);raw=read_json(path)
 if not raw:
  return {'state':'idle','busy':False,'target_sha':current_sha or '','agent_version':None,'started_at':None,'updated_at':None,'total':0,'done':0,'in_progress':0,'queued':0,'failed':0,'max_concurrent':ROLLOUT_MAX_CONCURRENT,'message':'Belum ada proses update massal.'}
 target_sha=str(raw.get('target_sha') or '').strip().lower()
 items=raw.get('devices') or {}
 now_ts=time.time();changed=False
 if devices is not None:
  by_id={str(d['id'] if isinstance(d,dict) else d.id):d for d in devices}
  for dev_id,entry in items.items():
   if entry.get('state') in ('queued','in_progress') and dev_id in by_id:
    if target_sha and _device_build_sha(by_id[dev_id])==target_sha:
     entry['state']='done';entry['updated_at']=now_ts;entry['error']=None;changed=True
 for entry in items.values():
  if entry.get('state')=='in_progress':
   started=float(entry.get('claimed_at') or entry.get('updated_at') or raw.get('started_at') or now_ts)
   if now_ts-started>ROLLOUT_DEVICE_TIMEOUT:
    entry['state']='failed';entry['error']='Waktu update habis (timeout)';entry['updated_at']=now_ts;changed=True
 active_in_progress=sum(1 for x in items.values() if x.get('state')=='in_progress')
 if raw.get('state')=='running' and active_in_progress<ROLLOUT_MAX_CONCURRENT:
  for entry in items.values():
   if active_in_progress>=ROLLOUT_MAX_CONCURRENT:break
   if entry.get('state')=='queued':
    entry['state']='in_progress';entry['claimed_at']=now_ts;entry['updated_at']=now_ts;active_in_progress+=1;changed=True
 total=len(items)
 done=sum(1 for x in items.values() if x.get('state')=='done')
 in_progress=sum(1 for x in items.values() if x.get('state')=='in_progress')
 queued=sum(1 for x in items.values() if x.get('state')=='queued')
 failed=sum(1 for x in items.values() if x.get('state')=='failed')
 if raw.get('state')=='running':
  if in_progress==0 and queued==0:
   raw['state']='completed' if failed==0 else ('partial' if done>0 else 'failed')
   raw['updated_at']=now_ts
   raw['message']=f'Update massal selesai: {done}/{total} PC berhasil diperbarui.'+(f' ({failed} gagal/lewat waktu)' if failed else '')
   changed=True
  else:
   msg=f'Memperbarui agent secara bergilir: {done}/{total} selesai, {in_progress} sedang diproses, {queued} antrean.'
   if raw.get('message')!=msg:
    raw['message']=msg;raw['updated_at']=now_ts;changed=True
 if changed:write_json(path,raw)
 return {'state':raw.get('state','idle'),'busy':raw.get('state')=='running','target_sha':target_sha,'agent_version':raw.get('agent_version'),'started_at':raw.get('started_at'),'updated_at':raw.get('updated_at'),'total':total,'done':done,'in_progress':in_progress,'queued':queued,'failed':failed,'max_concurrent':ROLLOUT_MAX_CONCURRENT,'message':raw.get('message') or 'Belum ada proses update massal.'}

def rollout_status(data,current_sha='',devices=None):
 with _ROLLOUT_LOCK:
  return _sync_rollout_unlocked(data,current_sha,devices)

def status(data,current_sha='',devices=None):
 base=folder(data);metadata=read_json(base/'status.json');package=base/'SIMONAgent-store.zip'
 ready=bool(metadata.get('source_sha')==current_sha and package.is_file() and metadata.get('package_sha256')==hashlib.sha256(package.read_bytes()).hexdigest())
 rollout=rollout_status(data,current_sha,devices)
 online_outdated=0
 if devices is not None:
  online_outdated=sum(1 for d in devices if isinstance(d,dict) and d.get('online') and (d.get('agent') or {}).get('status')!='current')
 return {**metadata,'ready':ready,'current_sha':current_sha,'download':'/api/system/agent-package/download' if ready else None,'rollout':rollout,'online_outdated':online_outdated}

def start_rollout(data,current_sha,devices,actor=None):
 with _ROLLOUT_LOCK:
  base=folder(data);metadata=read_json(base/'status.json');package=base/'SIMONAgent-store.zip'
  ready=bool(metadata.get('source_sha')==current_sha and package.is_file() and metadata.get('package_sha256')==hashlib.sha256(package.read_bytes()).hexdigest())
  if not ready:
   raise AgentPackageError('Paket agent terbaru belum siap. Klik Ambil agent terbaru terlebih dahulu.')
  current_rollout=_sync_rollout_unlocked(data,current_sha,devices)
  if current_rollout['busy']:
   raise AgentPackageError('Update massal agent sedang berjalan. Tunggu proses selesai.')
  targets=[d for d in (devices or []) if d.get('online') and (d.get('agent') or {}).get('status')!='current']
  if not targets:
   raise AgentPackageError('Semua PC yang sedang online sudah menggunakan agent versi terbaru.')
  now_ts=time.time();items={}
  for idx,d in enumerate(targets):
   active=idx<ROLLOUT_MAX_CONCURRENT
   items[str(d['id'])]={'id':d['id'],'hostname':d.get('hostname') or '','store_code':d.get('store_code') or '','state':'in_progress' if active else 'queued','claimed_at':now_ts if active else None,'updated_at':now_ts,'error':None}
  raw={'state':'running','target_sha':current_sha,'agent_version':metadata.get('agent_version'),'package_sha256':metadata.get('package_sha256'),'actor':str(actor or ''),'started_at':now_ts,'updated_at':now_ts,'devices':items,'message':''}
  write_json(rollout_file(data),raw)
  return _sync_rollout_unlocked(data,current_sha,devices)

def claim_device_update(data,current_sha,device_id,device_build_sha=''):
 with _ROLLOUT_LOCK:
  path=rollout_file(data);raw=read_json(path)
  if not raw:return None
  target_sha=str(raw.get('target_sha') or '').strip().lower()
  build=str(device_build_sha or '').strip().lower()
  items=raw.get('devices') or {}
  entry=items.get(str(device_id))
  if not entry:return None
  now_ts=time.time()
  if build and target_sha and build==target_sha:
   if entry.get('state')!='done':
    entry['state']='done';entry['updated_at']=now_ts;entry['error']=None
    write_json(path,raw)
    _sync_rollout_unlocked(data,current_sha)
   return None
  if raw.get('state')!='running' or (current_sha and target_sha!=str(current_sha).strip().lower()):
   return None
  _sync_rollout_unlocked(data,current_sha)
  raw=read_json(path);items=raw.get('devices') or {};entry=items.get(str(device_id))
  if not entry or entry.get('state') in ('done','failed'):return None
  active_other=sum(1 for k,x in items.items() if k!=str(device_id) and x.get('state')=='in_progress')
  if entry.get('state')=='in_progress' or (entry.get('state')=='queued' and active_other<ROLLOUT_MAX_CONCURRENT):
   entry['state']='in_progress'
   if not entry.get('claimed_at'):entry['claimed_at']=now_ts
   entry['updated_at']=now_ts
   write_json(path,raw)
   return {'target_sha':target_sha,'version':raw.get('agent_version'),'package_sha256':raw.get('package_sha256'),'download_url':'/api/agent/update/package'}
  return None

def record_device_update_status(data,current_sha,device_id,state,error=''):
 with _ROLLOUT_LOCK:
  path=rollout_file(data);raw=read_json(path)
  if not raw:return {'ok':False}
  items=raw.get('devices') or {};entry=items.get(str(device_id))
  if not entry:return {'ok':False}
  now_ts=time.time()
  if state=='failed':
   entry['state']='failed';entry['error']=str(error or 'Gagal memperbarui agent')[:300];entry['updated_at']=now_ts
  elif state in ('downloading','installing'):
   entry['substate']=state;entry['updated_at']=now_ts
  write_json(path,raw)
  summary=_sync_rollout_unlocked(data,current_sha)
  return {'ok':True,'rollout':summary}

def validate_template(path,expected_sha):
 import zipfile
 try:
  with zipfile.ZipFile(path) as archive:
   names=archive.namelist()
   if 'agent-build.json' not in names or 'SIMONAgent/SIMONAgent.exe' not in names:raise AgentPackageError('Artifact agent tidak lengkap.')
   metadata=json.loads(archive.read('agent-build.json').decode('utf-8-sig'))
   executable=archive.read('SIMONAgent/SIMONAgent.exe')
 except (OSError,zipfile.BadZipFile,KeyError,ValueError) as error:raise AgentPackageError('Artifact agent rusak atau tidak valid: '+str(error))
 if metadata.get('source_sha')!=expected_sha:raise AgentPackageError('Build agent untuk versi server ini belum tersedia. Tunggu GitHub Actions selesai lalu coba lagi.')
 if not REQUIRED_CAPABILITIES.issubset(metadata.get('capabilities',[])):raise AgentPackageError('Artifact agent tidak memiliki capability wajib terbaru.')
 if metadata.get('exe_sha256')!=hashlib.sha256(executable).hexdigest():raise AgentPackageError('Checksum EXE agent tidak sesuai manifest.')
 return metadata

def fetch_template(target):
 try:
  with httpx.stream('GET',ASSET_URL,follow_redirects=True,timeout=60) as response:
   response.raise_for_status();size=0
   with target.open('wb') as output:
    for chunk in response.iter_bytes():
     size+=len(chunk)
     if size>MAX_TEMPLATE_BYTES:raise AgentPackageError('Artifact agent melebihi batas 100 MiB.')
     output.write(chunk)
 except AgentPackageError:raise
 except Exception as error:raise AgentPackageError('Gagal mengambil agent terbaru dari GitHub: '+str(error))

def prepare(data,root,current_sha,fetch=fetch_template):
 if not re.fullmatch('[0-9a-f]{40}',current_sha or ''):raise AgentPackageError('SHA versi server belum tersedia. Selesaikan pemasangan helper UpdateSimon terlebih dahulu.')
 base=folder(data);base.mkdir(parents=True,exist_ok=True);lock=base/'prepare.lock'
 try:lock.open('x').close()
 except FileExistsError:raise AgentPackageError('Paket agent sedang disiapkan. Tunggu proses sebelumnya selesai.')
 template=base/'template.download';output=base/'SIMONAgent-store.zip'
 try:
  fetch(template);metadata=validate_template(template,current_sha)
  make_package(root,template_path=template,ca_path=Path(data)/'tls'/'ca.crt',output_path=output)
  result={'source_sha':current_sha,'agent_version':metadata.get('version'),'exe_sha256':metadata['exe_sha256'],'package_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'size':output.stat().st_size,'created_at':time.time(),'filename':'SIMONAgent-store.zip','error':None}
  write_json(base/'status.json',result);return {**result,'ready':True,'download':'/api/system/agent-package/download','rollout':rollout_status(data,current_sha)}
 except Exception as error:
  previous=read_json(base/'status.json');previous.update(error=str(error),failed_at=time.time());write_json(base/'status.json',previous)
  if isinstance(error,AgentPackageError):raise
  raise AgentPackageError(str(error))
 finally:template.unlink(missing_ok=True);lock.unlink(missing_ok=True)
