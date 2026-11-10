"""Download the fixed GitHub agent asset and wrap it with the office public CA."""
import hashlib,json,re,time
from pathlib import Path
import httpx
from tools.make_agent_package import make_package,REQUIRED_CAPABILITIES
from tools.update_worker import read_json,write_json

ASSET_URL='https://github.com/RhenoSeptianto/SIMON/releases/download/agent-latest/SIMONAgent-template.zip'
MAX_TEMPLATE_BYTES=100*1024*1024

class AgentPackageError(Exception):pass

def folder(data):return Path(data)/'agent-package'

def status(data,current_sha=''):
 base=folder(data);metadata=read_json(base/'status.json');package=base/'SIMONAgent-store.zip'
 ready=bool(metadata.get('source_sha')==current_sha and package.is_file() and metadata.get('package_sha256')==hashlib.sha256(package.read_bytes()).hexdigest())
 return {**metadata,'ready':ready,'current_sha':current_sha,'download':'/api/system/agent-package/download' if ready else None}

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
  result={'source_sha':current_sha,'exe_sha256':metadata['exe_sha256'],'package_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'size':output.stat().st_size,'created_at':time.time(),'filename':'SIMONAgent-store.zip','error':None}
  write_json(base/'status.json',result);return {**result,'ready':True,'download':'/api/system/agent-package/download'}
 except Exception as error:
  previous=read_json(base/'status.json');previous.update(error=str(error),failed_at=time.time());write_json(base/'status.json',previous)
  if isinstance(error,AgentPackageError):raise
  raise AgentPackageError(str(error))
 finally:template.unlink(missing_ok=True);lock.unlink(missing_ok=True)
