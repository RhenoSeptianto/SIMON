$ErrorActionPreference='Stop'
$userDir=$PSScriptRoot
$log=Join-Path $userDir 'startup.log'
function Write-StartupLog($Message){Add-Content -LiteralPath $log -Value "$(Get-Date -Format s) $Message" -Encoding UTF8}
$mutex=$null;$locked=$false
try {
    if((Test-Path -LiteralPath $log) -and (Get-Item -LiteralPath $log).Length -gt 1048576){Move-Item -LiteralPath $log -Destination ($log+'.previous') -Force}
    $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $mutex=New-Object Threading.Mutex($false,"Local\SIMONUserAgent-$sid")
    try {$locked=$mutex.WaitOne(0)} catch [Threading.AbandonedMutexException] {$locked=$true}
    if(-not $locked){Write-StartupLog 'Peluncur user sudah aktif; duplikat dibatalkan.';exit 0}
    $exe=(Get-Content -LiteralPath (Join-Path $userDir 'launcher.json') -Raw | ConvertFrom-Json).exe
    $config=Join-Path $userDir 'config.json'
    if(-not (Test-Path -LiteralPath $exe)){throw 'EXE hilang/tidak dapat diakses. Periksa lokasi paket dan riwayat karantina antivirus.'}
    $existing=Get-CimInstance Win32_Process -Filter "Name='SIMONAgent.exe'" | Where-Object {$_.ExecutablePath -eq $exe}
    if($existing){Write-StartupLog 'Agent dari folder ini sudah berjalan; tidak menjalankan duplikat.';exit 0}
    foreach($name in @('worker-stdout.log','worker-stderr.log')) {
        $path=Join-Path $userDir $name
        if(Test-Path -LiteralPath $path){Move-Item -LiteralPath $path -Destination ($path+'.previous') -Force}
    }
    Write-StartupLog "Menjalankan agent: $exe"
    # Agent keeps its rotating agent.log; avoid duplicating routine console logs here.
    $env:SIAMS_WORKER_CAPTURE='1'
    $worker=Start-Process -FilePath $exe -ArgumentList @('--config',('"{0}"' -f $config)) -WorkingDirectory (Split-Path -Parent $exe) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $userDir 'worker-stdout.log') -RedirectStandardError (Join-Path $userDir 'worker-stderr.log') -PassThru
    Write-StartupLog "Agent dimulai PID $($worker.Id)."
    $null=$worker.Handle
    $worker.WaitForExit()
    Write-StartupLog "Agent berhenti, exit code $($worker.ExitCode). Lihat SIMONAgent\data\agent.log dan worker-stderr.log."
} catch {Write-StartupLog "GAGAL: $($_.Exception.Message). Access denied belum membuktikan blokir antivirus.";exit 1}
finally {if($locked){$mutex.ReleaseMutex()};if($mutex){$mutex.Dispose()}}
