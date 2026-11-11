import json
from pathlib import Path

def test_postgresql_identity_hides_password_and_stays_stable():
 from backend.database import database_descriptor
 first=database_descriptor('postgresql+psycopg://simon:secret-one@127.0.0.1:5432/simon')
 second=database_descriptor('postgresql+psycopg://simon:secret-two@127.0.0.1:5432/simon')
 assert first['kind']=='postgresql' and first['id']==second['id']
 assert 'secret' not in first['label'] and first['label']=='127.0.0.1:5432/simon'

def test_role_password_ddl_is_safely_quoted_without_bind_placeholder():
 from tools.migrate_postgresql import role_password_query
 statement=role_password_query('CREATE ROLE','simon_app',"p'ass").as_string()
 assert statement=='CREATE ROLE "simon_app" WITH LOGIN CREATEDB PASSWORD \'p\'\'ass\''
 assert '$1' not in statement and '%s' not in statement

def test_postgresql_worker_uses_dump_and_restore_without_password_in_arguments(tmp_path,monkeypatch):
 import tools.update_worker as updater
 url=tmp_path/'database-url.txt';url.write_text('postgresql+psycopg://simon:p%40ss@127.0.0.1:5432/simon')
 config={'database_kind':'postgresql','database_url_file':str(url),'pg_dump':'pg_dump.exe','pg_restore':'pg_restore.exe'}
 calls=[]
 def command(args,**kwargs):calls.append((args,kwargs));Path(args[args.index('--file')+1]).write_bytes(b'dump') if '--file' in args else None;return ''
 monkeypatch.setattr(updater,'command',command)
 backup=updater.backup_database(config,tmp_path/'backup')
 updater.restore_database(config,backup)
 assert backup.name=='database.dump'
 assert calls[0][0][0]=='pg_dump.exe' and calls[1][0][0]=='pg_restore.exe'
 assert calls[0][1]['env']['PGPASSWORD']=='p@ss'
 assert all('p@ss' not in str(arguments) for arguments,_ in calls)

def test_healthcheck_accepts_postgresql_identity(monkeypatch,tmp_path):
 import io
 from tools import server_healthcheck
 payload={'ok':True,'database_kind':'postgresql','database_id':'db-id','version':'sha'}
 response=io.BytesIO(json.dumps(payload).encode());response.status=200
 monkeypatch.setattr(server_healthcheck.ssl,'create_default_context',lambda **kwargs:object())
 monkeypatch.setattr(server_healthcheck.urllib.request,'urlopen',lambda *args,**kwargs:response)
 assert server_healthcheck.check_https('ca','https://localhost',attempts=1,expected_kind='postgresql',expected_id='db-id')==0
