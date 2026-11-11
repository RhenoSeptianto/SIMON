"""One-time, lossless SIMON migration from SQLite to a local PostgreSQL database."""
import argparse,os,secrets,sqlite3,time
from pathlib import Path
import psycopg
from psycopg import sql
from sqlalchemy import create_engine,select,func
from sqlalchemy.engine import URL

def sqlite_backup(source,target):
 target.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(source) as src,sqlite3.connect(target) as dst:
  src.backup(dst)
  if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Backup SQLite tidak lolos quick_check')

def role_password_query(verb,role,password):
 if verb not in ('CREATE ROLE','ALTER ROLE'):raise ValueError('Operasi role tidak valid')
 return sql.SQL('{} {} WITH LOGIN CREATEDB PASSWORD {}').format(sql.SQL(verb),sql.Identifier(role),sql.Literal(password))

def prepare_database(host,port,admin_user,admin_password,role,database,app_password,allow_replace=False):
 with psycopg.connect(host=host,port=port,user=admin_user,password=admin_password,dbname='postgres',autocommit=True) as connection:
  with connection.cursor() as cursor:
   cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,))
   verb='ALTER ROLE' if cursor.fetchone() else 'CREATE ROLE'
   cursor.execute(role_password_query(verb,role,app_password))
   cursor.execute('SELECT 1 FROM pg_database WHERE datname=%s',(database,));exists=bool(cursor.fetchone())
   if exists and not allow_replace:
    with psycopg.connect(host=host,port=port,user=admin_user,password=admin_password,dbname=database) as target_check:
     with target_check.cursor() as target_cursor:
      target_cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' LIMIT 1")
      if target_cursor.fetchone():raise RuntimeError(f"Database PostgreSQL '{database}' sudah berisi tabel. Migrasi dibatalkan tanpa menghapusnya.")
   if exists and allow_replace:
    cursor.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()',(database,))
    cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)));exists=False
   if not exists:cursor.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(database),sql.Identifier(role)))
   else:cursor.execute(sql.SQL('ALTER DATABASE {} OWNER TO {}').format(sql.Identifier(database),sql.Identifier(role)))

def copy_data(source_path,target_url):
 os.environ['DATABASE_URL']=target_url;os.environ.pop('DATABASE_URL_FILE',None)
 from backend.main import Base
 source=create_engine('sqlite:///'+str(source_path));target=create_engine(target_url,pool_pre_ping=True)
 Base.metadata.create_all(target)
 with target.connect() as check:
  occupied=[table.name for table in Base.metadata.sorted_tables if check.execute(select(func.count()).select_from(table)).scalar_one()]
 if occupied:raise RuntimeError('Database PostgreSQL tujuan sudah berisi data SIMON: '+', '.join(occupied))
 with source.connect() as src,target.begin() as dst:
  for table in Base.metadata.sorted_tables:
   rows=[dict(row._mapping) for row in src.execute(select(table))]
   if rows:dst.execute(table.insert(),rows)
  for table in Base.metadata.sorted_tables:
   for column in table.primary_key.columns:
    if getattr(column.type,'python_type',None) is not int:continue
    sequence=dst.exec_driver_sql('SELECT pg_get_serial_sequence(%s,%s)',(table.name,column.name)).scalar()
    if sequence:
     maximum=dst.execute(select(func.max(column))).scalar()
     dst.exec_driver_sql("SELECT setval(%s,%s,%s)",(sequence,maximum or 1,maximum is not None))

def migrate(source,data,host,port,admin_user,role,database):
 source=Path(source).resolve();data=Path(data).resolve()
 if not source.is_file():raise RuntimeError('Database SQLite tidak ditemukan: '+str(source))
 admin_password=os.environ.pop('SIMON_PG_ADMIN_PASSWORD','')
 if not admin_password:raise RuntimeError('Password administrator PostgreSQL tidak diterima')
 app_password=secrets.token_urlsafe(32)
 backup=data/'backups'/('pre-postgresql-'+time.strftime('%Y%m%d-%H%M%S')+'.db')
 sqlite_backup(source,backup)
 prepare_database(host,port,admin_user,admin_password,role,database,app_password,allow_replace=(data/'database-url.txt').exists())
 url=URL.create('postgresql+psycopg',username=role,password=app_password,host=host,port=port,database=database).render_as_string(hide_password=False)
 copy_data(source,url)
 url_file=data/'database-url.txt';url_file.write_text(url+'\n',encoding='utf-8')
 print('MIGRATION_OK')
 print('Backup SQLite:',backup)
 print('Database URL file:',url_file)
 return url_file

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--data',required=True);parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=5432);parser.add_argument('--admin-user',default='postgres');parser.add_argument('--role',default='simon_app');parser.add_argument('--database',default='simon');args=parser.parse_args()
 migrate(args.source,args.data,args.host,args.port,args.admin_user,args.role,args.database)
