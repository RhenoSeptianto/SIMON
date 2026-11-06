import json,ssl,zipfile,uuid,hashlib
from pathlib import Path
import pytest
from agent.config import load_config,validate_server,tls_context
from tools.server_setup import generate_tls
from tools.make_agent_package import make_package

def test_config_relative_paths_and_utf8_bom(tmp_path):
 file=tmp_path/'config.json';file.write_text(json.dumps({'server':'https://172.18.123.92:8443','ca_file':'ca.crt','state':'state'}),encoding='utf-8-sig')
 data=load_config(file)
 assert data['ca_file']==str(tmp_path/'ca.crt')
 assert data['state']==str(tmp_path/'state')
 assert validate_server(data['server'])=='https://172.18.123.92:8443'
 with pytest.raises(ValueError):load_config(tmp_path/'missing.json')

@pytest.mark.parametrize('url',['http://172.18.123.92:8000','http://127.0.0.1.evil.test:8000','https://user:secret@example.org','file:///server'])
def test_agent_rejects_unsafe_server_url(url):
 with pytest.raises(ValueError):validate_server(url)

def test_tls_is_idempotent_has_ip_san_and_validates(tmp_path):
 from cryptography import x509
 from cryptography.hazmat.primitives import hashes
 folder=tmp_path/'tls';generate_tls(folder)
 first=(folder/'ca.crt').read_bytes();generate_tls(folder)
 assert (folder/'ca.crt').read_bytes()==first
 server=x509.load_pem_x509_certificate((folder/'server.crt').read_bytes())
 root=x509.load_pem_x509_certificate(first)
 root.public_key().verify(server.signature,server.tbs_certificate_bytes,__import__('cryptography.hazmat.primitives.asymmetric.padding',fromlist=['PKCS1v15']).PKCS1v15(),server.signature_hash_algorithm)
 assert '172.18.123.92' in [str(x) for x in server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)]
 assert tls_context(str(folder/'ca.crt')).verify_mode==ssl.CERT_REQUIRED

def test_agent_package_contains_public_ca_only(tmp_path):
 generate_tls(tmp_path/'data'/'tls')
 release=tmp_path/'release';release.mkdir()
 with zipfile.ZipFile(release/'SIMONAgent-template.zip','w') as z:
  z.writestr('SIMONAgent/SIMONAgent.exe',b'test executable fixture')
  z.writestr('agent-build.json',json.dumps({'capabilities':['sentinel_xml','store_code','reenrollment_after_delete','ten_second_metrics'],'exe_sha256':hashlib.sha256(b'test executable fixture').hexdigest()}))
  z.writestr('install.bat','test fixture')
 result=make_package(tmp_path)
 with zipfile.ZipFile(result) as z:
  assert 'ca.crt' in z.namelist()
  assert not any(n.endswith(('.key','.db')) for n in z.namelist())
  assert not any('identity.json' in n for n in z.namelist())

def test_agent_package_rejects_zip_traversal(tmp_path):
 generate_tls(tmp_path/'data'/'tls');release=tmp_path/'release';release.mkdir()
 with zipfile.ZipFile(release/'SIMONAgent-template.zip','w') as z:z.writestr('../leak.txt','bad')
 with pytest.raises(RuntimeError,match='Unsafe archive'):make_package(tmp_path)
 assert not (release/'leak.txt').exists()

def test_source_package_excludes_runtime_and_private_files(tmp_path):
 from tools.package_source import package_source
 (tmp_path/'agent').mkdir();(tmp_path/'data').mkdir();(tmp_path/'.venv').mkdir()
 (tmp_path/'agent'/'main.py').write_text('pass')
 (tmp_path/'agent'/'identity.json').write_text('credential')
 (tmp_path/'agent'/'private.key').write_text('private')
 (tmp_path/'data'/'siams.db').write_text('db')
 (tmp_path/'.env').write_text('secret')
 (tmp_path/'README.md').write_text('docs')
 with zipfile.ZipFile(package_source(tmp_path)) as archive:
  assert set(archive.namelist())=={'README.md','agent/main.py'}


def test_store_package_refreshes_installer_without_rebuilding_exe(tmp_path):
 generate_tls(tmp_path/'data'/'tls')
 release=tmp_path/'release';release.mkdir()
 with zipfile.ZipFile(release/'SIMONAgent-template.zip','w') as z:
  z.writestr('SIMONAgent/SIMONAgent.exe',b'unchanged-binary')
  z.writestr('agent-build.json',json.dumps({'capabilities':['sentinel_xml','store_code','reenrollment_after_delete','ten_second_metrics'],'exe_sha256':hashlib.sha256(b'unchanged-binary').hexdigest()}))
  z.writestr('install.ps1','old installer')
 installers=tmp_path/'deployment'/'agent';installers.mkdir(parents=True)
 (installers/'install.ps1').write_text('fixed installer')
 with zipfile.ZipFile(make_package(tmp_path)) as z:
  assert z.read('install.ps1')==b'fixed installer'
  assert z.read('SIMONAgent/SIMONAgent.exe')==b'unchanged-binary'
