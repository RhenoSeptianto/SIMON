"""Native user startup: no PowerShell runtime required."""
import atexit,ctypes,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path

_MUTEX=None

def active_service():
 if sys.platform!='win32':return None
 import win32service,pywintypes
 manager=win32service.OpenSCManager(None,None,win32service.SC_MANAGER_CONNECT)
 try:
  try:service=win32service.OpenService(manager,'SIMONAgent',win32service.SERVICE_QUERY_STATUS|win32service.SERVICE_QUERY_CONFIG)
  except pywintypes.error as error:
   if error.winerror==1060:return None
   raise
  try:
   if win32service.QueryServiceStatus(service)[1] in (win32service.SERVICE_STOPPED,win32service.SERVICE_STOP_PENDING):return None
   return win32service.QueryServiceConfig(service)[3]
  finally:win32service.CloseServiceHandle(service)
 finally:win32service.CloseServiceHandle(manager)

def conflicting_agent(server):
 from urllib.parse import urlsplit
 # Isolated loopback test/development servers have their own namespace.
 if urlsplit(server).hostname in ('127.0.0.1','localhost','::1'):return None
 if os.getenv('SIAMS_WINDOWS_SERVICE')!='1':
  service=active_service()
  if service:return 'Service SIMONAgent masih aktif: '+service+'. Hentikan/nonaktifkan service lama sebelum memakai mode Startup.'
 import psutil
 for process in psutil.process_iter(['pid','name','cmdline']):
  if process.pid==os.getpid() or (process.info['name'] or '').lower()!='simonagent.exe':continue
  command=process.info['cmdline'] or []
  if any(flag in command for flag in ('--background','--install-user','--check-connection','--diagnose','--once','--service')):continue
  if '--config' in command:
   try:
    settings=json.loads(Path(command[command.index('--config')+1]).read_text(encoding='utf-8-sig'))
    if settings.get('server','').rstrip('/').casefold()==server.rstrip('/').casefold():
     return 'Agent lain masih aktif (PID '+str(process.pid)+') memakai '+command[command.index('--config')+1]+'. Hentikan agent lama dahulu; jangan buat UUID baru.'
   except (OSError,ValueError,IndexError):continue
 return None

def single_instance(state,server):
 global _MUTEX
 if sys.platform!='win32' or not getattr(sys,'frozen',False):return True
 conflict=conflicting_agent(server)
 if conflict:
  import logging
  logging.warning('duplicate_agent_blocked: %s',conflict);return False
 import win32event,win32api,win32security,pywintypes
 security=pywintypes.SECURITY_ATTRIBUTES()
 security.SECURITY_DESCRIPTOR=win32security.ConvertStringSecurityDescriptorToSecurityDescriptor('D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;AU)',1)
 # Global spans logon sessions; the key deliberately excludes installation/state folders.
 name='Global\\SIMONAgent-'+hashlib.sha256(server.rstrip('/').casefold().encode()).hexdigest()
 handle=win32event.CreateMutex(security,False,name)
 if win32api.GetLastError()==183:handle.Close();return False
 _MUTEX=handle;atexit.register(handle.Close);return True

def background(state,config_path=None):
 state=Path(state);state.mkdir(parents=True,exist_ok=True)
 root=Path(config_path).resolve().parent if config_path else state.parent
 log=root/'startup.log'
 if log.exists() and log.stat().st_size>1048576:log.replace(root/'startup.previous.log')
 arguments=[arg for arg in sys.argv[1:] if arg!='--background']
 try:
  with log.open('ab',buffering=0) as output:
   worker=subprocess.Popen([sys.executable,*arguments],cwd=Path(sys.executable).parent,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,env={**os.environ,'SIAMS_WORKER_CAPTURE':'1'},creationflags=subprocess.CREATE_NO_WINDOW)
   output.write((time.strftime('%Y-%m-%d %H:%M:%S')+' Agent dimulai PID '+str(worker.pid)+'\n').encode())
  time.sleep(1)
  if worker.poll() is None:(root/'background.pid').write_text(str(worker.pid),encoding='ascii')
  if worker.poll() not in (None,0):raise RuntimeError('Agent berhenti, exit '+str(worker.returncode)+'. Lihat '+str(log))
  print('Agent diluncurkan tanpa jendela. Log: '+str(log))
 except Exception as error:
  with log.open('a',encoding='utf-8') as output:output.write('GAGAL: '+str(error)+'\n')
  raise

def create_shortcut(exe,config,startup):
 import win32com.client
 path=Path(startup)/'SIMON Agent.lnk'
 shell=win32com.client.Dispatch('WScript.Shell')
 link=shell.CreateShortCut(str(path))
 link.TargetPath=str(exe)
 link.Arguments=subprocess.list2cmdline(['--background','--config',str(config)])
 link.WorkingDirectory=str(Path(config).parent)
 link.WindowStyle=7;link.Description='SIMON monitoring - otomatis saat user login'
 link.Save()
 return path

def startup_folder():
 path=ctypes.create_unicode_buffer(32768)
 result=ctypes.windll.shell32.SHGetFolderPathW(None,7,None,0,path)
 if result!=0:raise OSError('Folder Startup user tidak dapat dibaca: '+str(result))
 return Path(path.value)

def install(root,store_code=None,startup=None,launch=True):
 root=Path(root).resolve();config=root/'config.json';exe=root/'SIMONAgent'/'SIMONAgent.exe'
 log=root/'install-user.log'
 def record(message):
  print(message,flush=True)
  with log.open('a',encoding='utf-8') as stream:stream.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+message+'\n')
 try:
  record('Instalasi native SIMON dimulai (tanpa PowerShell).')
  if not exe.is_file() or not (root/'ca.crt').is_file():raise ValueError('Paket tidak lengkap: EXE/ca.crt tidak ditemukan.')
  legacy=Path(os.environ.get('LOCALAPPDATA',str(root)))/'SIMON'
  previous=config if config.exists() else legacy/'config.json'
  settings=json.loads(previous.read_text(encoding='utf-8-sig')) if previous.exists() else {}
  if store_code is None:store_code=input('Kode store'+(' [Enter tetap '+str(settings['store_code'])+']' if settings.get('store_code') else '')+': ').strip() or settings.get('store_code','')
  store_code=str(store_code).strip()
  if not store_code or len(store_code)>40:raise ValueError('Kode store wajib diisi, maksimal 40 karakter.')
  conflict=conflicting_agent(settings.get('server','https://172.18.123.92:8443'))
  if conflict:raise ValueError(conflict)
  state=root/'SIMONAgent'/'data';old=legacy/'data'
  if not (state/'identity.json').exists() and (old/'identity.json').exists():
   import psutil
   for process in psutil.process_iter(['exe']):
    if process.info['exe'] and Path(process.info['exe']).resolve()==exe:raise ValueError('Tutup agent lama terlebih dahulu sebelum migrasi identitas.')
   shutil.copytree(old,state,dirs_exist_ok=True);record('Identitas lama disalin ke D; sumber tidak dihapus.')
  state.mkdir(parents=True,exist_ok=True)
  settings.update(server=settings.get('server','https://172.18.123.92:8443'),ca_file='ca.crt',state=str(state),store_code=store_code,sentinel_xml=str(exe.parent/'HDSentinel.xml'))
  temporary=config.with_suffix('.json.tmp');temporary.write_text(json.dumps(settings,indent=2),encoding='utf-8');temporary.replace(config)
  link=create_shortcut(exe,config,startup or startup_folder())
  record('Startup EXE langsung berhasil dibuat: '+str(link))
  record('Kode store: '+store_code+'; XML: '+settings['sentinel_xml'])
  if launch:
   result=subprocess.run([str(exe),'--background','--config',str(config)],capture_output=True,text=True,timeout=20)
   record(result.stdout.strip())
   if result.returncode:raise RuntimeError(result.stderr.strip() or 'Peluncur gagal. Lihat startup.log.')
  record('Selesai. Agent otomatis setelah user login. Semua data/log berada di '+str(root))
 except Exception as error:
  record('GAGAL: '+str(error));raise

def install_cli():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--install-user',action='store_true');parser.add_argument('--store-code')
 parser.add_argument('--startup-folder',help=argparse.SUPPRESS)
 args=parser.parse_args()
 try:install(Path(sys.executable).parent.parent,args.store_code,startup=args.startup_folder)
 except Exception as error:print('INSTALASI GAGAL: '+str(error),file=sys.stderr);raise SystemExit(1)
