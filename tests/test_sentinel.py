import os,sqlite3,time,uuid,json
from pathlib import Path
import pytest
from agent.sentinel import parse_report,SentinelWatcher

def report(health='95 %',temperature='37 C',serial='SSD-1',extra=''):
 return f'''<?xml version="1.0" encoding="ISO-8859-2"?><Hard_Disk_Sentinel><General_Information><Application_Information><Current_Date_And_Time>11/6/2026 2:23:03 PM</Current_Date_And_Time></Application_Information></General_Information><Physical_Disk_Information_Disk_9><Hard_Disk_Summary><Hard_Disk_Model_ID>Test SSD</Hard_Disk_Model_ID><Hard_Disk_Serial_Number>{serial}</Hard_Disk_Serial_Number><SSD_Controller>Controller</SSD_Controller><Health>{health}</Health><Performance>100 %</Performance><Current_Temperature>{temperature}</Current_Temperature><Power_on_time>2 days, 3 hours</Power_on_time><Description>solid state disk</Description></Hard_Disk_Summary><Drive><Total_Sectors>100000</Total_Sectors><Bytes_Per_Sector>512</Bytes_Per_Sector></Drive></Physical_Disk_Information_Disk_9>{extra}</Hard_Disk_Sentinel>'''.encode('iso-8859-2')

def test_parser_summary_and_identity_without_array_order():
 disk=parse_report(report())['disks'][0]
 assert disk['serial_number']=='SSD-1' and disk['disk_identity']=='sentinel:SSD-1'
 assert disk['health_percent']==95 and disk['performance_percent']==100
 assert disk['temperature_c']==37 and disk['power_on_hours']==51
 assert disk['capacity_bytes']==51200000 and disk['wear_percent'] is None
 assert parse_report(report('N/A','N/A'))['disks'][0]['health_percent'] is None
 assert parse_report(report('N/A','N/A'))['disks'][0]['temperature_c'] is None


def test_watcher_follows_changes_handles_partial_and_stale(tmp_path):
 file=tmp_path/'HDSentinel.xml';watch=SentinelWatcher(file)
 assert watch.read_update()['sentinel_status']=='missing'
 assert watch.read_update() is None
 file.write_bytes(report());first=watch.read_update()
 assert first['sentinel_status']=='fresh'
 assert watch.read_update() is None
 file.write_bytes(b'<Hard_Disk_Sentinel>')
 assert watch.read_update()['sentinel_status']=='error'
 file.write_bytes(report('94 %'));fresh=watch.read_update()
 assert fresh['disks'][0]['health_percent']==94
 assert watch.read_update(now=file.stat().st_mtime+121)['sentinel_status']=='stale'
 assert watch.read_update(now=file.stat().st_mtime+122) is None


def test_parser_rejects_entities_and_duplicate_serials():
 with pytest.raises(ValueError):parse_report(b'<!DOCTYPE a [<!ENTITY x "value">]><Hard_Disk_Sentinel/>')
 duplicate=report().decode('iso-8859-2').split('<Physical_Disk_Information_Disk_9>')[1].split('</Physical_Disk_Information_Disk_9>')[0]
 with pytest.raises(ValueError,match='duplikat'):parse_report(report(extra='<Physical_Disk_Information_Disk_8>'+duplicate+'</Physical_Disk_Information_Disk_8>'))


def test_storage_latest_only_alerts_and_store_code():
 from backend.main import app,DB,Device,Sample,Alert,digest
 from fastapi.testclient import TestClient
 token=uuid.uuid4().hex
 with DB() as s:
  device=Device(uuid=str(uuid.uuid4()),hostname='STORE-PC',store_code='00115',claim='test',credential=digest(token),status='approved');s.add(device);s.flush();id=device.id;s.commit()
 c=TestClient(app);headers={'Authorization':'Bearer '+token};timestamp=time.time()
 def send(payload,kind='storage'):
  nonlocal timestamp
  timestamp+=1
  r=c.post('/api/agent/report',json={'event_id':str(uuid.uuid4()),'collected_at':timestamp,'kind':kind,'payload':payload},headers=headers)
  assert r.status_code==200,r.text
 base={**parse_report(report()),'sentinel_status':'fresh'}
 for _ in range(3):send(base)
 with DB() as s:
  assert s.query(Sample).filter_by(device_id=id).count()==0
  assert s.query(Alert).filter_by(device_id=id).count()==0
 dropped={**parse_report(report('94 %','70 C')),'sentinel_status':'fresh'}
 for _ in range(3):send(dropped)
 with DB() as s:
  alerts=s.query(Alert).filter_by(device_id=id).all()
  assert len(alerts)==2  # Health fell once and high temperature is deduplicated.
  assert s.query(Sample).filter_by(device_id=id).count()==0
 send({'sentinel_status':'error','sentinel_message':'partial XML'})
 with DB() as s:assert s.query(Alert).filter_by(device_id=id,status='active').count()==2
 send(base)
 replacement={**parse_report(report(serial='SSD-NEW')),'sentinel_status':'fresh'}
 for _ in range(2):send(replacement)
 with DB() as s:
  assert s.query(Alert).filter_by(device_id=id,category='component_change').count()==1
  assert s.query(Alert).filter(Alert.device_id==id,Alert.category.like('temperature:%'),Alert.status=='resolved').count()==1
 send({'hostname':'NEW-NAME','store_code':'00999'},'inventory')
 send({'cpu_usage':10,'ram_percent':30},'metrics')
 with DB() as s:
  assert s.get(Device,id).store_code=='00999'
  assert s.get(Device,id).hostname=='NEW-NAME'
  assert s.query(Sample).filter_by(device_id=id).count()==1
  assert json.loads(s.get(Device,id).metrics)['disks'][0]['temperature_c']==37
  assert json.loads(s.get(Device,id).metrics)['disks'][0]['serial_number']=='SSD-NEW'


def test_existing_database_gets_store_code_column_without_losing_device(tmp_path):
 import os,sys,subprocess
 from sqlalchemy import create_engine,text,inspect
 from backend.main import Base,Device
 engine=create_engine('sqlite:///'+str(tmp_path/'siams.db'))
 Base.metadata.create_all(engine)
 with engine.begin() as c:
  c.execute(Device.__table__.insert().values(uuid=str(uuid.uuid4()),hostname='KEEP-LEGACY-PC',status='approved'))
  c.execute(text('ALTER TABLE devices DROP COLUMN store_code'))
 env=os.environ.copy();env['SIAMS_DATA']=str(tmp_path);env.pop('DATABASE_URL',None)
 for _ in range(2):
  result=subprocess.run([sys.executable,'-c','import backend.main'],env=env,capture_output=True,text=True,timeout=30)
  assert result.returncode==0,result.stdout+result.stderr
 with engine.connect() as c:
  assert c.execute(text('select hostname,store_code from devices')).fetchone()==('KEEP-LEGACY-PC','')
 engine.dispose()



def test_report_identity_does_not_depend_on_disk_array_order():
 one=report(serial='A').decode('iso-8859-2')
 two=report(serial='B').decode('iso-8859-2')
 disk=lambda xml:xml[xml.index('<Physical_Disk_Information_Disk_9>'):xml.index('</Physical_Disk_Information_Disk_9>')+len('</Physical_Disk_Information_Disk_9>')]
 left=parse_report(('<Hard_Disk_Sentinel>'+disk(one)+disk(two)+'</Hard_Disk_Sentinel>').encode())
 right=parse_report(('<Hard_Disk_Sentinel>'+disk(two)+disk(one)+'</Hard_Disk_Sentinel>').encode())
 assert {d['serial_number']:d['disk_identity'] for d in left['disks']}=={d['serial_number']:d['disk_identity'] for d in right['disks']}



def test_store_code_is_searchable_exported_and_does_not_grant_access():
 from backend.main import DB,Device,User,UserDeviceAccess,password,app
 from fastapi.testclient import TestClient
 from openpyxl import load_workbook
 from io import BytesIO
 with DB() as s:
  visible=Device(uuid=str(uuid.uuid4()),hostname='VISIBLE',store_code='00115',claim='test',status='approved')
  hidden=Device(uuid=str(uuid.uuid4()),hostname='HIDDEN',store_code='00115',claim='test',status='approved')
  user=User(name='TS',username='store-search',password=password('1'),role='ts')
  s.add_all([visible,hidden,user]);s.flush();id=visible.id
  s.add(UserDeviceAccess(user_id=user.id,device_id=visible.id));s.commit()
 c=TestClient(app);assert c.post('/api/login',json={'username':'store-search','password':'1'}).status_code==200
 result=c.get('/api/devices?q=00115').json()
 assert result['total']==1 and result['items'][0]['id']==id
 assert result['items'][0]['store_code']=='00115'
 csv=c.get('/api/reports/csv').text
 assert '00115' in csv and 'VISIBLE' in csv and 'HIDDEN' not in csv
 wb=load_workbook(BytesIO(c.get('/api/reports/xlsx').content))
 assert wb.active.cell(2,1).value=='00115'



def test_unknown_xml_encoding_does_not_stop_watcher(tmp_path):
 file=tmp_path/'HDSentinel.xml';file.write_bytes(b'<?xml version="1.0" encoding="unknown-encoding"?><Hard_Disk_Sentinel/>')
 watcher=SentinelWatcher(file)
 assert watcher.read_update()['sentinel_status']=='error'
 file.write_bytes(report())
 assert watcher.read_update()['sentinel_status']=='fresh'
