param([string]$HostName='127.0.0.1',[int]$Port=5432,[string]$AdminUser='postgres')
$ErrorActionPreference='Stop'
if(-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Klik kanan migrate-postgresql.bat lalu Run as administrator.'}
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$data=Join-Path $root 'data';$source=Join-Path $data 'siams.db';$python=Join-Path $root '.venv\Scripts\python.exe';$urlFile=Join-Path $data 'database-url.txt'
if(-not (Test-Path -LiteralPath $source -PathType Leaf)){throw "Database SQLite tidak ditemukan: $source"}
if(-not (Test-Path -LiteralPath $python -PathType Leaf)){throw 'Python server tidak ditemukan. Jalankan setup-server.bat terlebih dahulu.'}
if(-not (Get-Command psql.exe -ErrorAction SilentlyContinue)){
 $candidate=Get-ChildItem "$env:ProgramFiles\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
 if(-not $candidate){throw 'PostgreSQL belum terpasang. Instal PostgreSQL for Windows terlebih dahulu, lalu jalankan migrasi ini lagi.'}
 $env:Path=$candidate.Directory.FullName+';'+$env:Path
}
& $python -m pip install --disable-pip-version-check -r (Join-Path $root 'deployment\server\requirements.txt')
if($LASTEXITCODE -ne 0){throw 'Dependency PostgreSQL gagal dipasang.'}
$secure=Read-Host "Password user PostgreSQL '$AdminUser'" -AsSecureString
$pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$task=Get-ScheduledTask -TaskName SIMONServer -ErrorAction Stop;$oldAction=$task.Actions | Select-Object -First 1
try{
 $env:SIMON_PG_ADMIN_PASSWORD=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
 if($task.State -in @('Running','Queued')){Stop-ScheduledTask -TaskName SIMONServer;Start-Sleep -Seconds 3}
 Push-Location $root
 & $python -m tools.migrate_postgresql --source $source --data $data --host $HostName --port $Port --admin-user $AdminUser
 if($LASTEXITCODE -ne 0){throw 'Pemindahan data ke PostgreSQL gagal.'}
 & icacls.exe $urlFile /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' /Q | Out-Null
 if($LASTEXITCODE -ne 0){throw 'Gagal melindungi file kredensial database.'}
 $arguments='-m backend.run_server --data "'+$data+'" --database-url-file "'+$urlFile+'"'
 $newAction=New-ScheduledTaskAction -Execute $oldAction.Execute -Argument $arguments -WorkingDirectory $oldAction.WorkingDirectory
 Set-ScheduledTask -TaskName SIMONServer -Action $newAction | Out-Null
 Start-ScheduledTask -TaskName SIMONServer
 & $python -m tools.server_healthcheck --ca (Join-Path $data 'tls\ca.crt') --url 'https://127.0.0.1:8443/api/health' --expected-kind postgresql
 if($LASTEXITCODE -ne 0){throw 'Server PostgreSQL belum sehat.'}
 & (Join-Path $PSScriptRoot 'setup-updater.ps1') -DataPath $data
 if($LASTEXITCODE -ne 0){throw 'PostgreSQL aktif, tetapi helper UpdateSimon gagal dikonfigurasi ulang.'}
 Write-Host 'Migrasi PostgreSQL selesai. Agent tidak perlu dipasang ulang.'
} catch {
 try{if((Get-ScheduledTask -TaskName SIMONServer).State -in @('Running','Queued')){Stop-ScheduledTask -TaskName SIMONServer};Set-ScheduledTask -TaskName SIMONServer -Action $oldAction | Out-Null;Start-ScheduledTask -TaskName SIMONServer}catch{}
 throw
} finally {
 $env:SIMON_PG_ADMIN_PASSWORD=$null
 if($pointer -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}
 Pop-Location -ErrorAction SilentlyContinue
}
