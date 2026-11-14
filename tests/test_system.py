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

def test_agent_compatibility_uses_build_identity(monkeypatch):
 from backend.main import agent_compatibility
 monkeypatch.setenv('SIAMS_BUILD_SHA','a'*40)
 current=agent_compatibility({'agent_version':'1.0.0','agent_build_sha':'a'*40})
 old=agent_compatibility({'agent_version':'0.2.7','agent_build_sha':'b'*40})
 unknown=agent_compatibility({'agent_version':'0.1.0'})
 assert current['status']=='current' and current['label']=='Agent terbaru'
 assert old['status']=='outdated' and old['label']=='Agent perlu diperbarui'
 assert unknown['status']=='unknown' and unknown['label']=='Versi agent tidak diketahui'

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
 summary=client.get('/api/summary').json()
 assert summary['active_alerts']==1 and summary['new_alerts']==1 and summary['latest_alert_id']>0
 assert client.get('/api/summary?after_alert_id='+str(summary['latest_alert_id'])).json()['new_alerts']==0
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


def test_system_health_endpoint_details():
 from backend.main import app
 c=TestClient(app)
 res=c.get('/api/health')
 assert res.status_code==200
 data=res.json()
 assert data['ok'] is True
 assert 'database_kind' in data
 assert 'database_label' in data
 assert 'db_latency_ms' in data
 assert isinstance(data['db_latency_ms'], (int, float))
 assert 'pool' in data
 assert isinstance(data['pool'], dict)
 assert 'server_time' in data


def test_devices_unassigned_filter():
 from openpyxl import load_workbook
 from io import BytesIO
 from backend.main import attempts,UserDeviceAccess
 attempts.clear()
 with DB() as s:
  adm=User(name='Filter Admin',username='filteradmin',password=password('1'),role='super_admin',active=1)
  ts=User(name='Filter TS',username='filterts',password=password('1'),role='ts',active=1)
  d1=Device(uuid=str(uuid.uuid4()),hostname='ASSIGNED-FILTER-PC',claim='unused',status='approved')
  d2=Device(uuid=str(uuid.uuid4()),hostname='UNASSIGNED-FILTER-PC',claim='unused',status='approved')
  s.add_all([adm,ts,d1,d2]);s.flush()
  s.add(UserDeviceAccess(user_id=ts.id,device_id=d1.id));s.commit()
 c=TestClient(app);c.post('/api/login',json={'username':'filteradmin','password':'1'})
 res=c.get('/api/devices?unassigned=1&limit_=500').json()
 names=[x['hostname'] for x in res['items']]
 assert 'UNASSIGNED-FILTER-PC' in names
 assert 'ASSIGNED-FILTER-PC' not in names
 assert res['facets']['unassigned']>=1
 w=load_workbook(BytesIO(c.get('/api/reports/xlsx?unassigned=1&q=UNASSIGNED-FILTER-PC').content))
 vals=[value for sheet in w for row in sheet.values for value in row]
 assert 'UNASSIGNED-FILTER-PC' in vals
 assert 'ASSIGNED-FILTER-PC' not in vals


def test_security_headers_and_400_store_optimizations():
 import json
 c=TestClient(app)
 res=c.get('/api/health')
 assert res.headers.get('X-Content-Type-Options')=='nosniff'
 assert res.headers.get('X-Frame-Options')=='DENY'
 assert res.headers.get('Referrer-Policy')=='same-origin'
 uid=str(uuid.uuid4());claim='m'*64
 assert c.post('/api/agent/enroll',json={'uuid':uid,'claim':claim,'inventory':{'hostname':'PERF-PC','primary_ip':'127.0.0.1'}}).status_code==200
 token=c.post('/api/agent/claim',json={'uuid':uid,'claim':claim}).json()['credential']
 headers={'Authorization':'Bearer '+token}
 t0=time.time()
 assert c.post('/api/agent/report',json={'event_id':str(uuid.uuid4()),'collected_at':t0,'kind':'metrics','payload':{'cpu_usage':10,'ram_percent':40}},headers=headers).status_code==200
 assert c.post('/api/agent/report',json={'event_id':str(uuid.uuid4()),'collected_at':t0+10,'kind':'metrics','payload':{'cpu_usage':15,'ram_percent':42}},headers=headers).status_code==200
 with DB() as s:
  d=s.query(Device).filter_by(uuid=uid).first()
  assert s.query(Sample).filter_by(device_id=d.id).count()==1
  assert json.loads(d.metrics).get('last_history_at')==t0


def test_ado_full_workflow_and_roles():
 from openpyxl import load_workbook
 from io import BytesIO
 with DB() as s:
  s.add(User(name='Super ADO',username='superado',password=password('1'),role='super_admin',active=1))
  s.commit()
 super_c=TestClient(app)
 assert super_c.post('/api/ado/login',json={'username':'superado','password':'1'}).status_code==200
 assert super_c.get('/api/ado/me').json()['role']=='super_admin'
 assert super_c.post('/api/ado/catalog',headers=H,json={'kind':'device','group_type':'PERANGKAT','parent_category':'Pos 1','name':'SCANNER ZEBRA'}).status_code==200
 cat_data=super_c.get('/api/ado/catalog').json()
 assert any(d['name']=='SCANNER ZEBRA' and d['parent_category']=='Pos 1' for d in cat_data['devices'])
 tiny_png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
 r_it=super_c.post('/api/ado/users',headers=H,json={'name':'Vani','username':'vani','password':'1','role':'admin_it','active':True,'signature_data':tiny_png})
 assert r_it.status_code==200
 r_ts=super_c.post('/api/ado/users',headers=H,json={'name':'Rheno TS','username':'rhenots','password':'1','role':'ts','active':True})
 assert r_ts.status_code==200
 ts_id=r_ts.json()['id']

 it_c=TestClient(app)
 assert it_c.post('/api/ado/login',json={'username':'vani','password':'1'}).status_code==200
 assert it_c.get('/api/ado/me').json()['signature_data']==tiny_png
 st1=it_c.post('/api/ado/stores',headers=H,json={'store_code':'00115','name':'HokBen Mall Grand Indonesia','region':'Jabodetabek','store_type':'Existing Store','ts_user_id':ts_id}).json()['id']
 st2=it_c.post('/api/ado/stores',headers=H,json={'store_code':'00201','name':'HokBen Bandung','region':'Luar Jabodetabek','store_type':'New Store','ts_user_id':ts_id}).json()['id']

 ts_c=TestClient(app)
 assert ts_c.post('/api/ado/login',json={'username':'rhenots','password':'1'}).status_code==200
 do_res=ts_c.post('/api/ado/do',headers=H,json={'store_id':st1,'store_type':'Existing Store','items':[{'category':'Pos 1','device_name':'SCANNER ZEBRA','brand':'ZEBRA','serial_number':'SN-ZEB-001','purchase_year':2023,'notes':'Unit baru'},{'category':'Back Office','device_name':'UPS','brand':'WEARNES','serial_number':'W23G00725','purchase_year':2023,'notes':''}]})
 assert do_res.status_code==200
 do_id=do_res.json()['id']
 assert '/DO/IT/001/' in do_res.json()['do_number']
 assert ts_c.post(f'/api/ado/do/{do_id}/confirm',headers=H).status_code==403

 conf_res=it_c.post(f'/api/ado/do/{do_id}/confirm',headers=H,json={'do_number':'XI/DO/IT/099/2026','delivery_date':'2026-11-12','confirmed_by':'Vani','approved_signature':tiny_png})
 assert conf_res.status_code==200 and conf_res.json()['added_assets']==2 and conf_res.json()['do_number']=='XI/DO/IT/099/2026'
 print_res=it_c.get(f'/api/ado/do/{do_id}/print')
 assert print_res.status_code==200
 assert 'DELIVERY ORDER FORM' in print_res.text
 assert 'HBG/SUP/FRM/B.04/1' in print_res.text
 assert 'XI/DO/IT/099/2026' in print_res.text
 assert '12 November 2026' in print_res.text
 assert 'PT. EKA BOGAINTI' in print_res.text
 assert 'HOKBEN MALL GRAND INDONESIA' in print_res.text
 assert 'ZEBRA / SCANNER ZEBRA' in print_res.text
 assert 'Vani' in print_res.text
 assert tiny_png in print_res.text
 assert 'Rheno TS' in print_res.text
 assets=ts_c.get('/api/ado/assets').json()
 assert len(assets)==2
 assert any(a['serial_number']=='W23G00725' and 'Tahun' in a['age_label'] and a['do_number']=='XI/DO/IT/099/2026' for a in assets)

 asset_id=assets[0]['id']
 assert ts_c.post('/api/ado/mutations',headers=H,json={'asset_id':asset_id,'to_store_id':st2,'notes':'Relokasi'}).status_code==200
 assert len(it_c.get('/api/ado/mutations').json())==1

 logs_res=ts_c.get(f'/api/ado/assets/{asset_id}/logs')
 assert logs_res.status_code==200
 logs_data=logs_res.json()
 ev_types={l['event_type'] for l in logs_data['logs']}
 assert 'do_masuk' in ev_types and 'mutasi' in ev_types
 add_log=ts_c.post(f'/api/ado/assets/{asset_id}/logs',headers=H,json={'event_type':'perbaikan','event_date':'2026-11-13','description':'Ganti kabel LAN','update_status':True})
 assert add_log.status_code==200 and add_log.json()['status']=='perbaikan'
 updated_assets=ts_c.get('/api/ado/assets').json()
 assert any(a['id']==asset_id and a['repair_count']==1 and a['status']=='perbaikan' for a in updated_assets)

 wb=load_workbook(BytesIO(it_c.get('/api/ado/reports/xlsx').content))
 assert wb.sheetnames==['Data Perangkat Store','History DO']

 import base64
 tpl_bytes=ts_c.get('/api/ado/stores/template').content
 tpl_wb=load_workbook(BytesIO(tpl_bytes))
 assert tpl_wb.sheetnames==['Data Store','Panduan & Daftar TS']
 imp_wb=load_workbook(BytesIO(tpl_bytes))
 imp_ws=imp_wb['Data Store']
 imp_ws.delete_rows(2,imp_ws.max_row)
 imp_ws.append(['00305','HokBen Bekasi','Jabodetabek','Existing Store',''])
 imp_buf=BytesIO(); imp_wb.save(imp_buf); imp_wb.close()
 imp_res=ts_c.post('/api/ado/stores/import',headers=H,json={'content_base64':base64.b64encode(imp_buf.getvalue()).decode(),'update_existing':True})
 assert imp_res.status_code==200 and imp_res.json()['created']==1
 assert any(st['store_code']=='00305' and st['ts_user_id']==ts_id for st in ts_c.get('/api/ado/stores').json())

 # v1.3.0: health app_version + accounting role + 4-stage store-to-store mutation workflow
 assert super_c.get('/mutasi').status_code==200
 health=super_c.get('/api/health').json()
 assert health['app_version']=='1.3.0'
 r_acc=super_c.post('/api/ado/users',headers=H,json={'name':'Budi Accounting','username':'budiacc','password':'1','role':'accounting','active':True})
 assert r_acc.status_code==200
 acc_c=TestClient(app)
 assert acc_c.post('/api/ado/login',json={'username':'budiacc','password':'1'}).status_code==200
 assert acc_c.get('/api/ado/me').json()['role']=='accounting'

 pub_c=TestClient(app)
 pub_stores=pub_c.get('/api/ado/public/mutasi/stores')
 assert pub_stores.status_code==200 and len(pub_stores.json())>=2
 pub_assets=pub_c.get(f'/api/ado/public/mutasi/assets?store_id={st2}')
 assert pub_assets.status_code==200
 mut_create=pub_c.post('/api/ado/public/mutasi',headers=H,json={
  'from_store_id':st2,'to_store_id':st1,'mutation_date':'2026-11-14','reason':'Relokasi store',
  'sender_name':'PIC Pengirim','sender_signature':tiny_png,
  'items':[{'asset_id':asset_id,'asset_code':'AST-001','device_name':'SCANNER ZEBRA','brand':'ZEBRA','serial_number':'SN-ZEB-001','qty':1}],
 })
 assert mut_create.status_code==200
 mut_data=mut_create.json()
 mut_id=mut_data['id']
 mut_tok=mut_data['token']
 pin=mut_data['receiver_pin']
 assert len(pin)==6 and mut_data['status']=='pending_area' and '/MA/' in mut_data['doc_number']

 assert pub_c.get(f'/api/ado/public/mutasi/{mut_tok}').json().get('receiver_pin') is None
 area_res=pub_c.post(f'/api/ado/public/mutasi/{mut_tok}/area',headers=H,json={
  'area_manager_name':'Pak Area','area_label':'Area Manager 02','area_signature':tiny_png,
 })
 assert area_res.status_code==200 and area_res.json()['status']=='pending_receiver'

 bad_pin=pub_c.post(f'/api/ado/public/mutasi/{mut_tok}/receive',headers=H,json={
  'pin':'000000','receiver_name':'PIC Penerima','receiver_signature':tiny_png,
 })
 assert bad_pin.status_code==403
 ok_recv=pub_c.post(f'/api/ado/public/mutasi/{mut_tok}/receive',headers=H,json={
  'pin':pin,'receiver_name':'PIC Penerima','receiver_signature':tiny_png,
 })
 assert ok_recv.status_code==200 and ok_recv.json()['status']=='pending_accounting'

 assert len(acc_c.get('/api/ado/mutation-orders').json())>=1
 app_res=acc_c.post(f'/api/ado/mutation-orders/{mut_id}/approve',headers=H,json={
  'sap_number':'4900098765','accounting_name':'Budi Accounting','accounting_signature':tiny_png,'save_user_signature':True,
 })
 assert app_res.status_code==200 and app_res.json()['ok'] and app_res.json()['moved_assets']==1
 approved_order=[o for o in acc_c.get('/api/ado/mutation-orders').json() if o['id']==mut_id][0]
 assert approved_order['status']=='approved' and approved_order['sap_number']=='4900098765'

 mut_print=acc_c.get(f'/api/ado/mutation-orders/{mut_id}/print')
 assert mut_print.status_code==200
 assert 'MUTASI ASSET/KIRIM BARANG' in mut_print.text
 assert '4900098765' in mut_print.text
 assert 'Area Manager 02' in mut_print.text

 moved_assets=ts_c.get('/api/ado/assets').json()
 assert any(a['id']==asset_id and a['store_id']==st1 and a['asset_code']=='AST-001' for a in moved_assets)
 logs_after=ts_c.get(f'/api/ado/assets/{asset_id}/logs').json()['logs']
 assert any(l['event_type']=='mutasi' and mut_data['doc_number'] in (l['description'] or '') for l in logs_after)





