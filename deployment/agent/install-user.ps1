param([string]$Server='https://172.18.123.92:8443',[string]$StoreCode='')
$ErrorActionPreference='Stop'
$userDir=$PSScriptRoot
$legacyDir=Join-Path $env:LOCALAPPDATA 'SIMON'
New-Item -ItemType Directory -Path $userDir -Force | Out-Null
$log=Join-Path $userDir 'install-user.log'
Start-Transcript -LiteralPath $log -Append | Out-Null
try {
    $uri=[Uri]$Server
    if($uri.Scheme -ne 'https' -or -not $uri.Host){throw 'Alamat server harus HTTPS.'}
    $exe=Join-Path $PSScriptRoot 'SIMONAgent\SIMONAgent.exe'
    $xml=Join-Path $PSScriptRoot 'SIMONAgent\HDSentinel.xml'
    $ca=Join-Path $PSScriptRoot 'ca.crt'
    if(-not (Test-Path -LiteralPath $exe)){throw 'SIMONAgent.exe tidak ditemukan. Ekstrak paket lengkap terlebih dahulu.'}
    if(-not (Test-Path -LiteralPath $ca)){throw 'ca.crt tidak ditemukan. Gunakan paket dari server kantor.'}
    $configPath=Join-Path $userDir 'config.json'
    $previous=$null
    if(Test-Path -LiteralPath $configPath){$previous=Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json}
    elseif(Test-Path -LiteralPath (Join-Path $legacyDir 'config.json')){$previous=Get-Content -LiteralPath (Join-Path $legacyDir 'config.json') -Raw | ConvertFrom-Json}
    if(-not $StoreCode){
        $default=if($previous){$previous.store_code}else{''}
        $StoreCode=Read-Host $(if($default){"Kode store (Enter tetap $default)"}else{'Masukkan kode store, contoh 417'})
        if(-not $StoreCode){$StoreCode=$default}
    }
    $StoreCode=([string]$StoreCode).Trim()
    if(-not $StoreCode -or $StoreCode.Length -gt 40){throw 'Kode store wajib diisi, maksimal 40 karakter.'}
    $state=Join-Path $PSScriptRoot 'SIMONAgent\data'
    New-Item -ItemType Directory -Path $state -Force | Out-Null
    $legacyState=Join-Path $legacyDir 'data'
    if(-not (Test-Path -LiteralPath (Join-Path $state 'identity.json')) -and (Test-Path -LiteralPath (Join-Path $legacyState 'identity.json'))) {
        $active=Get-CimInstance Win32_Process -Filter "Name='SIMONAgent.exe'" | Where-Object {$_.ExecutablePath -eq $exe}
        if($active){throw 'Tutup agent lama dengan Ctrl+C atau logout terlebih dahulu, lalu install lagi agar identitas dapat dipindahkan dengan aman.'}
        Copy-Item -Path (Join-Path $legacyState '*') -Destination $state -Recurse -Force
        Write-Host 'Identitas lama disalin ke folder D; sumber lama dipertahankan.'
    }
    @{server=$Server.TrimEnd('/');store_code=$StoreCode;state=$state;ca_file='ca.crt';sentinel_xml=$xml} | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
    @{exe=$exe} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $userDir 'launcher.json') -Encoding UTF8
    # Keep a visible, standard per-user Startup shortcut, without elevation/service registration.
    $startup=[Environment]::GetFolderPath('Startup')
    if(-not $startup){throw 'Folder Startup user tidak tersedia.'}
    $shell=New-Object -ComObject WScript.Shell
    $shortcut=$shell.CreateShortcut((Join-Path $startup 'SIMON Agent.lnk'))
    $shortcut.TargetPath=Join-Path $PSHOME 'powershell.exe'
    $shortcut.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f (Join-Path $userDir 'start-user.ps1')
    $shortcut.WorkingDirectory=$userDir
    $shortcut.WindowStyle=7
    $shortcut.Description='SIMON monitoring - otomatis saat user login'
    $shortcut.Save()
    Write-Host "Startup berhasil dibuat untuk user $env:USERNAME. Kode store: $StoreCode"
    Write-Host "EXE tetap: $exe"
    Write-Host "Ekspor XML Sentinel ke: $xml"
    $existing=Get-CimInstance Win32_Process -Filter "Name='SIMONAgent.exe'" | Where-Object {$_.ExecutablePath -eq $exe}
    if($existing){Write-Host 'Agent dari folder ini sudah berjalan. Tidak menjalankan salinan kedua. Startup aktif untuk login berikutnya.'}
    else {
        Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',('"{0}"' -f (Join-Path $userDir 'start-user.ps1'))) -WindowStyle Hidden
        Write-Host 'Peluncur agent dijalankan. Periksa dashboard dan log jika belum Online.'
    }
    Write-Host "Log: $userDir\install-user.log, startup.log, SIMONAgent\data\agent.log"
    Write-Host 'Tidak perlu administrator. Agent berjalan setelah user ini login, termasuk saat layar dikunci; berhenti saat logout.'
} catch {
    Write-Host "INSTALASI USER GAGAL: $($_.Exception.Message)" -ForegroundColor Red
    throw
} finally { Stop-Transcript | Out-Null; Write-Host "Log instalasi: $log" }
