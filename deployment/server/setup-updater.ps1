param([string]$DataPath='',[string]$GitPath='',[switch]$SkipRestart)
$ErrorActionPreference='Stop'
if(-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Klik kanan setup-updater.bat > Run as administrator.'}
$rootPath=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if(-not $DataPath){$DataPath=Join-Path $rootPath 'data'}
$DataPath=[IO.Path]::GetFullPath($DataPath)
$python=Join-Path $rootPath '.venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $python)){throw 'Python server belum siap. Jalankan setup-server.bat terlebih dahulu.'}
if(-not $GitPath){$GitPath=(Get-Command git.exe -ErrorAction Stop).Source}
$folder=Join-Path $DataPath 'updater'
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$serverTask=Get-ScheduledTask -TaskName SIMONServer -ErrorAction Stop
$action=$serverTask.Actions | Select-Object -First 1
if($serverTask.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')){throw 'Task SIMONServer harus berjalan sebagai SYSTEM. Gunakan konfigurasi setup-server.bat sebelum memasang helper.'}
$taskState=Join-Path $folder 'setup-task.json'
@{python=$action.Execute;root=$action.WorkingDirectory;arguments=$action.Arguments} | ConvertTo-Json | Set-Content -LiteralPath $taskState -Encoding UTF8
$databaseUrlFile=Join-Path $DataPath 'database-url.txt'
$databaseKind='sqlite';$databaseId=''
if(Test-Path -LiteralPath $databaseUrlFile -PathType Leaf){
 $descriptor=& $python -c "import json,sys;from backend.database import database_descriptor;print(json.dumps(database_descriptor(open(sys.argv[1],encoding='utf-8-sig').read().strip())))" $databaseUrlFile | ConvertFrom-Json
 $databaseKind=$descriptor.kind;$databaseId=$descriptor.id
} else {
 $databasePath=Join-Path $DataPath 'siams.db'
 $descriptor=& $python -c "import json,sys;from backend.database import database_descriptor;print(json.dumps(database_descriptor('sqlite:///'+sys.argv[1])))" $databasePath | ConvertFrom-Json
 $databaseId=$descriptor.id
}
$serverTransition=$false
Push-Location -LiteralPath $rootPath
try {
 Write-Host '[Update 1/4] Memeriksa server dan database aktif...'
 # Load the new health endpoint WITHOUT changing the database/task arguments first.
 # This prevents a leftover SQLite file from replacing an active external database.
 $serverTransition=$true
 if(-not (Test-Path -LiteralPath (Join-Path $folder 'installed.json'))){
  if((Get-ScheduledTask -TaskName SIMONServer).State -in @('Running','Queued')){Stop-ScheduledTask -TaskName SIMONServer;Start-Sleep -Seconds 2}
  Start-ScheduledTask -TaskName SIMONServer
 }
 & $python -m tools.server_healthcheck --ca (Join-Path $DataPath 'tls\ca.crt') --url 'https://127.0.0.1:8443/api/health' --expected-kind $databaseKind --expected-id $databaseId
 if($LASTEXITCODE -ne 0){throw 'Database aktif tidak cocok atau health endpoint belum siap. Database dan konfigurasi task lama dipertahankan.'}
 $setupArguments=@('-m','tools.setup_updater','--root',$rootPath,'--data',$DataPath,'--git',$GitPath,'--task-state',$taskState)
 if($databaseKind -like 'postgresql*'){$setupArguments+=@('--database-url-file',$databaseUrlFile)}
 & $python @setupArguments
 if($LASTEXITCODE -ne 0){throw 'Pemasangan helper gagal. Baca pesan di atas.'}
 Write-Host '[Update 2/4] Mendaftarkan helper UpdateSimon...'
 $updaterAction=New-ScheduledTaskAction -Execute $python -Argument ('"{0}" --config "{1}"' -f (Join-Path $folder 'worker.py'),(Join-Path $folder 'config.json')) -WorkingDirectory $rootPath
 $trigger=New-ScheduledTaskTrigger -AtStartup
 $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances Queue -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
 Register-ScheduledTask -TaskName SIMONUpdater -Action $updaterAction -Trigger $trigger -Settings $settings -User SYSTEM -RunLevel Highest -Force -Description 'SIMON updater and automatic rollback/recovery' | Out-Null
 # Secure the root once, then reset descendants in one native recursive pass so
 # large release virtualenvs do not require thousands of icacls processes.
 Write-Host '[Update 3/4] Mengamankan folder helper (bisa beberapa detik)...'
 & icacls.exe $folder /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /remove:g '*S-1-5-32-545' '*S-1-5-11' '*S-1-1-0' /Q | Out-Null
 if($LASTEXITCODE -ne 0){throw "Gagal melindungi folder helper: $folder"}
 & icacls.exe (Join-Path $folder '*') /reset /T /C /Q | Out-Null
 if($LASTEXITCODE -ne 0){throw "Gagal menerapkan permission turunan helper: $folder"}
 $current=Get-Content -LiteralPath (Join-Path $folder 'current.json') -Raw | ConvertFrom-Json
 if(-not (Test-Path -LiteralPath $current.root)){throw 'Folder versi aktif tidak ditemukan. Task server belum diubah.'}
 if(-not $current.arguments){throw 'Konfigurasi versi belum lengkap. Periksa pemasangan helper.'}
 $serverTransition=$true
 if(-not $SkipRestart){if((Get-ScheduledTask -TaskName SIMONServer).State -in @('Running','Queued')){Stop-ScheduledTask -TaskName SIMONServer;Start-Sleep -Seconds 2}}
 $serverAction=New-ScheduledTaskAction -Execute $current.python -Argument $current.arguments -WorkingDirectory $current.root
 Set-ScheduledTask -TaskName SIMONServer -Action $serverAction | Out-Null
 if(-not $SkipRestart){Start-ScheduledTask -TaskName SIMONServer}
 Write-Host '[Update 4/4] Memeriksa server setelah konfigurasi...'
 & $python -m tools.server_healthcheck --ca (Join-Path $DataPath 'tls\ca.crt') --url 'https://127.0.0.1:8443/api/health' --expected-version $current.sha --expected-kind $databaseKind --expected-id $databaseId
 if($LASTEXITCODE -ne 0){throw 'Helper terpasang, tetapi server belum lolos health check. Periksa data\logs\server.log.'}
 @{task='SIMONUpdater';installed_at=(Get-Date -Format s)} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $folder 'installed.json') -Encoding UTF8
 $serverTransition=$false
 Write-Host 'Helper update siap. Login Super Admin > Pembaruan > Cek update.'
} catch {
 if($serverTransition){
  try {if((Get-ScheduledTask -TaskName SIMONServer).State -in @('Running','Queued')){Stop-ScheduledTask -TaskName SIMONServer};Set-ScheduledTask -TaskName SIMONServer -Action $action | Out-Null;Start-ScheduledTask -TaskName SIMONServer;Write-Warning 'Task server dikembalikan ke konfigurasi sebelum pemasangan helper.'}
  catch {Write-Warning ('Pemulihan task awal gagal: '+$_.Exception.Message)}
 }
 throw
} finally {Pop-Location}
