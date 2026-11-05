"""Generate office-local TLS files. Private keys must stay in data/tls."""
import ipaddress, os, sys, getpass
from pathlib import Path
from datetime import datetime,timedelta,timezone
from cryptography import x509
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
ROOT=Path(__file__).resolve().parents[1]

def generate_tls(folder,ip='172.18.123.92'):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
 required=[folder/x for x in ('ca.crt','ca.key','server.crt','server.key')]
 if all(x.exists() for x in required): return
 if any(x.exists() for x in required): raise RuntimeError('TLS files incomplete. Restore the original TLS folder; do not overwrite keys.')
 now=datetime.now(timezone.utc)
 ca_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'SIMON Office CA')])
 ca=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.KeyUsage(digital_signature=True,key_encipherment=False,key_cert_sign=True,crl_sign=True,content_commitment=False,data_encipherment=False,key_agreement=False,encipher_only=False,decipher_only=False),critical=True).sign(ca_key,hashes.SHA256())
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 server=x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'SIMON Office Server')])).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=825)).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip)),x509.IPAddress(ipaddress.ip_address('127.0.0.1')),x509.DNSName('localhost')]),critical=False).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(ca_key,hashes.SHA256())
 for path,obj in ((folder/'ca.key',ca_key),(folder/'server.key',key)):
  path.write_bytes(obj.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
 for path,obj in ((folder/'ca.crt',ca),(folder/'server.crt',server)):path.write_bytes(obj.public_bytes(serialization.Encoding.PEM))

def bootstrap_accounts():
 from backend.main import DB,User,password,audit
 with DB() as s:
  if s.query(User).first(): print('Database existing: akun dipertahankan.');return
  admin_password=getpass.getpass('Password Super Admin (username admin): ')
  ts_password=getpass.getpass('Password awal 9 user TS: ')
  if not admin_password or not ts_password: raise ValueError('Password tidak boleh kosong')
  s.add(User(name='Admin',username='admin',password=password(admin_password),role='super_admin',active=1))
  for name in ('Dovi','Arief','Gani','Reza','Dimas','Yazid','Ilham','Akmal','Wa haji'):
   s.add(User(name=name,username=name.lower().replace(' ',''),password=password(ts_password),role='ts',active=1))
  audit(s,'office_setup','bootstrap_accounts','admin and 9 TS');s.commit()

if __name__=='__main__':
 generate_tls(ROOT/'data'/'tls')
 bootstrap_accounts()
 print('Office setup ready. URL: https://172.18.123.92:8443')
