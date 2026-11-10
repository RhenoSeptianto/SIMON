import hashlib,json,shutil,zipfile
from pathlib import Path
import pytest
from backend.agent_packages import AgentPackageError,prepare,status
from tools.make_agent_package import REQUIRED_CAPABILITIES


def template(path,source_sha):
 executable=b'fake-windows-agent-for-packaging-test'
 metadata={'format':9,'source_sha':source_sha,'capabilities':sorted(REQUIRED_CAPABILITIES),'exe_sha256':hashlib.sha256(executable).hexdigest()}
 with zipfile.ZipFile(path,'w') as archive:
  archive.writestr('SIMONAgent/SIMONAgent.exe',executable)
  archive.writestr('agent-build.json',json.dumps(metadata))
 return executable


def fixture(tmp_path,source_sha):
 root=tmp_path/'root';data=tmp_path/'data';(root/'deployment'/'agent').mkdir(parents=True);(data/'tls').mkdir(parents=True)
 (root/'deployment'/'agent'/'install.bat').write_text('@echo off\necho current installer',encoding='utf-8')
 (root/'deployment'/'agent'/'install-user.ps1').write_text('# current installer',encoding='utf-8')
 (data/'tls'/'ca.crt').write_text('PUBLIC OFFICE CA',encoding='utf-8')
 artifact=tmp_path/'template.zip';template(artifact,source_sha)
 return root,data,artifact


def test_prepare_agent_package_validates_build_and_adds_only_public_ca(tmp_path):
 source_sha='a'*40;root,data,artifact=fixture(tmp_path,source_sha)
 result=prepare(data,root,source_sha,fetch=lambda target:shutil.copy2(artifact,target))
 output=data/'agent-package'/'SIMONAgent-store.zip'
 assert result['ready'] and status(data,source_sha)['ready']
 with zipfile.ZipFile(output) as package:
  names=set(package.namelist())
  assert package.read('ca.crt')==b'PUBLIC OFFICE CA'
  assert b'current installer' in package.read('install.bat')
  assert 'SIMONAgent/SIMONAgent.exe' in names
  assert not any(name.endswith(('.key','.db','identity.json')) for name in names)
 assert not status(data,'b'*40)['ready']


def test_prepare_rejects_agent_built_for_another_server_commit(tmp_path):
 root,data,artifact=fixture(tmp_path,'a'*40)
 with pytest.raises(AgentPackageError,match='belum tersedia'):
  prepare(data,root,'b'*40,fetch=lambda target:shutil.copy2(artifact,target))
 assert not (data/'agent-package'/'SIMONAgent-store.zip').exists()
