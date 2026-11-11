import os,shutil
from pathlib import Path
from sqlalchemy.engine import make_url

def find_program(name):
 found=shutil.which(name)
 if found:return found
 roots=[Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'PostgreSQL']
 candidates=[]
 for root in roots:
  if root.is_dir():candidates.extend(root.glob('*/bin/'+name+'.exe'))
 if candidates:return str(sorted(candidates,reverse=True)[0])
 raise RuntimeError(f'{name}.exe tidak ditemukan. Instal PostgreSQL untuk Windows terlebih dahulu.')

def postgres_env(url):
 url=make_url(str(url));env=os.environ.copy()
 env.update(PGHOST=url.host or 'localhost',PGPORT=str(url.port or 5432),PGDATABASE=url.database or '',PGUSER=url.username or '')
 if url.password is not None:env['PGPASSWORD']=url.password
 return env
