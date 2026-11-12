import os, json, secrets, hashlib, hmac, time, io, threading, contextlib, subprocess
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, ForeignKey, Float, Text, UniqueConstraint, inspect, text, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from backend.localization import localize_metrics
from backend.database import make_engine,database_descriptor

ROOT=Path(__file__).resolve().parents[1]
APP_VERSION=(ROOT/'VERSION').read_text(encoding='utf-8-sig').strip() if (ROOT/'VERSION').exists() else '0.1.0'
DATA=Path(os.getenv('SIAMS_DATA',str(ROOT/'data'))); DATA.mkdir(parents=True,exist_ok=True)
engine=make_engine()
DB=sessionmaker(bind=engine); Base=declarative_base()
REPORT_WRITE_LOCK=threading.RLock()
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
 id=Column(Integer,primary_key=True); store_code=Column(String(40),default='',nullable=False); store_code_key=Column(String(160),nullable=True); uuid=Column(String,unique=True); hostname=Column(String); ip=Column(String); serial=Column(String); status=Column(String,default='pending'); store_id=Column(Integer,ForeignKey('stores.id'),nullable=True); claim=Column(String); credential=Column(String,nullable=True); created=Column(Float,default=now); last_seen=Column(Float,default=0); inventory=Column(Text,default='{}'); metrics=Column(Text,default='{}')
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
# Add display-only store code to existing SQLite/PostgreSQL installations.
if 'store_code' not in {column['name'] for column in inspect(engine).get_columns('devices')}:
 with engine.begin() as connection: connection.execute(text("ALTER TABLE devices ADD COLUMN store_code VARCHAR(40) NOT NULL DEFAULT ''"))
# A nullable normalized key keeps blank legacy codes compatible; the DB enforces concurrent claims.
if 'store_code_key' not in {column['name'] for column in inspect(engine).get_columns('devices')}:
 with engine.begin() as connection: connection.execute(text('ALTER TABLE devices ADD COLUMN store_code_key VARCHAR(160)'))
with engine.begin() as connection: connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_device_store_code_key ON devices (store_code_key)'))
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
def agent_compatibility(inventory):
 version=str(inventory.get('agent_version') or '').strip();build=str(inventory.get('agent_build_sha') or '').strip().lower();expected=str(os.getenv('SIAMS_BUILD_SHA','') or current_update_sha()).strip().lower()
 valid_build=len(build)==40 and all(x in '0123456789abcdef' for x in build)
 valid_expected=len(expected)==40 and all(x in '0123456789abcdef' for x in expected)
 state='current' if valid_build and valid_expected and build==expected else 'outdated' if valid_build and valid_expected else 'unknown'
 return {'status':state,'label':{'current':'Agent terbaru','outdated':'Agent perlu diperbarui','unknown':'Versi agent tidak diketahui'}[state],'version':version or None,'build_sha':build if valid_build else None,'expected_sha':expected if valid_expected else None}
def serialize(d):
 inventory=json.loads(d.inventory)
 # Keep legacy agents online using their old grace window during gradual rollout.
 grace=420
 try:
  interval=float(inventory.get('heartbeat_interval_seconds',0))
  if 0<interval<86400:grace=max(45,interval*3+15)
 except (ValueError,TypeError):pass
 if os.getenv('OFFLINE_SECONDS'):grace=float(os.environ['OFFLINE_SECONDS'])
 return {'id':d.id,'uuid':d.uuid,'store_code':d.store_code,'hostname':d.hostname,'ip':d.ip,'serial':d.serial,'status':d.status,'store_id':d.store_id,'online':d.status=='approved' and now()-d.last_seen<grace,'last_seen':d.last_seen,'inventory':inventory,'agent':agent_compatibility(inventory),'metrics':localize_metrics(json.loads(d.metrics))}
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
 return {'id':u.id,'name':u.name,'role':u.role,'version':APP_VERSION,'disk_health_warning':float(os.getenv('SENTINEL_HEALTH_WARNING','80'))}
@app.post('/api/logout')
def logout(request:Request,response:Response,s:Session=Depends(db)):
 if request.headers.get('x-siams-request')!='1': raise HTTPException(403,'Header CSRF diperlukan')
 s.query(LoginSession).filter_by(token=digest(request.cookies.get('siams_session',''))).delete(); s.commit(); response.delete_cookie('siams_session'); return {'ok':True}
@app.get('/api/me')
def me(u=Depends(user)): return {'id':u.id,'name':u.name,'role':u.role,'version':APP_VERSION,'disk_health_warning':float(os.getenv('SENTINEL_HEALTH_WARNING','80'))}
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
def assigned_ts(s,device_ids):
 result={device_id:[] for device_id in device_ids}
 if result:
  for access,owner in s.query(UserDeviceAccess,User).join(User,User.id==UserDeviceAccess.user_id).filter(UserDeviceAccess.device_id.in_(result.keys()),User.role=='ts').order_by(User.name).all():result[access.device_id].append(owner.name)
 return result

def needs_attention(row):
 metrics=row.get('metrics') or {};disks=metrics.get('disks') or [];volumes=metrics.get('volumes') or []
 health=[float(d['health_percent']) for d in disks if d.get('source')=='sentinel' and d.get('health_percent') not in (None,'')]
 stale=metrics.get('storage_source')=='sentinel' and metrics.get('sentinel_status') not in (None,'fresh')
 hot=any(float(d.get('temperature_c') or 0)>65 for d in disks)
 low_space=any(float(v.get('free_percent',100 if v.get('used_percent') is None else 100-float(v['used_percent'])))<10 for v in volumes)
 return not row['online'] or bool(health and min(health)<float(os.getenv('SENTINEL_HEALTH_WARNING','80'))) or stale or hot or low_space

def device_priority(row):
 metrics=row.get('metrics') or {};disks=metrics.get('disks') or []
 health=[float(d['health_percent']) for d in disks if d.get('source')=='sentinel' and d.get('health_percent') not in (None,'')]
 critical=bool(health and min(health)<float(os.getenv('SENTINEL_HEALTH_WARNING','80')))
 hot=any(float(d.get('temperature_c') or 0)>65 for d in disks)
 stale=metrics.get('storage_source')=='sentinel' and metrics.get('sentinel_status') not in (None,'fresh')
 if critical:return (0,min(health),row['id'])
 if hot:return (1,0,row['id'])
 if not row['online']:return (2,row.get('last_seen') or 0,row['id'])
 if stale:return (3,0,row['id'])
 if row['agent']['status']!='current':return (4,0,row['id'])
 return (5,0,-row['id'])

@app.get('/api/devices')
def devices(q:str='',store_id:int|None=None,online:int|None=None,attention:int|None=None,unassigned:int|None=None,agent_state:str='',priority:bool=True,page:int=1,limit_:int=50,u=Depends(user),s:Session=Depends(db)):
 models=visible(s,u);assigned=assigned_ts(s,[d.id for d in models]);all_rows=[{**serialize(d),'ts_names':assigned[d.id]} for d in models]
 facets={'all':len(all_rows),'online':sum(d['online'] for d in all_rows),'offline':sum(not d['online'] for d in all_rows),'attention':sum(needs_attention(d) for d in all_rows),'unassigned':sum(len(d['ts_names'])==0 for d in all_rows),'agent_old':sum(d['agent']['status']!='current' for d in all_rows)}
 query=q.strip().casefold();rows=[]
 for row in all_rows:
  haystack=' '.join((row.get('hostname') or '',row.get('ip') or '',row.get('store_code') or '',*row.get('ts_names',[]))).casefold()
  if query not in haystack or (store_id is not None and row['store_id']!=store_id):continue
  if online is not None and row['online']!=(online==1):continue
  if attention is not None and needs_attention(row)!=(attention==1):continue
  if unassigned is not None and (len(row.get('ts_names',[]))==0)!=(unassigned==1):continue
  if agent_state=='old' and row['agent']['status']=='current':continue
  rows.append(row)
 if priority:rows.sort(key=device_priority)
 size=max(1,min(limit_,500)); start=(max(page,1)-1)*size
 return {'total':len(rows),'items':rows[start:start+size],'facets':facets}

class BulkDeviceAssignments(BaseModel):
 device_ids:list[int]=Field(min_length=1,max_length=500)
 user_id:int
 mode:str='replace'

@app.put('/api/devices/assignments/bulk')
def bulk_device_assignments(v:BulkDeviceAssignments,u=Depends(admin),s:Session=Depends(db)):
 ids=set(v.device_ids)
 if v.mode not in ('add','replace'):raise HTTPException(422,'Mode assignment tidak valid')
 target=s.get(User,v.user_id)
 if not target or target.role!='ts' or not target.active:raise HTTPException(422,'Pilih user TS aktif yang valid')
 found={d.id for d in s.query(Device).filter(Device.id.in_(ids)).all()}
 if found!=ids:raise HTTPException(422,'Ada perangkat yang tidak valid')
 if v.mode=='replace':s.query(UserDeviceAccess).filter(UserDeviceAccess.device_id.in_(ids)).delete(synchronize_session=False)
 existing={x.device_id for x in s.query(UserDeviceAccess).filter(UserDeviceAccess.user_id==target.id,UserDeviceAccess.device_id.in_(ids)).all()}
 for device_id in ids-existing:s.add(UserDeviceAccess(user_id=target.id,device_id=device_id))
 audit(s,u.id,'bulk_assign_devices',json.dumps({'device_ids':sorted(ids),'user_id':target.id,'mode':v.mode}));s.commit()
 return {'ok':True,'updated':len(ids),'user_id':target.id,'mode':v.mode}
@app.get('/api/devices/{id}')
def detail(id:int,u=Depends(user),s:Session=Depends(db)):
 d=device(s,id,u);return {**serialize(d),'ts_names':assigned_ts(s,[d.id])[d.id]}
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
 # Delete only the server record. An active agent may enroll again with its UUID.
 s.query(DeletedDevice).filter_by(uuid=d.uuid).delete(synchronize_session=False)
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
def store_conflict(code,owner=None):
 name=owner.hostname if owner else 'perangkat lain'
 return HTTPException(409,detail=f'Kode store {code} sudah digunakan oleh PC {name}. Gunakan kode lain atau lepaskan kode dari perangkat lama melalui admin.')

def set_store_code(s,d,value):
 code=str(value or '').strip()
 if len(code)>40: raise HTTPException(422,'Kode store maksimal 40 karakter')
 key=code.casefold()
 # Inspect legacy rows too: existing duplicates are retained, never silently deleted/moved.
 owner=next((other for other in s.query(Device).filter(Device.store_code!='').all() if other.id!=d.id and other.store_code.strip().casefold()==key),None) if key else None
 if owner: raise store_conflict(code,owner)
 d.store_code=code;d.store_code_key=key or None

def commit_store(s,code):
 try:s.commit()
 except IntegrityError:
  s.rollback()
  owner=s.query(Device).filter_by(store_code_key=str(code).strip().casefold()).first()
  if owner:raise store_conflict(code,owner)
  raise

def validate_machine(d,inventory):
 previous=json.loads(d.inventory or '{}')
 old_machine=previous.get('machine_id');new_machine=inventory.get('machine_id')
 old_serial=str(d.serial or previous.get('bios_serial') or '').strip().casefold()
 new_serial=str(inventory.get('bios_serial') or '').strip().casefold()
 invalid={'','unknown','none','n/a','default string','to be filled by o.e.m.','system serial number','0','00000000'}
 strong_serial=old_serial not in invalid and new_serial not in invalid
 mismatch=(old_machine and new_machine and old_machine!=new_machine) or (strong_serial and old_serial!=new_serial)
 if new_machine and not old_machine and old_serial not in invalid and new_serial in invalid:
  mismatch=mismatch or bool(inventory.get('hostname') and str(inventory['hostname']).casefold()!=str(d.hostname).casefold())
 if mismatch:raise HTTPException(409,detail={'code':'identity_mismatch','message':'Identitas agent milik PC '+str(d.hostname)+'. Folder data/credential tersalin ke PC berbeda. Jalankan installer terbaru untuk membuat identitas terpisah.'})
 # Legacy inventory updates cannot silently remove an established binding.
 if old_machine and not new_machine:inventory['machine_id']=old_machine

class Enrollment(BaseModel):
 uuid:str=Field(min_length=32,max_length=64); claim:str=Field(min_length=40,max_length=200); inventory:dict
@app.post('/api/agent/enroll')
def enroll(v:Enrollment,request:Request,s:Session=Depends(db)):
 limit(('enroll',request.client.host),10)
 if len(json.dumps(v.inventory))>100000: raise HTTPException(413)
 d=s.query(Device).filter_by(uuid=v.uuid).first()
 if d:
  if not hmac.compare_digest(d.claim,digest(v.claim)): raise HTTPException(403)
  validate_machine(d,v.inventory)
  if d.status=='approved':
   d.last_seen=now()
   if 'store_code' in v.inventory: set_store_code(s,d,v.inventory['store_code'])
   commit_store(s,d.store_code)
  return {'status':d.status}
 i=v.inventory; d=Device(uuid=v.uuid,claim=digest(v.claim),hostname=str(i.get('hostname','Unknown'))[:160],ip=str(i.get('primary_ip',''))[:64],serial=str(i.get('bios_serial',''))[:160],inventory=json.dumps(i),status='approved',last_seen=now()); set_store_code(s,d,i.get('store_code','')); s.add(d); audit(s,'agent','auto_enrollment',v.uuid); commit_store(s,d.store_code); return {'status':'approved'}
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
_last_telemetry_cleanup=0
class Telemetry(BaseModel):
 event_id:str=Field(max_length=80); collected_at:float; kind:str; payload:dict
@app.post('/api/agent/report')
def report(v:Telemetry,d=Depends(agent),s:Session=Depends(db)):
 lock=REPORT_WRITE_LOCK if engine.dialect.name=='sqlite' else contextlib.nullcontext()
 with lock:return process_report(v,d,s)

def process_report(v,d,s):
 global _last_telemetry_cleanup
 if v.kind not in ('heartbeat','inventory','metrics','storage'): raise HTTPException(422)
 if len(json.dumps(v.payload))>200000: raise HTTPException(413)
 d=s.get(Device,d.id); d.last_seen=now()
 if v.kind=='inventory':
  validate_machine(d,v.payload)
  d.inventory=json.dumps(v.payload); d.hostname=str(v.payload.get('hostname',d.hostname)); d.ip=str(v.payload.get('primary_ip',d.ip)); d.serial=str(v.payload.get('bios_serial',d.serial))
  if 'store_code' in v.payload: set_store_code(s,d,v.payload['store_code'])
 elif v.kind!='heartbeat':
  m=json.loads(d.metrics); previous=dict(m)
  # Only CPU/RAM samples create history. Storage is an upsert of latest state.
  if v.kind=='metrics':
   last_sample=s.query(Sample).filter_by(device_id=d.id).order_by(Sample.collected.desc()).first()
   history_interval=float(os.getenv('HISTORY_INTERVAL_SECONDS','300'))
   if (last_sample is None or v.collected_at-last_sample.collected>=history_interval) and not s.query(Sample).filter_by(event_id=v.event_id).first():
    s.add(Sample(device_id=d.id,event_id=v.event_id,collected=v.collected_at,payload=json.dumps(v.payload)))
  if v.collected_at>=m.get(v.kind+'_at',0):
   m.update(v.payload); m[v.kind+'_at']=v.collected_at; d.metrics=json.dumps(m)
   evaluate(s,d,m,previous)
 cleanup_due=now()-_last_telemetry_cleanup>=3600
 if cleanup_due: s.query(Sample).filter(Sample.received<now()-int(os.getenv('RETENTION_DAYS','30'))*86400).delete()
 commit_store(s,d.store_code)
 if cleanup_due: _last_telemetry_cleanup=now()
 resp={'ok':True}
 if v.kind in ('heartbeat','inventory'):
  from backend.agent_packages import claim_device_update
  inv=json.loads(d.inventory or '{}')
  cmd=claim_device_update(DATA,current_update_sha(),d.id,inv.get('agent_build_sha',''))
  if cmd:resp['agent_update']=cmd
 return resp
def evaluate(s,d,m,previous=None):
 previous=previous or {}
 def condition(category,bad,message):
  alert=s.query(Alert).filter(Alert.device_id==d.id,Alert.category==category,Alert.status!='resolved').first()
  if bad and not alert: s.add(Alert(device_id=d.id,category=category,message=message))
  elif not bad and alert: alert.status='resolved'
 def event(category,message):
  alert=s.query(Alert).filter(Alert.device_id==d.id,Alert.category==category,Alert.status!='resolved').first()
  if not alert: s.add(Alert(device_id=d.id,category=category,message=message))
  else: alert.message=message; alert.status='active'
 condition('disk_free',any(x.get('free_percent',100)<10 for x in m.get('volumes',[])),'Ruang disk kurang dari 10%')
 if m.get('storage_source')!='sentinel':
  condition('temperature',any((x.get('temperature_c') or 0)>65 for x in m.get('disks',[])),'Suhu disk di atas 65 C')
  condition('disk_health',any(x.get('health_status') not in (None,'Healthy','Unknown') for x in m.get('disks',[])),'Kondisi physical disk perlu diperiksa')
  return
 # Do not clear existing disk alerts based on missing, partial, or stale reports.
 if m.get('sentinel_status')!='fresh': return
 condition('temperature',False,''); condition('disk_health',False,'')
 disks=m.get('disks',[])
 old={x.get('disk_identity'):x for x in previous.get('disks',[]) if x.get('source')=='sentinel'} if previous.get('storage_source')=='sentinel' else {}
 threshold=float(os.getenv('SENTINEL_HEALTH_WARNING','80'))
 for disk in disks:
  identity=disk.get('disk_identity')
  if not identity: continue
  key=digest(identity)[:16];label=f"{disk.get('model') or 'Disk'} ({disk.get('serial_number') or identity})"
  temperature=disk.get('temperature_c');health=disk.get('health_percent')
  if temperature is not None: condition('temperature:'+key,temperature>65,f'{label}: suhu di atas 65 C')
  if health is not None: condition('disk_health:'+key,health<threshold,f'{label}: Health Sentinel {health}% (batas {threshold}%)')
  before=old.get(identity,{}).get('health_percent')
  if health is not None and before is not None:
   if health<before: event('health_drop:'+key,f'{label}: Health Sentinel turun dari {before}% menjadi {health}%')
   elif health>before: condition('health_drop:'+key,False,'')
 if old and set(old)!={x.get('disk_identity') for x in disks}:
  event('component_change','Identitas physical disk berubah; periksa disk yang diganti, ditambah, atau dilepas')
@app.get('/api/alerts')
def alerts(u=Depends(user),s:Session=Depends(db)):
 ids=[x.id for x in visible(s,u)]; return [{'id':x.id,'device_id':x.device_id,'category':x.category,'message':x.message,'status':x.status,'created':x.created} for x in s.query(Alert).filter(Alert.device_id.in_(ids)).order_by(Alert.id.desc()).limit(500)]
@app.post('/api/alerts/{id}/acknowledge')
def ack(id:int,u=Depends(user),s:Session=Depends(db)):
 a=s.get(Alert,id)
 if not a: raise HTTPException(404)
 device(s,a.device_id,u); a.status='acknowledged'; audit(s,u.id,'ack_alert',id); s.commit(); return {'ok':True}
@app.get('/api/summary')
def summary(after_alert_id:int=0,u=Depends(user),s:Session=Depends(db)):
 ds=[serialize(d) for d in visible(s,u)];ids=[d['id'] for d in ds]
 active_alerts=s.query(Alert).filter(Alert.device_id.in_(ids),Alert.status!='resolved').count() if ids else 0
 new_alerts=s.query(Alert).filter(Alert.device_id.in_(ids),Alert.status!='resolved',Alert.id>after_alert_id).count() if ids else 0
 latest_alert_id=s.query(func.max(Alert.id)).filter(Alert.device_id.in_(ids)).scalar() if ids else 0
 assigned_ids={x[0] for x in s.query(UserDeviceAccess.device_id).filter(UserDeviceAccess.device_id.in_(ids)).all()} if ids else set()
 return {'devices':len(ds),'online':sum(d['online'] for d in ds),'offline':sum(d['status']=='approved' and not d['online'] for d in ds),'unassigned':sum(d['id'] not in assigned_ids for d in ds),'attention':sum(needs_attention(d) for d in ds),'agent_old':sum(d['agent']['status']!='current' for d in ds),'database_kind':engine.dialect.name,'last_report_at':max((d['last_seen'] for d in ds),default=0),'active_alerts':active_alerts,'new_alerts':new_alerts,'latest_alert_id':latest_alert_id or 0}
@app.get('/api/reports/{format}')
def export(format:str,u=Depends(user),s:Session=Depends(db)):
 if format!='xlsx':raise HTTPException(404,'Laporan hanya tersedia dalam format Excel (.xlsx)')
 from backend.reports import inventory_workbook
 models=visible(s,u);ts_map=assigned_ts(s,[d.id for d in models])
 data,filename=inventory_workbook(models,lambda d:{**serialize(d),'ts_names':ts_map.get(d.id,[])})
 return StreamingResponse(data,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="{filename}"'})
@app.get('/api/audit')
def audits(u=Depends(admin),s:Session=Depends(db)): return [{'actor':x.actor,'action':x.action,'target':x.target,'timestamp':x.timestamp} for x in s.query(Audit).order_by(Audit.id.desc()).limit(200)]
def super_admin(u=Depends(user)):
 if u.role!='super_admin': raise HTTPException(403,'Hanya Super Admin')
 return u

def database_backup():
 folder=DATA/'backups'; folder.mkdir(exist_ok=True)
 stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4)
 if engine.dialect.name=='sqlite':
  import sqlite3
  target=folder/('simon-'+stamp+'.db');connection=engine.raw_connection()
  try:
   with sqlite3.connect(target) as dest: connection.driver_connection.backup(dest)
  finally:connection.close()
  return target
 if engine.dialect.name.startswith('postgresql'):
  from tools.postgres_tools import find_program,postgres_env
  target=folder/('simon-'+stamp+'.dump');program=find_program('pg_dump')
  result=subprocess.run([program,'--format=custom','--create','--file',str(target)],env=postgres_env(engine.url),capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  if result.returncode:raise HTTPException(500,'Backup PostgreSQL gagal: '+(result.stderr or result.stdout)[-1000:])
  return target
 raise HTTPException(501,'Jenis database belum mendukung backup')

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

# The maintenance gate blocks data mutations during schema changes/rollback.
@app.middleware('http')
async def maintenance_gate(request,call_next):
 if (DATA/'updater'/'maintenance.json').exists() and request.url.path.startswith('/api/') and request.url.path not in ('/api/health','/api/me','/api/system/update/status'):
  from fastapi.responses import JSONResponse
  return JSONResponse({'detail':'SIMON sedang diperbarui. Coba lagi setelah selesai.'},status_code=503,headers={'Retry-After':'5'})
 return await call_next(request)

@app.get('/api/health')
def system_health(s:Session=Depends(db)):
 t0=time.monotonic()
 for model in (User,Device,Sample,LoginSession,Alert,UserDeviceAccess,Audit):s.query(model).limit(1).all()
 db_latency_ms=round((time.monotonic()-t0)*1000,1)
 descriptor=database_descriptor(str(engine.url))
 kind=descriptor['kind']
 db_label=f"{engine.url.host or 'localhost'}:{engine.url.port or 5432}/{engine.url.database or ''}" if kind.startswith('postgresql') else descriptor['label']
 pool=engine.pool
 pool_info={}
 try:
  pool_info={'pool_size':getattr(pool,'size',lambda:None)(),'checked_out':getattr(pool,'checkedout',lambda:None)(),'overflow':getattr(pool,'overflow',lambda:None)(),'checked_in':getattr(pool,'checkedin',lambda:None)()}
 except Exception:pass
 return {'ok':True,'version':os.getenv('SIAMS_BUILD_SHA','bootstrap'),'database_kind':kind,'database_id':descriptor['id'],'database_label':db_label,'db_latency_ms':db_latency_ms,'pool':pool_info,'server_time':time.time()}

def updater_database():
 return database_descriptor(str(engine.url))['id']

@app.get('/api/system/update/status')
def update_status(u=Depends(super_admin)):
 from backend.updates import status
 return status(DATA,ROOT)

@app.post('/api/system/update/check')
def update_check(u=Depends(super_admin)):
 from backend.updates import check,UpdateError
 try:return check(DATA,updater_database())
 except Exception as error:raise HTTPException(409,str(error))

class UpdateRequest(BaseModel):
 target:str=Field(pattern='^[0-9a-f]{40}$')

@app.post('/api/system/update/start')
def update_start(v:UpdateRequest,u=Depends(super_admin),s:Session=Depends(db)):
 from backend.updates import start,UpdateError
 # Audit before maintenance can begin; the database backup includes this request.
 audit(s,u.id,'request_application_update',v.target);s.commit()
 try:
  result=start(DATA,updater_database(),v.target,u.id)
  return {'job_id':result['id'],'message':'Update diproses oleh helper.'}
 except UpdateError as error:raise HTTPException(409,str(error))

@app.get('/api/system/update/log')
def update_log(u=Depends(super_admin)):
 path=DATA/'updater'/'update.log'
 if not path.exists():return {'log':'Belum ada log update.'}
 with path.open('rb') as source:
  source.seek(max(0,path.stat().st_size-24000));data=source.read()
 return {'log':data.decode('utf-8',errors='replace')}

def current_update_sha():
 from backend.updates import status
 return status(DATA,ROOT).get('current','')

@app.get('/api/system/agent-package/status')
def agent_package_status(u=Depends(super_admin),s:Session=Depends(db)):
 from backend.agent_packages import status
 devices=[serialize(d) for d in s.query(Device).all()]
 return status(DATA,current_update_sha(),devices=devices)

@app.post('/api/system/agent-package/prepare')
def agent_package_prepare(u=Depends(super_admin),s:Session=Depends(db)):
 from backend.agent_packages import prepare,AgentPackageError
 try:
  result=prepare(DATA,ROOT,current_update_sha());audit(s,u.id,'prepare_agent_package',result['source_sha']);s.commit();return result
 except AgentPackageError as error:raise HTTPException(409,str(error))

@app.post('/api/system/agent-package/rollout')
def agent_package_rollout(u=Depends(super_admin),s:Session=Depends(db)):
 from backend.agent_packages import start_rollout,status,AgentPackageError
 devices=[serialize(d) for d in s.query(Device).all()]
 try:
  rollout=start_rollout(DATA,current_update_sha(),devices,actor=u.id)
  audit(s,u.id,'start_agent_rollout',json.dumps({'target_sha':rollout['target_sha'],'total':rollout['total']}))
  s.commit()
  return status(DATA,current_update_sha(),devices=devices)
 except AgentPackageError as error:raise HTTPException(409,str(error))

@app.get('/api/system/agent-package/download')
def agent_package_download(u=Depends(super_admin)):
 from backend.agent_packages import status
 state=status(DATA,current_update_sha());path=DATA/'agent-package'/'SIMONAgent-store.zip'
 if not state['ready'] or not path.is_file():raise HTTPException(404,'Paket agent terbaru belum siap. Klik Ambil agent terbaru dahulu.')
 return FileResponse(path,media_type='application/zip',filename='SIMONAgent-store.zip')

@app.get('/api/agent/update/package')
def agent_update_package(d=Depends(agent)):
 from backend.agent_packages import status
 state=status(DATA,current_update_sha());path=DATA/'agent-package'/'SIMONAgent-store.zip'
 if not state['ready'] or not path.is_file():raise HTTPException(404,'Paket agent terbaru belum siap.')
 return FileResponse(path,media_type='application/zip',filename='SIMONAgent-store.zip')

class AgentUpdateStatus(BaseModel):
 state:str=Field(max_length=40); target_sha:str=''; error:str=''

@app.post('/api/agent/update/status')
def agent_update_status(v:AgentUpdateStatus,d=Depends(agent)):
 from backend.agent_packages import record_device_update_status
 return record_device_update_status(DATA,current_update_sha(),d.id,v.state,v.error)

app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')
@app.get('/')
def index(): return FileResponse(ROOT/'frontend'/'index.html')
