"""Super-admin update API support; worker runs separately via Task Scheduler."""
import json,os,subprocess,time,uuid
from pathlib import Path
from tools.update_worker import BUSY,check_latest,read_json,write_json

class UpdateError(Exception):pass

def folder(data):return Path(data)/'updater'

def status(data,root):
 base=folder(data);configuration=read_json(base/'config.json')
 current=read_json(base/'current.json');state=read_json(base/'status.json',{'state':'idle','message':'Klik Cek update untuk memeriksa versi terbaru.'})
 ready=bool(configuration and (base/'worker.py').is_file() and (base/'task-control.ps1').is_file() and (base/'installed.json').is_file())
 try:version=(Path(root)/'VERSION').read_text(encoding='utf-8-sig').strip()
 except FileNotFoundError:version='0.1.0'
 return {'ready':ready,'version':version,'current':current.get('sha',os.getenv('SIAMS_BUILD_SHA','')),'check':read_json(base/'checked.json'),'job':state,'busy':state.get('state') in BUSY or (base/'request.json').exists(),'maintenance':(base/'maintenance.json').exists(),'setup_message':None if ready else 'Helper belum dipasang. Jalankan setup-updater.bat sekali sebagai Administrator di PC server kantor.'}

def configuration(data,database):
 base=folder(data);config=read_json(base/'config.json')
 if not config or not (base/'worker.py').exists() or not (base/'installed.json').exists():raise UpdateError('Helper update belum dipasang pada server.')
 if Path(config['database']).resolve()!=Path(database).resolve():raise UpdateError('Database server berbeda dari konfigurasi helper. Pasang ulang helper untuk lokasi database yang benar.')
 return config

def check(data,database):
 config=configuration(data,database);base=folder(data)
 if (base/'request.json').exists() or (base/'maintenance.json').exists():raise UpdateError('Proses update/pemulihan masih berjalan.')
 return check_latest(config)

def start(data,database,target,actor,runner=None):
 config=configuration(data,database);base=folder(data);checked=read_json(base/'checked.json')
 if not checked.get('available') or checked.get('latest')!=target:raise UpdateError('Versi belum diperiksa atau tidak ada update. Klik Cek update dahulu.')
 if time.time()-checked.get('checked_at',0)>1800:raise UpdateError('Hasil pemeriksaan sudah kedaluwarsa. Klik Cek update lagi.')
 if (base/'maintenance.json').exists():raise UpdateError('Pemulihan sebelumnya belum selesai. Periksa log sebelum update lagi.')
 request={'id':uuid.uuid4().hex,'target':target,'actor':str(actor),'created_at':time.time()}
 path=base/'request.json'
 try:
  with path.open('x',encoding='utf-8') as output:json.dump(request,output)
 except FileExistsError:raise UpdateError('Sudah ada update dalam antrean atau sedang berjalan.')
 try:
  write_json(base/'status.json',{'state':'queued','message':'Update masuk antrean helper. Server akan restart sementara.','job_id':request['id'],'target':target,'updated_at':time.time()})
  if runner:runner()
  else:
   result=subprocess.run(['schtasks.exe','/Run','/TN','SIMONUpdater'],capture_output=True,text=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if result.returncode:raise UpdateError((result.stderr or result.stdout).strip())
 except Exception as error:
  path.unlink(missing_ok=True);write_json(base/'status.json',{'state':'failed','message':'Helper tidak dapat dijalankan. Versi lama tetap berjalan.','error':str(error),'updated_at':time.time()})
  raise UpdateError('Helper tidak dapat dijalankan: '+str(error))
 return request
