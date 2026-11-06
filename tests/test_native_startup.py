import json,os
from pathlib import Path
import pytest
from agent.user_startup import install

@pytest.mark.skipif(os.name!='nt',reason='Real Windows COM shortcut')
def test_native_install_real_shortcut_migrates_identity_and_keeps_config(tmp_path,monkeypatch):
 import win32com.client
 root=tmp_path/'paket agent';(root/'SIMONAgent').mkdir(parents=True)
 exe=root/'SIMONAgent'/'SIMONAgent.exe';exe.write_bytes(b'fixture')
 (root/'ca.crt').write_text('public ca')
 legacy=tmp_path/'local';state=legacy/'SIMON'/'data';state.mkdir(parents=True)
 (state/'identity.json').write_text('{"uuid":"same-PC-A31"}')
 monkeypatch.setenv('LOCALAPPDATA',str(legacy))
 startup=tmp_path/'fake-startup';startup.mkdir()
 install(root,'A31',startup=startup,launch=False)
 link=win32com.client.Dispatch('WScript.Shell').CreateShortCut(str(startup/'SIMON Agent.lnk'))
 assert Path(link.TargetPath)==exe
 assert '--background --config' in link.Arguments and 'powershell' not in link.TargetPath.lower()
 assert json.loads((root/'SIMONAgent'/'data'/'identity.json').read_text())['uuid']=='same-PC-A31'
 install(root,'B32',startup=startup,launch=False)
 assert json.loads((root/'config.json').read_text())['store_code']=='B32'
 assert json.loads((root/'SIMONAgent'/'data'/'identity.json').read_text())['uuid']=='same-PC-A31'
 assert (root/'install-user.log').exists()
