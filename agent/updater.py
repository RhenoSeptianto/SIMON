"""Safe outbound self-updater for SIMONAgent on store PCs."""
import argparse,hashlib,json,logging,os,shutil,subprocess,sys,time,zipfile
from pathlib import Path
from agent.build_info import SOURCE_SHA as AGENT_BUILD_SHA

MAX_PACKAGE_BYTES=100*1024*1024
PRESERVED_AGENT_ITEMS={'data','hdsentinel.xml'}
PRESERVED_ROOT_FILES={'config.json'}

def report_update_status(client,credential,state,target_sha='',error=''):
 try:
  client.post('/api/agent/update/status',json={'state':state,'target_sha':target_sha,'error':str(error)[:500]},headers={'Authorization':'Bearer '+credential},timeout=10)
 except Exception:
  pass

def safe_extract(archive_path,destination):
 destination=Path(destination).resolve()
 if destination.exists():shutil.rmtree(destination,ignore_errors=True)
 destination.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(archive_path) as archive:
  for member in archive.infolist():
   target=(destination/member.filename).resolve()
   if destination not in target.parents and target!=destination:
    raise ValueError('Path zip tidak aman: '+member.filename)
  archive.extractall(destination)
 return destination

def download_and_stage(client,credential,update_info,state_dir):
 target_sha=str(update_info.get('target_sha') or '').strip().lower()
 expected_pkg_sha=str(update_info.get('package_sha256') or '').strip().lower()
 download_url=str(update_info.get('download_url') or '/api/agent/update/package')
 staging=Path(state_dir).resolve()/'update-staging'
 staging.mkdir(parents=True,exist_ok=True)
 archive_path=staging/'SIMONAgent-store.zip'
 digest=hashlib.sha256();size=0
 with client.stream('GET',download_url,headers={'Authorization':'Bearer '+credential},timeout=120) as response:
  response.raise_for_status()
  with archive_path.open('wb') as out:
   for chunk in response.iter_bytes():
    size+=len(chunk)
    if size>MAX_PACKAGE_BYTES:raise ValueError('Paket update agent melebihi batas 100 MiB')
    digest.update(chunk);out.write(chunk)
 if expected_pkg_sha and digest.hexdigest().lower()!=expected_pkg_sha:
  raise ValueError('Checksum paket update agent tidak cocok')
 extracted=safe_extract(archive_path,staging/'extracted')
 meta_path=extracted/'agent-build.json'
 exe_path=extracted/'SIMONAgent'/'SIMONAgent.exe'
 if not meta_path.is_file() or not exe_path.is_file():
  raise ValueError('Isi paket update agent tidak lengkap')
 metadata=json.loads(meta_path.read_text(encoding='utf-8-sig'))
 if target_sha and str(metadata.get('source_sha') or '').strip().lower()!=target_sha:
  raise ValueError('SHA build paket agent tidak sesuai target')
 exe_sha=hashlib.sha256(exe_path.read_bytes()).hexdigest().lower()
 if str(metadata.get('exe_sha256') or '').strip().lower()!=exe_sha:
  raise ValueError('Checksum SIMONAgent.exe tidak sesuai manifest')
 return extracted,exe_path,metadata

def trigger_self_update(client,credential,update_info,state_dir,config_path=None):
 if not isinstance(update_info,dict):return False
 target_sha=str(update_info.get('target_sha') or '').strip().lower()
 current_sha=str(AGENT_BUILD_SHA or '').strip().lower()
 if not target_sha or target_sha==current_sha:return False
 state_dir=Path(state_dir).resolve()
 try:
  report_update_status(client,credential,'downloading',target_sha)
  extracted,staged_exe,_=download_and_stage(client,credential,update_info,state_dir)
  report_update_status(client,credential,'installing',target_sha)
  if config_path and Path(config_path).exists():
   install_root=Path(config_path).resolve().parent
   cfg=str(Path(config_path).resolve())
  elif getattr(sys,'frozen',False):
   install_root=Path(sys.executable).resolve().parent.parent
   cfg=str(install_root/'config.json')
  else:
   install_root=state_dir.parent.parent
   cfg=str(install_root/'config.json')
  if not getattr(sys,'frozen',False) and os.getenv('SIAMS_ALLOW_TEST_SELF_UPDATE')!='1':
   logging.info('self_update_staged_non_frozen target_sha=%s path=%s',target_sha,extracted)
   return False
  cmd=[str(staged_exe),'--apply-update','--install-root',str(install_root),'--staging-dir',str(extracted),'--old-pid',str(os.getpid()),'--config',cfg]
  subprocess.Popen(cmd,cwd=str(extracted),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  logging.info('self_update_spawned target_sha=%s',target_sha)
  return True
 except Exception as error:
  logging.warning('self_update_failed target_sha=%s error=%s',target_sha,error)
  report_update_status(client,credential,'failed',target_sha,str(error))
  return False

def _copy_agent_tree(source_dir,target_dir):
 target_dir.mkdir(parents=True,exist_ok=True)
 for item in source_dir.iterdir():
  if item.name.casefold() in PRESERVED_AGENT_ITEMS:continue
  dest=target_dir/item.name
  if item.is_dir():
   if dest.exists():shutil.rmtree(dest)
   shutil.copytree(item,dest,dirs_exist_ok=True)
  else:
   shutil.copy2(item,dest)

def apply_update(install_root,staging_dir,old_pid=None,config_path=None,launch=True):
 install_root=Path(install_root).resolve()
 staging_dir=Path(staging_dir).resolve()
 log_path=install_root/'update-agent.log'
 def record(msg):
  try:
   with log_path.open('a',encoding='utf-8') as f:f.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+msg+'\n')
  except OSError:pass
 record(f'Memulai apply_update dari {staging_dir}')
 if old_pid:
  import psutil
  deadline=time.monotonic()+20
  while time.monotonic()<deadline and psutil.pid_exists(int(old_pid)):
   time.sleep(0.25)
 target_agent=install_root/'SIMONAgent'
 staged_agent=staging_dir/'SIMONAgent'
 if not (staged_agent/'SIMONAgent.exe').is_file():
  raise RuntimeError('SIMONAgent.exe baru tidak ditemukan di staging')
 backup_dir=staging_dir.parent/'backup-agent'
 if backup_dir.exists():shutil.rmtree(backup_dir,ignore_errors=True)
 backup_dir.mkdir(parents=True,exist_ok=True)
 if target_agent.exists():
  for item in target_agent.iterdir():
   if item.name.casefold() in PRESERVED_AGENT_ITEMS:continue
   dest=backup_dir/item.name
   if item.is_dir():shutil.copytree(item,dest,dirs_exist_ok=True)
   elif item.is_file():shutil.copy2(item,dest)
 try:
  _copy_agent_tree(staged_agent,target_agent)
  for item in staging_dir.iterdir():
   if item.is_dir() or item.name.casefold() in PRESERVED_ROOT_FILES:continue
   if item.name.casefold()=='ca.crt' and (install_root/'ca.crt').exists():continue
   shutil.copy2(item,install_root/item.name)
  cfg=Path(config_path) if config_path else (install_root/'config.json')
  if launch:
   args=[str(target_agent/'SIMONAgent.exe'),'--background']
   if cfg.exists():args.extend(['--config',str(cfg)])
   res=subprocess.run(args,cwd=str(install_root),capture_output=True,text=True,timeout=25,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if res.returncode!=0:raise RuntimeError(res.stderr.strip() or res.stdout.strip() or f'Exit {res.returncode}')
  record('Update agent berhasil diterapkan.')
 except Exception as error:
  record('Update gagal, memulihkan backup: '+str(error))
  if backup_dir.exists():
   try:_copy_agent_tree(backup_dir,target_agent)
   except Exception as restore_err:record('Gagal memulihkan backup: '+str(restore_err))
   if launch:
    cfg=Path(config_path) if config_path else (install_root/'config.json')
    args=[str(target_agent/'SIMONAgent.exe'),'--background']
    if cfg.exists():args.extend(['--config',str(cfg)])
    subprocess.Popen(args,cwd=str(install_root),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  raise

def apply_update_cli():
 parser=argparse.ArgumentParser()
 parser.add_argument('--apply-update',action='store_true')
 parser.add_argument('--install-root',required=True)
 parser.add_argument('--staging-dir',required=True)
 parser.add_argument('--old-pid',type=int,default=0)
 parser.add_argument('--config',default='')
 parser.add_argument('--no-launch',action='store_true')
 args=parser.parse_args()
 apply_update(args.install_root,args.staging_dir,old_pid=args.old_pid or None,config_path=args.config or None,launch=not args.no_launch)
