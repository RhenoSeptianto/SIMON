"""Bind local credentials to the Windows installation; never transmit raw MachineGuid."""
import hashlib,json,os,platform,secrets,uuid,time
from pathlib import Path

def machine_id():
 if os.name=='nt':
  import winreg
  with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
   value=winreg.QueryValueEx(key,'MachineGuid')[0]
 else:value=platform.node()
 return hashlib.sha256(('simon-machine-v1:'+str(value)).encode()).hexdigest()

def write_identity(path,value):
 temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
 temporary.write_text(json.dumps(value),encoding='utf-8');temporary.replace(path)

def ensure_identity(state,rotate=False):
 state=Path(state);state.mkdir(parents=True,exist_ok=True);path=state/'identity.json'
 current=machine_id()
 value=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else None
 copied=value and value.get('machine_id') and value['machine_id']!=current
 if copied or rotate:
  # Keep all old credentials/queued reports outside the active state, never send their queue.
  backup=state.parent/('data-other-machine-'+str(time.time_ns()))
  backup.mkdir()
  for name in ('identity.json','queue.db','queue.db-wal','queue.db-shm','queue.db-journal'):
   source=state/name
   if source.exists():source.replace(backup/name)
  value=None
 if value is None:value={'uuid':str(uuid.uuid4()),'claim':secrets.token_urlsafe(48)}
 value['machine_id']=current;write_identity(path,value)
 return value
