import os,subprocess,json
from pathlib import Path
import pytest

@pytest.mark.skipif(os.name!='nt',reason='PowerShell installer integration')
def test_in_place_install_preserves_legacy_identity_and_logs_failure(tmp_path):
    root=Path(__file__).resolve().parents[1]
    package=tmp_path/'package';binary=package/'SIMONAgent';binary.mkdir(parents=True)
    (binary/'SIMONAgent.exe').write_bytes(b'fixture')
    (binary/'HDSentinel.xml').write_text('<existing/>')
    (package/'ca.crt').write_text('public ca fixture')
    legacy=tmp_path/'programdata';(legacy/'SIAMS').mkdir(parents=True);(legacy/'SIMON').mkdir()
    (legacy/'SIAMS'/'identity.json').write_text('{"uuid":"existing-pc","claim":"fixture"}')
    (legacy/'SIMON'/'config.json').write_text('{"store_code":"00115"}')
    harness=r'''
param($Installer,$PackageRoot,$LegacyRoot)
$ErrorActionPreference='Stop'
$env:ProgramData=$LegacyRoot
$Server='https://172.18.123.92:8443';$StoreCode='00115'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($Installer,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Syntax error'}
foreach($name in @('Restore-AgentSetupAccess','Protect-AgentData')) {
    $definition=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
    Invoke-Expression $definition.Extent.Text
}
# Mock only OS mutations and network/EXE launch. Real filesystem/config/migration/log logic runs.
function Invoke-AgentAcl {param($AclArguments)}
function Get-CimInstance {param($Filter) return $null}
function New-Service {param($Name,$BinaryPathName,$DisplayName,$StartupType,$Description) $script:installedPath=$BinaryPathName}
function sc.exe { $global:LASTEXITCODE=0 }
function Start-Service {param($Name) if($script:failStart){throw 'Access denied fixture'} }
function Get-Service {param($Name) return [pscustomobject]@{Status='Running'} }
function Start-Sleep {param($Seconds)}
$body=[IO.File]::ReadAllText($Installer)
$body=$body.Substring($body.IndexOf('$installLog='))
$adminCheck=$ast.Find({param($n) $n -is [System.Management.Automation.Language.IfStatementAst] -and $n.Extent.Text -like '*WindowsBuiltInRole*'},$true)
$body=$body.Replace($adminCheck.Extent.Text,'')
$body=$body.Replace('$PSScriptRoot','$PackageRoot')
$body=$body.Replace("& `$exe --config (Join-Path `$source 'config.json') --check-connection | Out-Host",'$global:LASTEXITCODE=0')
Invoke-Expression $body
if($script:installedPath -ne ('"{0}" --service' -f (Join-Path $PackageRoot 'SIMONAgent\SIMONAgent.exe'))){throw 'Wrong service path'}
if((Get-Content -LiteralPath (Join-Path $PackageRoot 'SIMONAgent\data\identity.json') -Raw | ConvertFrom-Json).uuid -ne 'existing-pc'){throw 'Legacy identity not migrated'}
# A reinstall must use the identity already in the local folder, not replace from legacy.
[IO.File]::WriteAllText((Join-Path $PackageRoot 'SIMONAgent\data\identity.json'),'{"uuid":"local-retained"}')
Invoke-Expression $body
$script:failStart=$true
try {Invoke-Expression $body;throw 'Expected startup failure'} catch {if($_.Exception.Message -ne 'Access denied fixture'){throw}}
Write-Output 'IN_PLACE_INSTALL_OK'
'''
    script=tmp_path/'harness.ps1';script.write_text(harness,encoding='utf-8-sig')
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Installer',str(root/'deployment'/'agent'/'install.ps1'),'-PackageRoot',str(package),'-LegacyRoot',str(legacy)],capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'IN_PLACE_INSTALL_OK' in result.stdout
    config=json.loads((binary/'config.json').read_text(encoding='utf-8-sig'))
    assert config['state']=='data' and config['sentinel_xml']=='HDSentinel.xml' and config['store_code']=='00115'
    assert json.loads((binary/'data'/'identity.json').read_text())['uuid']=='local-retained'
    assert json.loads((legacy/'SIAMS'/'identity.json').read_text())['uuid']=='existing-pc'
    assert (binary/'HDSentinel.xml').read_text()=='<existing/>'
    log=(package/'install.log').read_text(encoding='utf-8-sig')
    assert 'Access denied fixture' in log and 'Menjalankan service' in log
