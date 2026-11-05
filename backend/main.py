import os, json, secrets, hashlib, hmac, time, csv, io
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, Text, UniqueConstraint, inspect
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.getenv('SIAMS_DATA',str(ROOT/'data'))); DATA.mkdir(parents=True,exist_ok=True)
engine=create_engine(os.getenv('DATABASE_URL','sqlite:///'+str(DATA/'siams.db')), **({'connect_args':{'check_same_thread':False}} if not os.getenv('DATABASE_URL') else {}))
DB=sessionmaker(bind=engine); Base=declarative_base()
def now(): return time.time()
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True); name=Column(String); username=Column(String,unique=True); password=Column(String); role=Column(String); active=Column(Integer,default=1); stores=Column(Text,default='[]')
 access=relationship('UserDeviceAccess',lazy='selectin',cascade='all, delete-orphan')
class UserDeviceAccess(Base):
 __tablename__='user_device_access'
 user_id=Column(Integer,ForeignKey('users.id'),primary_key=True); device_id=Column(Integer,ForeignKey('devices.id'),primary_key=True)
class Store(Base):
 __tablename__='stores'
 id=Column(Integer,primary_key=True); code=Column(String,unique=True); name=Column(String); area=Column(String,default=''); region=Column(String,default=''); active=Column(Integer,default=1)
class Device(Base):
 __tablename__='devices'
 id=Column(Integer,primary_key=True); uuid=Column(String,unique=True); hostname=Column(String); ip=Column(String); serial=Column(String); status=Column(String,default='pending'); store_id=Column(Integer,ForeignKey('stores.id'),nullable=True); claim=Column(String); credential=Column(String,nullable=True); created=Column(Float,default=now); last_seen=Column(Float,default=0); inventory=Column(Text,default='{}'); metrics=Column(Text,default='{}')
class DeletedDevice(Base):
 __tablename__='deleted_devices'
 uuid=Column(String,primary_key=True); deleted_at=Column(Float,default=now)
class Sample(Base):
 __tablename__='telemetry'
 id=Column(Integer,primary_key=True); device_id=Column(Integer,ForeignKey('devices.id'),index=True); event_id=Column(String,unique=True); collected=Column(Float,index=True); received=Column(Float,default=now); payload=Column(Text)
class LoginSession(Base):
 __tablename__='sessions'
 token=Column(String,primary_key=True); user_id=Column(Integer,ForeignKey('users.id')); expires=Column(Float)
class Audit(Base):
 __tablename__='audit_logs'
 id=Column(Integer,primary_key=True); actor=Column(String); action=Column(String); target=Column(String); timestamp=Column(Float,default=now)
class Alert(Base):
 __tablename__='alerts'
 id=Column(Integer,primary_key=True); device_id=Column(Integer,ForeignKey('devices.id'),index=True); category=Column(String); message=Column(String); status=Column(String,default='active'); created=Column(Float,default=now)
migrate_access=not inspect(engine).has_table('user_device_access')
Base.metadata.create_all(engine)
with DB() as migration:
 if migrate_access:
  for old_user in migration.query(User).all():
   for old_device in migration.query(Device).all():
    if old_device.store_id is not None and old_device.store_id in json.loads(old_user.stores):
     migration.add(UserDeviceAccess(user_id=old_user.id,device_id=old_device.id))
 migration.query(Device).filter_by(status='pending').update({'status':'approved'})
 changed_roles=[x.id for x in migration.query(User).filter(User.role.notin_(['super_admin','ts'])).all()]
 if changed_roles:
  migration.query(User).filter(User.id.in_(changed_roles)).update({'role':'ts'},synchronize_session=False)
  migration.query(LoginSession).filter(LoginSession.user_id.in_(changed_roles)).delete(synchronize_session=False)
 migration.commit()
app=FastAPI(title='SIMON - Sistem Monitoring',version='0.1.0')
def db():
 with DB() as s: yield s
def digest(v): return hashlib.sha256(v.encode()).hexdigest()
def password(v,salt=None):
 salt=salt or secrets.token_hex(16)
 return salt+':'+hashlib.scrypt(v.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def audit(s,actor,action,target): s.add(Audit(actor=str(actor),action=action,target=str(target)))
def user(request:Request,s:Session=Depends(db)):
 token=request.cookies.get('siams_session',''); session=s.get(LoginSession,digest(token))
 if not session or session.expires<now(): raise HTTPException(401,'Silakan login')
 u=s.get(User,session.user_id)
 if not u or not u.active: raise HTTPException(401,'Akun nonaktif')
 if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('x-siams-request')!='1': raise HTTPException(403,'Header CSRF diperlukan')
 return u
def admin(u:User=Depends(user)):
 if u.role not in ('super_admin',): raise HTTPException(403,'Akses admin diperlukan')
 return u
def allowed(u,d): return u.role in ('super_admin',) or any(a.device_id==d.id for a in u.access)
def visible(s,u): return [d for d in s.query(Device).all() if allowed(u,d)]
def device(s,id,u):
 d=s.get(Device,id)
 if not d or not allowed(u,d): raise HTTPException(404,'Perangkat tidak ditemukan')
 return d
def serialize(d):
 return {'id':d.id,'uuid':d.uuid,'hostname':d.hostname,'ip':d.ip,'serial':d.serial,'status':d.status,'store_id':d.store_id,'online':d.status=='approved' and now()-d.last_seen<int(os.getenv('OFFLINE_SECONDS','420')),'last_seen':d.last_seen,'inventory':json.loads(d.inventory),'metrics':json.loads(d.metrics)}
class Login(BaseModel):
 username:str; password:str
attempts={}
def limit(key,count=20):
 t=now(); items=[x for x in attempts.get(key,[]) if t-x<60]
 if len(items)>=count: raise HTTPException(429,'Terlalu banyak permintaan')
 attempts[key]=items+[t]
@app.post('/api/login')
def login(v:Login,request:Request,response:Response,s:Session=Depends(db)):
 limit(('login',request.client.host))
 u=s.query(User).filter_by(username=v.username).first()
 if not u or not u.active or not hmac.compare_digest(u.password,password(v.password,u.password.split(':')[0])): raise HTTPException(401,'Login tidak valid')
 token=secrets.token_urlsafe(32); s.add(LoginSession(token=digest(token),user_id=u.id,expires=now()+28800)); s.commit()
 response.set_cookie('siams_session',token,httponly=True,samesite='strict',secure=os.getenv('SIAMS_PRODUCTION')=='1',max_age=28800)
 return {'id':u.id,'name':u.name,'role':u.role}
@app.post('/api/logout')
def logout(request:Request,response:Response,s:Session=Depends(db)):
 if request.headers.get('x-siams-request')!='1': raise HTTPException(403,'Header CSRF diperlukan')
 s.query(LoginSession).filter_by(token=digest(request.cookies.get('siams_session',''))).delete(); s.commit(); response.delete_cookie('siams_session'); return {'ok':True}
@app.get('/api/me')
def me(u=Depends(user)): return {'id':u.id,'name':u.name,'role':u.role}
class ChangePassword(BaseModel):
 current_password:str
 new_password:str=Field(min_length=1)

@app.post('/api/me/password')
def change_password(v:ChangePassword,response:Response,u=Depends(user),s:Session=Depends(db)):
 limit(('change_password',u.id),10)
 if not hmac.compare_digest(u.password,password(v.current_password,u.password.split(':')[0])):
  raise HTTPException(400,'Password saat ini tidak cocok')
 u.password=password(v.new_password)
 s.query(LoginSession).filter_by(user_id=u.id).delete()
 audit(s,u.id,'change_own_password',u.id); s.commit()
 response.delete_cookie('siams_session')
 return {'ok':True,'message':'Password berhasil diubah. Silakan login kembali.'}

class UserInput(BaseModel):
 name:str; username:str; password:str|None=None; role:str; devices:list[int]=[]; active:bool=True
ROLES={'super_admin','ts'}
@app.get('/api/users')
def users(u=Depends(admin),s:Session=Depends(db)):
 return [{'id':x.id,'name':x.name,'username':x.username,'role':x.role,'devices':[] if x.role in ('super_admin',) else [a.device_id for a in x.access],'active':bool(x.active)} for x in s.query(User).all()]
def validate_user(v,u,s):
 if v.role not in ROLES: raise HTTPException(422,'Role tidak valid')
 if u.role!='super_admin' and v.role in ('super_admin',): raise HTTPException(403)
 if v.password is not None and len(v.password)<1: raise HTTPException(422,'Password tidak boleh kosong')
 if v.role not in ('super_admin',) and any(not s.get(Device,x) for x in v.devices): raise HTTPException(422,'PC tidak valid')
@app.post('/api/users')
def create_user(v:UserInput,u=Depends(admin),s:Session=Depends(db)):
 validate_user(v,u,s)
 if s.query(User).filter_by(username=v.username).first(): raise HTTPException(409,'Username sudah digunakan')
 if not v.password: raise HTTPException(422,'Password wajib diisi')
 x=User(name=v.name,username=v.username,password=password(v.password),role=v.role,active=v.active); x.access=[UserDeviceAccess(device_id=id) for id in (set(v.devices) if v.role not in ('super_admin',) else set())]; s.add(x); audit(s,u.id,'create_user',v.username); s.commit(); return {'id':x.id}
@app.put('/api/users/{id}')
def edit_user(id:int,v:UserInput,u=Depends(admin),s:Session=Depends(db)):
 validate_user(v,u,s); x=s.get(User,id)
 if not x: raise HTTPException(404)
 if u.role!='super_admin' and x.role in ('super_admin',): raise HTTPException(403)
 if x.id==u.id and (not v.active or v.role!=u.role): raise HTTPException(409,'Jangan nonaktifkan atau ubah role akun sendiri')
 if s.query(User).filter(User.username==v.username,User.id!=id).first(): raise HTTPException(409)
 security_changed=bool(v.password) or x.role!=v.role or bool(x.active)!=v.active
 for k in ('name','username','role','active'): setattr(x,k,getattr(v,k))
 if v.password: x.password=password(v.password)
 x.access=[UserDeviceAccess(device_id=id) for id in (set(v.devices) if v.role not in ('super_admin',) else set())]
 if security_changed: s.query(LoginSession).filter_by(user_id=id).delete()
 audit(s,u.id,'edit_user',id); s.commit(); return {'ok':True}
@app.get('/api/devices')
def devices(q:str='',store_id:int|None=None,page:int=1,limit_:int=50,u=Depends(user),s:Session=Depends(db)):
 rows=[serialize(d) for d in visible(s,u) if q.lower() in (d.hostname+' '+(d.ip or '')).lower() and (store_id is None or d.store_id==store_id)]
 size=max(1,min(limit_,200)); start=(max(page,1)-1)*size
 return {'total':len(rows),'items':rows[start:start+size]}
@app.get('/api/devices/{id}')
def detail(id:int,u=Depends(user),s:Session=Depends(db)): return serialize(device(s,id,u))
class DeviceAssignments(BaseModel):
 user_ids:list[int]=Field(default_factory=list)

@app.get('/api/devices/{id}/assignments')
def device_assignments(id:int,u=Depends(admin),s:Session=Depends(db)):
 device(s,id,u)
 assigned={a.user_id for a in s.query(UserDeviceAccess).filter_by(device_id=id).all()}
 return [{'id':x.id,'name':x.name,'username':x.username,'active':bool(x.active),'assigned':x.id in assigned} for x in s.query(User).filter_by(role='ts').order_by(User.name).all()]

@app.put('/api/devices/{id}/assignments')
def save_device_assignments(id:int,v:DeviceAssignments,u=Depends(admin),s:Session=Depends(db)):
 device(s,id,u)
 selected=set(v.user_ids)
 targets=s.query(User).filter(User.id.in_(selected)).all()
 if len(targets)!=len(selected) or any(x.role!='ts' for x in targets): raise HTTPException(422,'Pilih user TS yang valid')
 existing=s.query(UserDeviceAccess).filter_by(device_id=id).all()
 old={a.user_id for a in existing}
 for a in existing:
  if a.user_id not in selected: s.delete(a)
 for user_id in selected-old: s.add(UserDeviceAccess(user_id=user_id,device_id=id))
 audit(s,u.id,'assign_device_users',json.dumps({'device_id':id,'old':sorted(old),'new':sorted(selected)})); s.commit()
 return {'ok':True,'user_ids':sorted(selected)}

@app.delete('/api/devices/{id}')
def delete_device(id:int,u=Depends(admin),s:Session=Depends(db)):
 d=device(s,id,u)
 # Keep a UUID tombstone so an old agent cannot recreate a deleted PC.
 if not s.get(DeletedDevice,d.uuid): s.add(DeletedDevice(uuid=d.uuid))
 s.query(UserDeviceAccess).filter_by(device_id=id).delete(synchronize_session=False)
 s.query(Sample).filter_by(device_id=id).delete(synchronize_session=False)
 s.query(Alert).filter_by(device_id=id).delete(synchronize_session=False)
 audit(s,u.id,'delete_device',json.dumps({'id':id,'hostname':d.hostname,'uuid':d.uuid}))
 s.delete(d); s.commit()
 return {'ok':True}
@app.get('/api/devices/{id}/history')
def history(id:int,hours:int=Query(default=24,ge=1,le=168),u=Depends(user),s:Session=Depends(db)):
 device(s,id,u)
 rows=s.query(Sample).filter(Sample.device_id==id,Sample.collected>=now()-hours*3600).order_by(Sample.collected.desc()).limit(5000).all()
 return [{'collected_at':x.collected,**json.loads(x.payload)} for x in reversed(rows)]
@app.post('/api/devices/{id}/{action}')
def approve(id:int,action:str,u=Depends(admin),s:Session=Depends(db)):
 if action not in ('approve','reject','revoke'): raise HTTPException(404)
 d=device(s,id,u); d.status={'approve':'approved','reject':'rejected','revoke':'revoked'}[action]
 if action!='approve': d.credential=None
 audit(s,u.id,action,id); s.commit(); return {'ok':True}
class Enrollment(BaseModel):
 uuid:str=Field(min_length=32,max_length=64); claim:str=Field(min_length=40,max_length=200); inventory:dict
@app.post('/api/agent/enroll')
def enroll(v:Enrollment,request:Request,s:Session=Depends(db)):
 limit(('enroll',request.client.host),10)
 if len(json.dumps(v.inventory))>100000: raise HTTPException(413)
 if s.get(DeletedDevice,v.uuid): raise HTTPException(403,'Perangkat sudah dihapus oleh admin')
 d=s.query(Device).filter_by(uuid=v.uuid).first()
 if d:
  if not hmac.compare_digest(d.claim,digest(v.claim)): raise HTTPException(403)
  if d.status=='approved': d.last_seen=now(); s.commit()
  return {'status':d.status}
 i=v.inventory; d=Device(uuid=v.uuid,claim=digest(v.claim),hostname=str(i.get('hostname','Unknown'))[:160],ip=str(i.get('primary_ip',''))[:64],serial=str(i.get('bios_serial',''))[:160],inventory=json.dumps(i),status='approved',last_seen=now()); s.add(d); audit(s,'agent','auto_enrollment',v.uuid); s.commit(); return {'status':'approved'}
class Claim(BaseModel):
 uuid:str; claim:str
@app.post('/api/agent/claim')
def claim(v:Claim,request:Request,s:Session=Depends(db)):
 limit(('claim',request.client.host),30); d=s.query(Device).filter_by(uuid=v.uuid).first()
 if not d or not hmac.compare_digest(d.claim,digest(v.claim)): raise HTTPException(403)
 if d.status!='approved': return {'status':d.status}
 # Deterministic per-device secret makes a lost claim response retryable.
 token=hmac.new(v.claim.encode(),('siams-device:'+v.uuid).encode(),hashlib.sha256).hexdigest()
 if d.credential:
  return {'status':'approved','credential':token} if hmac.compare_digest(d.credential,digest(token)) else {'status':'credential_issued'}
 d.credential=digest(token); audit(s,'agent','issue_credential',d.id); s.commit(); return {'status':'approved','credential':token}
def agent(request:Request,s:Session=Depends(db)):
 token=request.headers.get('authorization','').removeprefix('Bearer ')
 d=s.query(Device).filter_by(credential=digest(token),status='approved').first()
 if not d: raise HTTPException(401,'Credential perangkat tidak valid')
 return d
class Telemetry(BaseModel):
 event_id:str=Field(max_length=80); collected_at:float; kind:str; payload:dict
@app.post('/api/agent/report')
def report(v:Telemetry,d=Depends(agent),s:Session=Depends(db)):
 if v.kind not in ('heartbeat','inventory','metrics','storage'): raise HTTPException(422)
 if len(json.dumps(v.payload))>200000: raise HTTPException(413)
 d=s.get(Device,d.id); d.last_seen=now()
 if v.kind=='inventory':
  d.inventory=json.dumps(v.payload); d.hostname=str(v.payload.get('hostname',d.hostname)); d.ip=str(v.payload.get('primary_ip',d.ip)); d.serial=str(v.payload.get('bios_serial',d.serial))
 elif v.kind!='heartbeat':
  if not s.query(Sample).filter_by(event_id=v.event_id).first():
   s.add(Sample(device_id=d.id,event_id=v.event_id,collected=v.collected_at,payload=json.dumps(v.payload)))
   m=json.loads(d.metrics)
   if v.collected_at>=m.get(v.kind+'_at',0): m.update(v.payload); m[v.kind+'_at']=v.collected_at; d.metrics=json.dumps(m)
   evaluate(s,d,m)
 s.query(Sample).filter(Sample.received<now()-int(os.getenv('RETENTION_DAYS','30'))*86400).delete(); s.commit(); return {'ok':True}
def evaluate(s,d,m):
 checks={'disk_free':(any(x.get('free_percent',100)<10 for x in m.get('volumes',[])),'Ruang disk kurang dari 10%'),'temperature':(any((x.get('temperature_c') or 0)>65 for x in m.get('disks',[])),'Suhu disk di atas 65 C'),'disk_health':(any(x.get('health_status') not in (None,'Healthy','Unknown') for x in m.get('disks',[])),'Kondisi physical disk perlu diperiksa')}
 for cat,(bad,msg) in checks.items():
  a=s.query(Alert).filter(Alert.device_id==d.id,Alert.category==cat,Alert.status!='resolved').first()
  if bad and not a: s.add(Alert(device_id=d.id,category=cat,message=msg))
  elif not bad and a: a.status='resolved'
@app.get('/api/alerts')
def alerts(u=Depends(user),s:Session=Depends(db)):
 ids=[x.id for x in visible(s,u)]; return [{'id':x.id,'device_id':x.device_id,'category':x.category,'message':x.message,'status':x.status,'created':x.created} for x in s.query(Alert).filter(Alert.device_id.in_(ids)).order_by(Alert.id.desc()).limit(500)]
@app.post('/api/alerts/{id}/acknowledge')
def ack(id:int,u=Depends(user),s:Session=Depends(db)):
 a=s.get(Alert,id)
 if not a: raise HTTPException(404)
 device(s,a.device_id,u); a.status='acknowledged'; audit(s,u.id,'ack_alert',id); s.commit(); return {'ok':True}
@app.get('/api/summary')
def summary(u=Depends(user),s:Session=Depends(db)):
 ds=[serialize(d) for d in visible(s,u)]; return {'devices':len(ds),'online':sum(d['online'] for d in ds),'offline':sum(d['status']=='approved' and not d['online'] for d in ds),'unassigned':sum(not s.query(UserDeviceAccess).filter_by(device_id=d['id']).first() for d in ds)}
@app.get('/api/reports/{format}')
def export(format:str,u=Depends(user),s:Session=Depends(db)):
 rows=[['Hostname','IP','Serial','Status','RAM bytes','Disks']]
 for d in visible(s,u):
  m=json.loads(d.metrics); rows.append([d.hostname,d.ip,d.serial,d.status,m.get('ram_total'),json.dumps(m.get('disks',[]))])
 rows=[["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in r] for r in rows]
 if format=='csv':
  f=io.StringIO(); csv.writer(f).writerows(rows); data=io.BytesIO(('\ufeff'+f.getvalue()).encode()); mime='text/csv'
 elif format=='xlsx':
  from openpyxl import Workbook
  w=Workbook(); sheet=w.active
  for r in rows: sheet.append(r)
  data=io.BytesIO(); w.save(data); data.seek(0); mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
 else: raise HTTPException(404)
 return StreamingResponse(data,media_type=mime,headers={'Content-Disposition':f'attachment; filename="simon-inventory.{format}"'})
@app.get('/api/audit')
def audits(u=Depends(admin),s:Session=Depends(db)): return [{'actor':x.actor,'action':x.action,'target':x.target,'timestamp':x.timestamp} for x in s.query(Audit).order_by(Audit.id.desc()).limit(200)]
def super_admin(u=Depends(user)):
 if u.role!='super_admin': raise HTTPException(403,'Hanya Super Admin')
 return u

def database_backup():
 import sqlite3
 if engine.dialect.name!='sqlite': raise HTTPException(501,'Backup ini khusus database SQLite')
 folder=DATA/'backups'; folder.mkdir(exist_ok=True)
 target=folder/('simon-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4)+'.db')
 connection=engine.raw_connection()
 try:
  with sqlite3.connect(target) as dest: connection.driver_connection.backup(dest)
 finally: connection.close()
 return target

@app.post('/api/database/backup')
def backup_database(u=Depends(super_admin),s:Session=Depends(db)):
 target=database_backup(); audit(s,u.id,'backup_database',target.name); s.commit()
 return FileResponse(target,media_type='application/octet-stream',filename=target.name)

class ResetDatabase(BaseModel):
 confirmation:str

@app.post('/api/database/reset')
def reset_database(v:ResetDatabase,u=Depends(super_admin),s:Session=Depends(db)):
 if v.confirmation!='RESET': raise HTTPException(422,'Ketik RESET untuk konfirmasi')
 # Preserve accounts/passwords and audit. Back up before removing monitoring data.
 target=database_backup()
 for model in (UserDeviceAccess,Sample,Alert,Device,DeletedDevice,Store): s.query(model).delete(synchronize_session=False)
 audit(s,u.id,'reset_database',target.name); s.commit()
 return {'ok':True,'backup':target.name,'message':'Data monitoring direset. Akun dan audit tetap tersimpan.'}

app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
@app.get('/')
def index(): return FileResponse(ROOT/'frontend'/'index.html')
