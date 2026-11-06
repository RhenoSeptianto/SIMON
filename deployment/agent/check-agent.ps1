$ErrorActionPreference='Continue'
$userDir=$PSScriptRoot
$userConfig=Join-Path $userDir 'config.json'
$userMode=Test-Path -LiteralPath $userConfig
$report=if($userMode){Join-Path $userDir 'check-agent.log'}else{Join-Path $PSScriptRoot 'check-agent.log'}
Start-Transcript -LiteralPath $report -Append -ErrorAction Stop | Out-Null
try {
    Write-Host "=== SIMON pemeriksaan $(Get-Date -Format s) ==="
    $folder=Join-Path $PSScriptRoot 'SIMONAgent'
    $exe=Join-Path $folder 'SIMONAgent.exe'
    $config=if($userMode){$userConfig}else{Join-Path $folder 'config.json'}
    $settings=$null
    if($userMode){
        $settings=Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
        $launcher=Get-Content -LiteralPath (Join-Path $userDir 'launcher.json') -Raw | ConvertFrom-Json
        $exe=$launcher.exe;$folder=Split-Path -Parent $exe
        Write-Host 'Mode Startup user: service tidak diperlukan.'
        $startupLink=Join-Path ([Environment]::GetFolderPath('Startup')) 'SIMON Agent.lnk'
        Write-Host "Shortcut Startup ada: $(Test-Path -LiteralPath $startupLink)"
    }
    $dataDir=if($userMode){$settings.state}else{Join-Path $folder 'data'}
    $caPath=if($userMode){Join-Path $userDir 'ca.crt'}else{Join-Path $folder 'ca.crt'}
    foreach($path in @($exe,$config,$caPath,(Join-Path $folder 'HDSentinel.xml'))) {
        try {
            $item=Get-Item -LiteralPath $path -ErrorAction Stop
            Write-Host "ADA: $path ($($item.Length) byte), diubah $($item.LastWriteTime)"
            $stream=[IO.File]::OpenRead($path);$stream.Dispose()
            Write-Host 'Akses baca: OK'
        } catch { Write-Host "TIDAK DAPAT DIBACA: $path : $($_.Exception.Message)" }
    }
    $service=Get-CimInstance Win32_Service -Filter "Name='SIMONAgent'"
    if($service) { $service | Select-Object Name,State,StartMode,PathName,ExitCode | Format-List }
    else { Write-Host 'SERVICE BELUM TERDAFTAR' }
    try {
        $probe=Join-Path $dataDir 'diagnostic-write.tmp'
        [IO.File]::WriteAllText($probe,'test');Remove-Item -LiteralPath $probe -ErrorAction Stop
        Write-Host 'Akses tulis folder data: OK'
    } catch { Write-Host "AKSES TULIS GAGAL: $($_.Exception.Message)" }
    if((Test-Path -LiteralPath $exe) -and (Test-Path -LiteralPath $config)) {
        Write-Host '=== Menjalankan EXE dan memeriksa HTTPS (CA diverifikasi) ==='
        try {
            & $exe --config $config --check-connection 2>&1 | Out-Host
            Write-Host "Exit code EXE: $LASTEXITCODE"
        } catch { Write-Host "EXE GAGAL DIJALANKAN: $($_.Exception.Message)" }
    }
    Write-Host '=== Log agent terakhir ==='
    $log=Join-Path $dataDir 'agent.log'
    if(Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log -Tail 40 }
    else { Write-Host 'Log agent belum dibuat; worker mungkin belum berjalan.' }
    $workerLog=Join-Path $dataDir 'service-worker.log'
    if(Test-Path -LiteralPath $workerLog) { Write-Host '=== Log startup worker ==='; Get-Content -LiteralPath $workerLog -Tail 25 }
    if($userMode){foreach($name in @('startup.log','worker-stderr.log')){$path=Join-Path $userDir $name;if(Test-Path -LiteralPath $path){Write-Host "=== $name ===";Get-Content -LiteralPath $path -Tail 25}}}
    $since=(Get-Date).AddHours(-2)
    foreach($channel in @('System','Microsoft-Windows-CodeIntegrity/Operational','Microsoft-Windows-AppLocker/EXE and DLL','Microsoft-Windows-Windows Defender/Operational')) {
        Write-Host "=== Event Windows: $channel (2 jam terakhir, terkait SIMON) ==="
        try {
            $events=Get-WinEvent -FilterHashtable @{LogName=$channel;StartTime=$since} -MaxEvents 300 -ErrorAction Stop
            $matches=@($events | Where-Object {$_.Message -match 'SIMONAgent|SIMONAgent-store|HDSentinel' } | Select-Object -First 15 TimeCreated,Id,ProviderName,Message)
            if($matches.Count) { $matches | Format-List } else { Write-Host 'Tidak ada event terkait yang ditemukan.' }
        } catch { Write-Host "Event tidak tersedia: $($_.Exception.Message)" }
    }
    Write-Host 'Tidak ada event bukan berarti antivirus pasti tidak memblokir. Untuk Sangfor, cocokkan waktu kejadian dengan riwayat karantina/kebijakan di konsol pengelola.'
    Write-Host 'Laporan berisi lokasi file/IP/serial dalam pesan error; bagikan hanya ke tim IT.'
} finally {
    Stop-Transcript | Out-Null
    Write-Host "Laporan: $report"
}
