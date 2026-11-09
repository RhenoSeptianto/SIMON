import os,tempfile,uuid,time
os.environ['SIAMS_DATA']=tempfile.mkdtemp(prefix='siams-test-')
from fastapi.testclient import TestClient
from backend.main import app,DB,User,password,Sample,Device
client=TestClient(app)
H={'X-SIAMS-Request':'1'}
def report_values(client):
 from openpyxl import load_workbook
 from io import BytesIO
 w=load_workbook(BytesIO(client.get('/api/reports/xlsx').content))
 return [value for sheet in w for row in sheet.values for value in row]

def test_full_flow_and_permissions():
 with DB() as s:
  s.add(User(name='Admin',username='admin',password=password('secure-pass-123'),role='super_admin')); s.commit()
 assert client.post('/api/login',json={'username':'admin','password':'wrong'}).status_code==401
 assert client.post('/api/login',json={'username':'admin','password':'secure-pass-123'}).status_code==200
 assert client.post('/api/users',json={}).status_code==403
 uid=str(uuid.uuid4()); claim='x'*64
 assert client.post('/api/agent/enroll',json={'uuid':uid,'claim':claim,'inventory':{'hostname':'TEST-PC','primary_ip':'127.0.0.1'}}).json()['status']=='approved'
 assert client.post('/api/agent/claim',json={'uuid':uid,'claim':'bad'}).status_code==403
 d=client.get('/api/devices').json()['items'][0]['id']
 assert client.get(f'/api/devices/{d}').json()['online'] is True
 token=client.post('/api/agent/claim',json={'uuid':uid,'claim':claim}).json()['credential']
 headers={'Authorization':'Bearer '+token}
 payload={'event_id':str(uuid.uuid4()),'collected_at':time.time(),'kind':'metrics','payload':{'cpu_usage':12,'ram_total':100,'volumes':[{'free_percent':5}]}}
 assert client.post('/api/agent/report',json=payload).status_code==401
 for _ in range(2): assert client.post('/api/agent/report',json=payload,headers=headers).status_code==200
 with DB() as s: assert s.query(Sample).count()==1
 for name,access in [('support',[d]),('outsider',[])]:
  assert client.post('/api/users',json={'name':name,'username':name,'password':'secure-pass-123','role':'ts','devices':access},headers=H).status_code==200
 assert len(client.get('/api/alerts').json())==1
 assert client.get('/api/summary').json()['active_alerts']==1
 assert client.get('/api/reports/xlsx').content.startswith(b'PK')
 support=TestClient(app); support.post('/api/login',json={'username':'support','password':'secure-pass-123'})
 outsider=TestClient(app); outsider.post('/api/login',json={'username':'outsider','password':'secure-pass-123'})
 assert support.get(f'/api/devices/{d}').status_code==200
 assert outsider.get(f'/api/devices/{d}').status_code==404
 assert outsider.get(f'/api/devices/{d}/history').status_code==404
 assert outsider.get('/api/devices').json()['total']==0
 assert 'TEST-PC' not in report_values(outsider)
 assert support.post('/api/users',json={},headers=H).status_code==403
 assert client.post('/api/agent/claim',json={'uuid':uid,'claim':claim}).json()['credential']==token
 assert client.put('/api/users/2',json={'name':'support','username':'support','role':'ts','devices':[]},headers=H).status_code==200
 support.post('/api/login',json={'username':'support','password':'secure-pass-123'})
 assert support.get(f'/api/devices/{d}').status_code==404
 assert client.post(f'/api/devices/{d}/revoke',json={},headers=H).status_code==404
 assert client.delete(f'/api/devices/{d}',headers=H).status_code==200
 assert client.post('/api/agent/report',json=payload,headers=headers).status_code==401
 assert client.post('/api/agent/enroll',json={'uuid':uid,'claim':claim,'inventory':{'hostname':'TEST-PC'}}).json()['status']=='approved'

def test_disk_collector_identity_mapping():
 import agent.collectors as c
 if os.name=='nt':
  rows=c.storage()['disks']
  assert isinstance(rows,list)
  assert all('serial_number' in d and 'disk_identity' in d for d in rows)

def test_delete_device_cleans_data_and_allows_reenrollment():
 from backend.main import UserDeviceAccess,Alert,Audit,DeletedDevice
 with DB() as s:
  a=User(name='Delete Admin',username='deleteadmin',password=password('secure-pass-123'),role='super_admin')
  v=User(name='Viewer',username='deleteviewer',password=password('secure-pass-123'),role='ts')
  d=Device(uuid=str(uuid.uuid4()),hostname='DELETE-PC',ip='10.0.0.2',claim='unused',credential='unused',status='approved')
  s.add_all([a,v,d]); s.flush(); did=d.id; uid=d.uuid
  s.add_all([UserDeviceAccess(user_id=v.id,device_id=did),Sample(device_id=did,event_id=str(uuid.uuid4()),collected=time.time(),payload='{}'),Alert(device_id=did,category='test',message='test')]); s.commit()
 anon=TestClient(app)
 assert anon.delete(f'/api/devices/{did}',headers=H).status_code==401
 viewer=TestClient(app); viewer.post('/api/login',json={'username':'deleteviewer','password':'secure-pass-123'})
 assert viewer.delete(f'/api/devices/{did}',headers=H).status_code==403
 admin=TestClient(app); admin.post('/api/login',json={'username':'deleteadmin','password':'secure-pass-123'})
 assert admin.delete(f'/api/devices/{did}').status_code==403
 assert admin.delete(f'/api/devices/{did}',headers=H).status_code==200
 assert admin.get(f'/api/devices/{did}').status_code==404
 assert viewer.get(f'/api/devices/{did}/history').status_code==404
 assert did not in [d['id'] for d in admin.get('/api/devices').json()['items']]
 assert admin.delete(f'/api/devices/{did}',headers=H).status_code==404
 with DB() as s:
  assert s.get(Device,did) is None
  assert s.query(Sample).filter_by(device_id=did).count()==0
  assert s.query(Alert).filter_by(device_id=did).count()==0
  assert s.query(UserDeviceAccess).filter_by(device_id=did).count()==0
  assert s.get(DeletedDevice,uid) is None
  assert s.query(Audit).filter_by(action='delete_device').count()==1
 assert anon.post('/api/agent/enroll',json={'uuid':uid,'claim':'z'*64,'inventory':{'hostname':'DELETE-PC','store_code':'00115'}}).json()['status']=='approved'
 new_token=anon.post('/api/agent/claim',json={'uuid':uid,'claim':'z'*64}).json()['credential']
 assert anon.post('/api/agent/report',json={'event_id':str(uuid.uuid4()),'collected_at':time.time(),'kind':'heartbeat','payload':{}},headers={'Authorization':'Bearer '+new_token}).status_code==200
 assert viewer.get('/api/devices').json()['total']==0  # Deleted assignments do not return.


def test_super_admin_all_devices_and_session_lifecycle():
 from backend.main import LoginSession,UserDeviceAccess,digest
 with DB() as s:
  u=User(name='Session Admin',username='sessionadmin',password=password('secure-pass-123'),role='super_admin')
  s.add(u); s.flush(); uid=u.id
  d=Device(uuid=str(uuid.uuid4()),hostname='UNASSIGNED-PC',ip='10.0.0.3',claim='unused',status='approved');s.add(d);s.flush();did=d.id;s.commit()
 c=TestClient(app)
 assert c.post('/api/login',json={'username':'sessionadmin','password':'secure-pass-123'}).status_code==200
 assert c.get(f'/api/devices/{did}').status_code==200
 assert 'UNASSIGNED-PC' in report_values(c)
 values={'name':'Renamed Admin','username':'sessionadmin','role':'super_admin','devices':[did]}
 assert c.put(f'/api/users/{uid}',json=values,headers=H).status_code==200
 assert c.get('/api/me').json()['name']=='Renamed Admin'
 assert c.get(f'/api/devices/{did}').status_code==200
 with DB() as s: assert s.query(UserDeviceAccess).filter_by(user_id=uid).count()==0
 values['password']='updated-pass-123'
 assert c.put(f'/api/users/{uid}',json=values,headers=H).status_code==200
 assert c.get('/api/me').status_code==401
 assert c.post('/api/logout',json={},headers=H).status_code==200
 assert c.post('/api/logout',json={},headers=H).status_code==200
 assert c.post('/api/login',json={'username':'sessionadmin','password':'updated-pass-123'}).status_code==200
 assert c.get(f'/api/devices/{did}').status_code==200

def test_short_password_ts_store_and_database_tools():
 import sqlite3
 from backend.main import DATA
 with DB() as s:
  a=User(name='DB Admin',username='dbadmin',password=password('1'),role='super_admin')
  s.add(a);s.commit()
 c=TestClient(app);assert c.post('/api/login',json={'username':'dbadmin','password':'1'}).status_code==200
 assert c.post('/api/users',headers=H,json={'name':'Short','username':'short','password':'x','role':'ts','devices':[]}).status_code==200
 ts=TestClient(app);assert ts.post('/api/login',json={'username':'short','password':'x'}).status_code==200
 assert ts.post('/api/database/backup',headers=H).status_code==403
 assert ts.post('/api/database/reset',headers=H,json={'confirmation':'RESET'}).status_code==403
 assert c.post('/api/database/backup').status_code==403
 r=c.post('/api/database/backup',headers=H);assert r.status_code==200 and r.content.startswith(b'SQLite format 3')
 before=c.get('/api/devices').json()['total']
 assert c.post('/api/database/reset',headers=H,json={'confirmation':'wrong'}).status_code==422
 assert c.get('/api/devices').json()['total']==before
 r=c.post('/api/database/reset',headers=H,json={'confirmation':'RESET'});assert r.status_code==200
 with sqlite3.connect(DATA/'backups'/r.json()['backup']) as backup:
  assert backup.execute('select count(*) from devices').fetchone()[0]==before
 assert c.get('/api/devices').json()['total']==0
 assert c.get('/api/me').status_code==200
 assert ts.get('/api/me').status_code==200
 assert ts.post('/api/login',json={'username':'short','password':'x'}).status_code==200

 assert c.post('/api/users',headers=H,json={'name':'Old Role','username':'oldrole','password':'1','role':'admin_it'}).status_code==422

import pytest
@pytest.mark.parametrize('role',['ts','super_admin'])
def test_user_changes_own_password(role):
 from backend.main import Audit
 username='password-'+role
 with DB() as s:
  s.add(User(name=username,username=username,password=password('old'),role=role));s.commit()
 a=TestClient(app);b=TestClient(app);anon=TestClient(app)
 for c in (a,b): assert c.post('/api/login',json={'username':username,'password':'old'}).status_code==200
 data={'current_password':'old','new_password':'x'}
 assert anon.post('/api/me/password',headers=H,json=data).status_code==401
 assert a.post('/api/me/password',json=data).status_code==403
 assert a.post('/api/me/password',headers=H,json={'current_password':'wrong','new_password':'x'}).status_code==400
 assert a.get('/api/me').status_code==200
 assert a.post('/api/me/password',headers=H,json={'current_password':'old','new_password':''}).status_code==422
 assert a.post('/api/me/password',headers=H,json=data).status_code==200
 assert a.get('/api/me').status_code==401
 assert b.get('/api/me').status_code==401
 assert a.post('/api/login',json={'username':username,'password':'old'}).status_code==401
 assert a.post('/api/login',json={'username':username,'password':'x'}).status_code==200
 assert a.get('/api/me').json()['role']==role
 with DB() as s:
  u=s.query(User).filter_by(username=username).one()
  assert u.password!='x'
  assert s.query(Audit).filter_by(action='change_own_password',target=str(u.id)).count()==1

def test_assign_users_from_device_details():
 from backend.main import attempts
 attempts.clear()
 with DB() as s:
  a=User(name='Assign Admin',username='assignadmin',password=password('1'),role='super_admin')
  t=User(name='Assign TS',username='assignts',password=password('1'),role='ts')
  d=Device(uuid=str(uuid.uuid4()),hostname='ASSIGN-PC',claim='unused',status='approved')
  other=Device(uuid=str(uuid.uuid4()),hostname='KEEP-PC',claim='unused',status='approved')
  s.add_all([a,t,d,other]);s.flush();aid=a.id;tid=t.id;did=d.id;otherid=other.id
  from backend.main import UserDeviceAccess
  s.add(UserDeviceAccess(user_id=tid,device_id=otherid));s.commit()
 a=TestClient(app);ts=TestClient(app);anon=TestClient(app)
 a.post('/api/login',json={'username':'assignadmin','password':'1'})
 ts.post('/api/login',json={'username':'assignts','password':'1'})
 url=f'/api/devices/{did}/assignments'
 assert anon.get(url).status_code==401
 assert ts.get(url).status_code==403
 assert ts.put(url,headers=H,json={'user_ids':[tid]}).status_code==403
 assert a.put(url,json={'user_ids':[tid]}).status_code==403
 assert a.put(url,headers=H,json={'user_ids':[aid]}).status_code==422
 assert a.put(url,headers=H,json={'user_ids':[999999]}).status_code==422
 assert a.put(url,headers=H,json={'user_ids':[tid,tid]}).status_code==200
 assert next(x for x in a.get(url).json() if x['id']==tid)['assigned']
 assert ts.get(f'/api/devices/{did}').status_code==200
 assert ts.get(f'/api/devices/{otherid}').status_code==200
 assert a.put(url,headers=H,json={'user_ids':[]}).status_code==200
 assert ts.get(f'/api/devices/{did}').status_code==404
 assert ts.get(f'/api/devices/{otherid}').status_code==200
 assert a.get(f'/api/devices/{did}').status_code==200

def test_history_period_and_access():
 from backend.main import UserDeviceAccess
 import json
 with DB() as s:
  u=User(name='History TS',username='historyts',password=password('1'),role='ts')
  d=Device(uuid=str(uuid.uuid4()),hostname='HISTORY-PC',claim='unused',status='approved')
  s.add_all([u,d]);s.flush();did=d.id
  s.add(UserDeviceAccess(user_id=u.id,device_id=d.id))
  for hours in (.5,2,48,192):
   s.add(Sample(device_id=did,event_id=str(uuid.uuid4()),collected=time.time()-hours*3600,payload=json.dumps({'cpu_usage':hours,'ram_percent':50})))
  s.commit()
 from backend.main import attempts
 attempts.clear()
 c=TestClient(app);c.post('/api/login',json={'username':'historyts','password':'1'})
 assert len(c.get(f'/api/devices/{did}/history?hours=1').json())==1
 assert len(c.get(f'/api/devices/{did}/history?hours=24').json())==2
 samples=c.get(f'/api/devices/{did}/history?hours=168').json()
 assert len(samples)==3
 assert samples[0]['collected_at']<samples[-1]['collected_at']
 assert c.get(f'/api/devices/{did}/history?hours=169').status_code==422
 assert c.get(f'/api/devices/{did}/history?hours=0').status_code==422


def test_login_and_me_publish_running_version_for_both_roles():
 from backend.main import APP_VERSION
 with DB() as s:
  s.add_all([User(name='Version Admin',username='versionadmin',password=password('1'),role='super_admin',active=1),User(name='Version TS',username='versionts',password=password('1'),role='ts',active=1)]);s.commit()
 for username in ('versionadmin','versionts'):
  c=TestClient(app)
  response=c.post('/api/login',json={'username':username,'password':'1'})
  assert response.status_code==200 and response.json()['version']==APP_VERSION
  assert response.json()['disk_health_warning']==80
  identity=c.get('/api/me').json()
  assert identity['version']==APP_VERSION and identity['disk_health_warning']==80
