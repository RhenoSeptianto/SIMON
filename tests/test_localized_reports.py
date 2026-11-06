import json,time,uuid
from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from backend.main import DB,Device,User,UserDeviceAccess,password,app
from backend.localization import message_id,power_state_id,lifetime_id,localize_disk


def test_indonesian_messages_preserve_health_problems_and_numbers():
 healthy,ok=message_id('The status of the solid state disk is PERFECT. Problematic or weak sectors were not found. The TRIM feature of the SSD is supported and enabled for optimal performance. The health is determined by SSD specific S.M.A.R.T. attribute(s): #231 SSD Life Remaining.')
 assert ok and 'Kondisi SSD sangat baik.' in healthy and 'TRIM didukung' in healthy and '#231 Sisa umur SSD' in healthy
 bad,ok=message_id('The hard disk status is BAD. There are 12 bad sectors on the disk surface. The contents of these sectors were moved to the spare area. Backup immediately to prevent data loss.')
 assert ok and 'Kondisi HDD buruk' in bad and '12 sektor rusak' in bad and 'Segera cadangkan data' in bad
 assert 'sangat baik' not in bad
 unknown,ok=message_id('Unknown vendor warning 123')
 assert not ok and 'belum dikenali' in unknown and 'sangat baik' not in unknown
 assert message_id('No actions needed.')[0]=='Tidak perlu tindakan.'
 assert power_state_id('Inactive (without monitoring) (since 11/6/2026 3:58:38 PM)')=='Tidak aktif (tanpa pemantauan) sejak 6 November 2026, 15.58.38'
 assert lifetime_id('more than 414 days')=='Lebih dari 414 hari'


def test_excel_has_three_localized_sheets_permissions_types_and_safe_text():
 disk={'source':'sentinel','model':'SSD TEST','serial_number':'DISK-SERIAL','health_percent':95,'performance_percent':100,'temperature_c':37,'power_on_hours':51,'capacity_bytes':128*1073741824,'sentinel_description':'The status of the solid state disk is PERFECT.','sentinel_tip':'No actions needed.','power_state':'Inactive (without monitoring) (since 11/6/2026 3:58:38 PM)','estimated_remaining_lifetime':'more than 414 days'}
 volumes=[{'drive_letter':'C:','filesystem':'NTFS','total_bytes':100*1073741824,'used_bytes':25*1073741824,'free_bytes':75*1073741824},{'drive_letter':'D:','total_bytes':200*1073741824,'free_bytes':100*1073741824}]
 with DB() as s:
  user=User(name='TS',username='report-ts',password=password('1'),role='ts')
  visible=Device(uuid=str(uuid.uuid4()),claim='test',hostname='=1+1',store_code='00115',ip='10.0.0.1',serial='PC-SERIAL',status='approved',last_seen=time.time(),inventory=json.dumps({'os_name':'Windows 11','cpu':'Intel CPU'}),metrics=json.dumps({'cpu_usage':20,'ram_total':16*1073741824,'ram_percent':40,'storage_source':'sentinel','sentinel_status':'fresh','sentinel_report_time':'11/6/2026 2:23:03 PM','disks':[disk,{**disk,'model':'HDD TEST','serial_number':'DISK-2','temperature_c':None,'health_percent':None}],'volumes':volumes}))
  hidden=Device(uuid=str(uuid.uuid4()),claim='test',hostname='DO-NOT-EXPORT',store_code='00222',status='approved')
  s.add_all([user,visible,hidden]);s.flush();id=visible.id;s.add(UserDeviceAccess(user_id=user.id,device_id=visible.id));s.commit()
 c=TestClient(app);c.post('/api/login',json={'username':'report-ts','password':'1'})
 response=c.get('/api/reports/xlsx');assert response.status_code==200
 assert 'SIMON-Inventaris-' in response.headers['content-disposition']
 workbook=load_workbook(BytesIO(response.content),data_only=False)
 assert workbook.sheetnames==['Perangkat','SSD-HDD','Kapasitas Drive']
 pc,disks,drive=[workbook[name] for name in workbook.sheetnames]
 assert pc.max_row==2 and disks.max_row==3 and drive.max_row==3
 assert pc['A2'].value=='00115' and pc['A2'].data_type=='s'
 assert pc['B2'].value=='=1+1' and pc['B2'].data_type=='s'
 assert pc['H2'].value==16 and isinstance(pc['K2'].value,__import__('datetime').datetime)
 assert disks['I2'].value==95 and disks['K2'].value==37
 assert disks['K3'].value=='Tidak tersedia'
 assert disks['N2'].value.startswith('Tidak aktif') and disks['P2'].value=='Tidak perlu tindakan.'
 assert drive['F2'].value==100 and drive['G2'].value==25 and drive['H2'].value==75
 assert drive['I2'].value==25 and drive['J2'].value==75
 for sheet in workbook:
  assert sheet.freeze_panes=='A2' and sheet.auto_filter.ref
  assert not any(cell.data_type=='f' for row in sheet for cell in row)
  assert 'DO-NOT-EXPORT' not in [v for row in sheet.values for v in row]
 assert c.get('/api/reports/csv').status_code==404
 details=c.get(f'/api/devices/{id}').json()
 localized=details['metrics']['disks'][0]
 assert localized['sentinel_tip_id']=='Tidak perlu tindakan.'
 with DB() as s:assert json.loads(s.get(Device,id).metrics)['disks'][0]['sentinel_tip']=='No actions needed.'


def test_empty_excel_still_has_all_sheets_and_headers():
 with DB() as s:s.add(User(name='Empty TS',username='empty-report',password=password('1'),role='ts'));s.commit()
 c=TestClient(app);c.post('/api/login',json={'username':'empty-report','password':'1'})
 workbook=load_workbook(BytesIO(c.get('/api/reports/xlsx').content))
 assert len(workbook.sheetnames)==3
 assert all(sheet.max_row==1 for sheet in workbook)
