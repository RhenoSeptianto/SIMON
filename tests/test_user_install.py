import os,subprocess,json
from pathlib import Path
import pytest

@pytest.mark.skipif(os.name!='nt',reason='Windows user installer')
def test_user_installer_retains_manual_identity_creates_startup_and_no_duplicate(tmp_path):
 root=Path(__file__).resolve().parents[1]
 package=tmp_path/'package';(package/'SIMONAgent').mkdir(parents=True)
 (package/'SIMONAgent'/'SIMONAgent.exe').write_bytes(b'fixture')
 (package/'ca.crt').write_text('ca fixture')
 (package/'start-user.ps1').write_text('# launcher fixture')
 local=tmp_path/'local';state=local/'SIMON'/'data';state.mkdir(parents=True)
 (state/'identity.json').write_text('{"uuid":"store417-existing"}')
 startup=tmp_path/'startup';startup.mkdir()
 # Replace only the external startup folder/COM/process APIs; run all actual installer logic.
 original=(root/'deployment'/'agent'/'install-user.ps1').read_text(encoding='utf-8-sig')
 original=original.replace("$startup=[Environment]::GetFolderPath('Startup')","$startup=$env:SIMON_TEST_STARTUP")
 (package/'install-user.ps1').write_text(original,encoding='utf-8-sig')
 harness=r'''
param($Package,$Local,$Startup)
$env:LOCALAPPDATA=$Local;$env:SIMON_TEST_STARTUP=$Startup
$global:launches=0;$global:running=$false
function New-Object {
 param($ComObject)
 $shell=[pscustomobject]@{}
 $shell | Add-Member ScriptMethod CreateShortcut {
  param($path)
  $link=[pscustomobject]@{Path=$path;TargetPath='';Arguments='';WorkingDirectory='';WindowStyle=0;Description=''}
  $link | Add-Member ScriptMethod Save { $this | ConvertTo-Json | Set-Content -LiteralPath $this.Path }
  return $link
 }
 return $shell
}
function Start-Process {$global:launches++}
function Get-CimInstance {
 param($Filter)
 if($global:running){return [pscustomobject]@{ExecutablePath=(Join-Path $Package 'SIMONAgent\SIMONAgent.exe')}}
}
& (Join-Path $Package 'install-user.ps1') -StoreCode '417'
if($global:launches -ne 1){throw 'Agent not started'}
$global:running=$true
& (Join-Path $Package 'install-user.ps1') -StoreCode '417'
if($global:launches -ne 1){throw 'Duplicate agent started'}
'''
 script=tmp_path/'harness.ps1';script.write_text(harness,encoding='utf-8-sig')
 result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Package',str(package),'-Local',str(local),'-Startup',str(startup)],capture_output=True,text=True,timeout=25)
 assert result.returncode==0,result.stdout+result.stderr
 config=json.loads((package/'config.json').read_text(encoding='utf-8-sig'))
 assert config['store_code']=='417' and Path(config['state'])==package/'SIMONAgent'/'data'
 assert Path(config['sentinel_xml'])==package/'SIMONAgent'/'HDSentinel.xml'
 assert json.loads((state/'identity.json').read_text())['uuid']=='store417-existing'
 assert json.loads((package/'SIMONAgent'/'data'/'identity.json').read_text())['uuid']=='store417-existing'
 link=json.loads((startup/'SIMON Agent.lnk').read_text(encoding='utf-8-sig'))
 assert 'start-user.ps1' in link['Arguments'] and 'Hidden' in link['Arguments']
 assert (package/'install-user.log').exists()


@pytest.mark.skipif(os.name!='nt',reason='Windows launcher integration')
def test_user_launcher_captures_worker_startup_error_without_touching_real_startup(tmp_path):
 import sys
 root=Path(__file__).resolve().parents[1]
 user=tmp_path/'SIMON';user.mkdir()
 # Python rejects --config immediately: a safe real process to exercise hidden launch/error logging.
 (user/'launcher.json').write_text(json.dumps({'exe':sys.executable}))
 (user/'config.json').write_text('{}')
 launcher=user/'start-user.ps1';launcher.write_bytes((root/'deployment'/'agent'/'start-user.ps1').read_bytes())
 env=os.environ.copy();env['LOCALAPPDATA']=str(tmp_path)
 result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(launcher)],env=env,capture_output=True,text=True,timeout=20)
 assert result.returncode==0,result.stdout+result.stderr
 log=(user/'startup.log').read_text(encoding='utf-8-sig')
 assert 'Agent dimulai PID' in log and 'exit code 2' in log
 assert (user/'worker-stderr.log').stat().st_size>0
