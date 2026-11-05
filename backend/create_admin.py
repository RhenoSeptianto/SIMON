import argparse,getpass
from backend.main import DB,User,password
p=argparse.ArgumentParser(); p.add_argument('username'); a=p.parse_args()
value=getpass.getpass('Password admin (tidak boleh kosong): ')
if not value: raise SystemExit('Password tidak boleh kosong')
with DB() as s:
 if s.query(User).filter_by(username=a.username).first(): raise SystemExit('User sudah ada')
 s.add(User(name=a.username,username=a.username,password=password(value),role='super_admin')); s.commit()
print('Admin dibuat.')
