import uuid,json,time,shutil
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app,DB,Device
from agent.identity import ensure_identity

def test_copy_to_other_machine_rotates_identity_and_queue_but_reinstall_retains(tmp_path,monkeypatch):
 monkeypatch.setattr('agent.identity.machine_id',lambda:'machine-A')
 original=tmp_path/'first'/'data';one=ensure_identity(original)
 (original/'queue.db').write_bytes(b'old-machine-queue')
 copied=tmp_path/'second'/'data';shutil.copytree(original,copied)
 monkeypatch.setattr('agent.identity.machine_id',lambda:'machine-B')
 two=ensure_identity(copied)
 assert two['uuid']!=one['uuid'] and two['claim']!=one['claim']
 assert two['machine_id']=='machine-B' and not (copied/'queue.db').exists()
 backups=list(copied.parent.glob('data-other-machine-*'))
 assert len(backups)==1 and (backups[0]/'queue.db').read_bytes()==b'old-machine-queue'
 assert ensure_identity(copied)==two
 assert json.loads((original/'identity.json').read_text())==one

def test_copied_uuid_cannot_overwrite_hostname_serial_or_store_and_two_ids_coexist():
 c=TestClient(app);uid=str(uuid.uuid4());claim='x'*64
 pc_a={'hostname':'NBICT-14','bios_serial':'SERIAL-A','machine_id':'a'*64,'store_code':'001'}
 payload={'uuid':uid,'claim':claim,'inventory':pc_a}
 assert c.post('/api/agent/enroll',json=payload).status_code==200
 pc_b={'hostname':'PANJOEL-REBORN','bios_serial':'SERIAL-B','machine_id':'b'*64,'store_code':'000'}
 response=c.post('/api/agent/enroll',json={**payload,'inventory':pc_b})
 assert response.status_code==409 and response.json()['detail']['code']=='identity_mismatch'
 token=c.post('/api/agent/claim',json={'uuid':uid,'claim':claim}).json()['credential']
 response=c.post('/api/agent/report',headers={'Authorization':'Bearer '+token},json={'event_id':str(uuid.uuid4()),'collected_at':time.time(),'kind':'inventory','payload':pc_b})
 assert response.status_code==409
 with DB() as s:
  owner=s.query(Device).filter_by(uuid=uid).one()
  assert (owner.hostname,owner.serial,owner.store_code)==('NBICT-14','SERIAL-A','001')
 assert c.post('/api/agent/enroll',json={'uuid':str(uuid.uuid4()),'claim':'y'*64,'inventory':pc_b}).status_code==200
 with DB() as s:assert s.query(Device).count()==2
 # Same physical PC renamed is still allowed; missing legacy binding cannot erase stored hash.
 renamed={**pc_a,'hostname':'RENAMED-PC'}
 assert c.post('/api/agent/report',headers={'Authorization':'Bearer '+token},json={'event_id':str(uuid.uuid4()),'collected_at':time.time(),'kind':'inventory','payload':renamed}).status_code==200
 with DB() as s:assert s.query(Device).filter_by(uuid=uid).one().hostname=='RENAMED-PC'

def test_legacy_uuid_with_different_real_bios_serial_is_rejected():
 c=TestClient(app);payload={'uuid':str(uuid.uuid4()),'claim':'x'*64,'inventory':{'hostname':'OLD-PC','bios_serial':'ORIGINAL','store_code':'001'}}
 assert c.post('/api/agent/enroll',json=payload).status_code==200
 response=c.post('/api/agent/enroll',json={**payload,'inventory':{'hostname':'COPIED-PC','bios_serial':'DIFFERENT','store_code':'002','machine_id':'b'*64}})
 assert response.status_code==409 and response.json()['detail']['code']=='identity_mismatch'
