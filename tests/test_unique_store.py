import uuid,time,json
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from backend.main import app,DB,Device,digest

def enroll(client,identity,code,hostname='TEST-PC'):
 return client.post('/api/agent/enroll',json={'uuid':identity,'claim':'test-claim-'+'x'*40,'inventory':{'store_code':code,'hostname':hostname}})

def test_store_code_duplicate_rejected_case_insensitive_even_offline_and_reinstall_allowed():
 c=TestClient(app);first=str(uuid.uuid4())
 assert enroll(c,first,' A31 ','FIRST-PC').status_code==200
 with DB() as s:
  s.query(Device).filter_by(uuid=first).update({'last_seen':0});s.commit()
 duplicate=enroll(c,str(uuid.uuid4()),'a31','OTHER-PC')
 assert duplicate.status_code==409 and 'FIRST-PC' in duplicate.json()['detail']
 assert enroll(c,first,'A31').status_code==200
 with DB() as s:assert s.query(Device).count()==1

def test_inventory_cannot_steal_code_and_existing_owner_unchanged():
 c=TestClient(app);one,two=str(uuid.uuid4()),str(uuid.uuid4())
 assert enroll(c,one,'001','FIRST-PC').status_code==200
 assert enroll(c,two,'002','SECOND-PC').status_code==200
 token=c.post('/api/agent/claim',json={'uuid':two,'claim':'test-claim-'+'x'*40}).json()['credential']
 response=c.post('/api/agent/report',headers={'Authorization':'Bearer '+token},json={'event_id':str(uuid.uuid4()),'collected_at':time.time(),'kind':'inventory','payload':{'hostname':'CHANGED','store_code':'001'}})
 assert response.status_code==409
 assert enroll(c,two,'001').status_code==409
 with DB() as s:
  assert s.query(Device).filter_by(uuid=two).one().store_code=='002'
  assert s.query(Device).filter_by(uuid=one).one().store_code=='001'
 assert enroll(c,one,'003').status_code==200
 assert enroll(c,two,'001').status_code==200

def test_parallel_claims_create_only_one_device():
 def attempt(_):
  with TestClient(app) as c:return enroll(c,str(uuid.uuid4()),'B32').status_code
 with ThreadPoolExecutor(max_workers=2) as executor:codes=list(executor.map(attempt,range(2)))
 assert sorted(codes)==[200,409]
 with DB() as s:assert s.query(Device).count()==1

def test_legacy_unkeyed_row_still_reserves_its_code():
 with DB() as s:
  s.add(Device(uuid=str(uuid.uuid4()),claim='legacy',hostname='LEGACY-PC',store_code=' A22 ',status='approved'));s.commit()
 response=enroll(TestClient(app),str(uuid.uuid4()),'a22')
 assert response.status_code==409 and 'LEGACY-PC' in response.json()['detail']
