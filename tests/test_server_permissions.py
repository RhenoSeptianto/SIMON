import os,subprocess
from pathlib import Path
import pytest
from tools.server_healthcheck import check_https


def test_healthcheck_reports_ca_failure_without_traceback(tmp_path,capsys):
    assert check_https(str(tmp_path/'missing.crt'),'https://127.0.0.1:8443/',attempts=1)==1
    output=capsys.readouterr()
    assert 'HEALTH_CHECK_FAILED: CA' in output.out
    assert output.err==''


@pytest.mark.skipif(os.name!='nt',reason='Windows ACL regression')
def test_protect_data_sets_real_file_grants_not_directory_inheritance_flags(tmp_path):
    script=Path(__file__).resolve().parents[1]/'deployment'/'server'/'setup-server.ps1'
    # Load just the real ACL function via the PowerShell AST; do not run setup,
    # register services/tasks, change firewall, or touch operational data.
    harness=r'''
param([string]$Installer,[string]$Sandbox)
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($Installer,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Installer parse failed'}
$function=$ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Protect-OperationalData'},$true)
Invoke-Expression $function.Extent.Text
function Invoke-Checked {param($Exe,$Arguments,$FailureMessage) & $Exe @Arguments | Out-Null; if($LASTEXITCODE){throw $FailureMessage}}
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$folder=Join-Path $Sandbox 'data';$nested=Join-Path $folder 'tls'
New-Item -ItemType Directory -Path $nested -Force | Out-Null
$db=Join-Path $folder 'siams.db';$ca=Join-Path $nested 'ca.crt'
Set-Content -LiteralPath $db -Value 'fixture';Set-Content -LiteralPath $ca -Value 'fixture'
try {
    Protect-OperationalData -DataPath $folder -SetupUserSid $sid
    # This test runs unelevated. Restore owner access to inspect the resulting
    # DACL while retaining the SYSTEM/Administrators entries being asserted.
    foreach($directory in @($folder,$nested)) { & icacls.exe $directory /grant:r "*${sid}:(OI)(CI)F" /Q | Out-Null }
    foreach($item in @($db,$ca)) { & icacls.exe $item /grant:r "*${sid}:F" /Q | Out-Null }
    foreach($file in @($db,$ca)) {
        $acl=Get-Acl -LiteralPath $file
        foreach($expectedSid in @('S-1-5-18','S-1-5-32-544')) {
            $grants=@($acl.Access | Where-Object { $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq $expectedSid -and $_.AccessControlType -eq 'Allow' -and ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl })
            if($grants.Count -ne 1){throw "Missing FullControl grant on file $file for $expectedSid"}
        }
    }
    Write-Output 'ACL_REGRESSION_OK'
} finally {
    # Restore access only on the fixtures, so pytest can clean up its own directory.
    foreach($directory in @($folder,$nested)) { & icacls.exe $directory /grant:r "*${sid}:(OI)(CI)F" /Q | Out-Null }
    foreach($file in @($db,$ca)) { & icacls.exe $file /grant:r "*${sid}:F" /Q | Out-Null }
}
'''
    test_script=tmp_path/'acl-test.ps1';test_script.write_text(harness,encoding='utf-8-sig')
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(test_script),'-Installer',str(script),'-Sandbox',str(tmp_path)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'ACL_REGRESSION_OK' in result.stdout
