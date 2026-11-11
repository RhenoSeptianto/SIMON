import hashlib, os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.getenv('SIAMS_DATA',str(ROOT/'data')))

def database_url():
 path=os.getenv('DATABASE_URL_FILE','').strip()
 if path:
  value=Path(path).read_text(encoding='utf-8-sig').strip()
  if not value:raise RuntimeError('File DATABASE_URL kosong: '+path)
  return value
 return os.getenv('DATABASE_URL','sqlite:///'+str(DATA/'siams.db'))

def database_descriptor(raw=None):
 url=make_url(raw or database_url());kind=url.get_backend_name()
 if kind=='sqlite' and url.database not in (None,':memory:'):
  path=str(Path(url.database).resolve())
  identity=hashlib.sha256(os.path.normcase(path).encode()).hexdigest()
  return {'kind':kind,'id':identity,'label':path,'path':path}
 safe=url.render_as_string(hide_password=True)
 identity=hashlib.sha256(safe.encode()).hexdigest()
 label=f'{url.host or "localhost"}:{url.port or 5432}/{url.database or ""}' if kind.startswith('postgresql') else safe
 return {'kind':kind,'id':identity,'label':label,'path':None}

def make_engine(raw=None):
 url=raw or database_url();backend=make_url(url).get_backend_name()
 if backend=='sqlite':
  engine=create_engine(url,connect_args={'check_same_thread':False,'timeout':30})
  @event.listens_for(engine,'connect')
  def sqlite_settings(connection,_):
   cursor=connection.cursor()
   for statement in ('PRAGMA journal_mode=WAL','PRAGMA synchronous=NORMAL','PRAGMA busy_timeout=30000','PRAGMA foreign_keys=ON'):
    cursor.execute(statement)
   cursor.close()
  return engine
 if backend.startswith('postgresql'):
  return create_engine(url,pool_pre_ping=True,pool_size=10,max_overflow=30,pool_timeout=30)
 return create_engine(url,pool_pre_ping=True)
