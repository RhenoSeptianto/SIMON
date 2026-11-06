$ErrorActionPreference = 'Stop'
$rootPath = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $rootPath

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Jalankan deployment\server\setup-server.bat dengan Run as administrator.'
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    $invokeError = $null
    try {
        & $Exe @Arguments
        $exitCode = $LASTEXITCODE
    } catch {
        $invokeError = $_.Exception.Message
        $exitCode = 1
    }
    if ($exitCode -ne 0) {
        $detail = if ($invokeError) { " Detail: $invokeError" } else { '' }
        throw "$FailureMessage (exit code: $exitCode).$detail"
    }
}

function Protect-OperationalData {
    param(
        [Parameter(Mandatory = $true)][string]$DataPath,
        [Parameter(Mandatory = $true)][string]$SetupUserSid
    )

    $targets = @(
        Get-ChildItem -LiteralPath $DataPath -Force -Recurse -ErrorAction Stop |
            Sort-Object { $_.FullName.Length } -Descending |
            Select-Object -ExpandProperty FullName
    )
    $targets += $DataPath
    foreach ($target in $targets) {
        Invoke-Checked -Exe 'icacls.exe' -Arguments @(
            $target, '/inheritance:r', '/grant:r',
            '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F',
            '/remove:g', "*$SetupUserSid", '/Q'
        ) -FailureMessage "Gagal mengamankan permission '$target' untuk SYSTEM dan Administrators."
    }
}

function Resolve-PythonLauncher {
    $launcher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($launcher) { return $launcher.Source }

    $knownPaths = @(
        (Join-Path $env:WINDIR 'py.exe'),
        (Join-Path $env:ProgramFiles 'Python Launcher\py.exe'),
        (Join-Path $env:LocalAppData 'Programs\Python\Launcher\py.exe')
    )
    foreach ($path in $knownPaths) {
        if ($path -and (Test-Path -LiteralPath $path -PathType Leaf)) { return $path }
    }
    return $null
}

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $pathEntries = @($machinePath, $userPath) | Where-Object { $_ }
    $env:Path = $pathEntries -join ';'
}

function Test-Python312 {
    param([Parameter(Mandatory = $true)][string]$LauncherPath)

    $output = @()
    $exitCode = 0
    try {
        $output = @(& $LauncherPath '-3.12-64' '-c' 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.maxsize > 2**32, sep=chr(124))' 2>&1)
        $exitCode = $LASTEXITCODE
    } catch {
        $output = @($_.Exception.Message)
        $exitCode = 1
    }

    $outputLine = ''
    if ($output) { $outputLine = ($output | Select-Object -Last 1).ToString().Trim() }
    return [pscustomobject]@{
        IsValid = ($exitCode -eq 0 -and $outputLine -eq '3|12|True')
        Output = $output
        ExitCode = $exitCode
    }
}

$pythonLauncherPath = Resolve-PythonLauncher
$pythonProbe = $null
if ($pythonLauncherPath) {
    $pythonProbe = Test-Python312 -LauncherPath $pythonLauncherPath
}

if (-not $pythonLauncherPath -or -not $pythonProbe.IsValid) {
    $winget = Get-Command 'winget.exe' -ErrorAction SilentlyContinue
    if (-not $winget) {
        $probeDetails = ''
        if ($pythonProbe) { $probeDetails = ($pythonProbe.Output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine }
        throw "Python 3.12 x64 belum tersedia dan winget tidak ditemukan untuk memasangnya otomatis. Instal App Installer dari Microsoft Store atau Python 3.12 x64 dari https://www.python.org/downloads/windows/. Detail pemeriksaan: $probeDetails"
    }

    Write-Host 'Python Launcher atau runtime Python 3.12 x64 belum tersedia. Menginstal Python 3.12 x64 untuk semua pengguna lewat winget...'
    Invoke-Checked -Exe $winget.Source -Arguments @(
        'install', '--id', 'Python.Python.3.12', '--exact', '--scope', 'machine',
        '--silent', '--accept-package-agreements', '--accept-source-agreements'
    ) -FailureMessage 'Instalasi otomatis Python 3.12 x64 gagal. Pastikan PC terhubung ke internet dan winget/App Installer tersedia; kemudian instal Python 3.12 x64 manual dari https://www.python.org/downloads/windows/.'

    Refresh-ProcessPath
    $pythonLauncherPath = Resolve-PythonLauncher
    if (-not $pythonLauncherPath) {
        throw 'Python berhasil dipasang, tetapi Python Launcher (py.exe) belum dapat ditemukan. Buka terminal baru lalu jalankan setup lagi; jika masih gagal, instal Python 3.12 x64 dengan opsi Python Launcher dari https://www.python.org/downloads/windows/.'
    }

    $pythonProbe = Test-Python312 -LauncherPath $pythonLauncherPath
}

if (-not $pythonProbe.IsValid) {
    $detectedPython = ($pythonProbe.Output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    throw "Python 3.12 x64 tetap tidak dapat divalidasi setelah instalasi otomatis (exit code: $($pythonProbe.ExitCode)). Detail: $detectedPython`nInstal Python 3.12 x64 dari https://www.python.org/downloads/windows/ dan pastikan Python Launcher terpasang, lalu jalankan setup kembali."
}

$venvPath = Join-Path $rootPath '.venv'
$venvPythonPath = Join-Path $venvPath 'Scripts\python.exe'
$venvValidationCode = 'import pathlib,sys,pip; root=pathlib.Path(sys.argv[1]).resolve(); prefix=pathlib.Path(sys.prefix).resolve(); base=pathlib.Path(sys.base_prefix).resolve(); print(sys.version_info.major, sys.version_info.minor, int(prefix.samefile(root)), int(prefix != base), pip.__version__, sep=chr(124))'

$existingTask = Get-ScheduledTask -TaskName 'SIMONServer' -ErrorAction SilentlyContinue
if ($existingTask -and $existingTask.State -eq 'Running') {
    Stop-ScheduledTask -TaskName 'SIMONServer' -ErrorAction Stop
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        $existingTask = Get-ScheduledTask -TaskName 'SIMONServer' -ErrorAction SilentlyContinue
        if (-not $existingTask -or $existingTask.State -ne 'Running') { break }
    }
    if ($existingTask -and $existingTask.State -eq 'Running') {
        throw 'Task SIMONServer tidak berhenti setelah 30 detik. Hentikan server secara manual sebelum menjalankan setup.'
    }
}

$venvScriptsPath = Join-Path $venvPath 'Scripts'
$venvProcesses = Get-CimInstance -ClassName Win32_Process -ErrorAction Stop | Where-Object {
    $_.ExecutablePath -and $_.ExecutablePath.StartsWith($venvScriptsPath, [StringComparison]::OrdinalIgnoreCase)
}
if ($venvProcesses) {
    $processIds = ($venvProcesses | ForEach-Object { $_.ProcessId }) -join ', '
    throw "Masih ada proses yang menggunakan .venv (PID: $processIds). Hentikan proses/server tersebut sebelum menjalankan setup."
}
$listeners = @(Get-NetTCPConnection -LocalPort 8443 -State Listen -ErrorAction SilentlyContinue)
if ($listeners) {
    $listenerIds = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
    throw "Port 8443 masih digunakan (PID: $listenerIds). Pastikan server SIMON telah berhenti sebelum menjalankan setup."
}

$venvValid = $false
if (Test-Path -LiteralPath $venvPath) {
    if ((Get-Item -LiteralPath $venvPath).PSIsContainer -and (Test-Path -LiteralPath $venvPythonPath)) {
        $venvInfo = & $venvPythonPath '-c' $venvValidationCode $venvPath 2>&1
        $venvCheckExitCode = $LASTEXITCODE
        $venvInfoLine = ''
        if ($venvInfo) { $venvInfoLine = ($venvInfo | Select-Object -Last 1).ToString().Trim() }
        $venvValid = ($venvCheckExitCode -eq 0 -and $venvInfoLine -match '^3\|12\|1\|1\|.+$')
    }

    if (-not $venvValid) {
        $backupPath = "$venvPath.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        $backupIndex = 1
        while (Test-Path -LiteralPath $backupPath) {
            $backupPath = "$venvPath.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$backupIndex"
            $backupIndex++
        }
        Move-Item -LiteralPath $venvPath -Destination $backupPath -ErrorAction Stop
        Write-Host "Virtualenv tidak valid/kompatibel. Backup dipertahankan di: $backupPath"
    }
}

if (-not $venvValid) {
    Invoke-Checked -Exe $pythonLauncherPath -Arguments @('-3.12-64', '-m', 'venv', $venvPath) -FailureMessage 'Gagal membuat virtualenv Python 3.12.'
    $createdVenvInfo = & $venvPythonPath '-c' $venvValidationCode $venvPath 2>&1
    $createdVenvExitCode = $LASTEXITCODE
    $createdVenvInfoLine = ''
    if ($createdVenvInfo) { $createdVenvInfoLine = ($createdVenvInfo | Select-Object -Last 1).ToString().Trim() }
    if ($createdVenvExitCode -ne 0 -or $createdVenvInfoLine -notmatch '^3\|12\|1\|1\|.+$') {
        $detail = ($createdVenvInfo | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        throw "Virtualenv baru gagal divalidasi sebagai Python 3.12 yang sehat. Detail: $detail"
    }
}

$requirementsPath = Join-Path $rootPath 'deployment\server\requirements.txt'
if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
    throw "File dependency server tidak ditemukan: $requirementsPath"
}
Invoke-Checked -Exe $venvPythonPath -Arguments @('-m', 'pip', 'install', '-r', $requirementsPath) -FailureMessage 'Instalasi dependency server gagal. Periksa output pip di atas dan kompatibilitas paket dengan Python 3.12.'
Invoke-Checked -Exe $venvPythonPath -Arguments @('-m', 'pip', 'check') -FailureMessage 'Pemeriksaan dependency gagal: terdapat dependency yang hilang atau tidak kompatibel.'

$dataPath = Join-Path $rootPath 'data'
$databaseDataPath = $dataPath
if ($env:SIAMS_DATA) { $databaseDataPath = [IO.Path]::GetFullPath($env:SIAMS_DATA) }
$defaultDatabasePath = Join-Path $databaseDataPath 'siams.db'
$databaseInfoCode = 'import os,sys; from pathlib import Path; from sqlalchemy.engine import make_url; raw=os.getenv(sys.argv[1]); url=make_url(raw) if raw else None; backend=url.get_backend_name() if url else sys.argv[2]; path=(url.database if url else sys.argv[3]) or sys.argv[4]; print(backend); print(Path(path).resolve() if path != sys.argv[4] else path)'
$databaseInfo = & $venvPythonPath '-c' $databaseInfoCode 'DATABASE_URL' 'sqlite' $defaultDatabasePath ':memory:' 2>&1
$databaseInfoExitCode = $LASTEXITCODE
if ($databaseInfoExitCode -ne 0 -or $databaseInfo.Count -lt 2) {
    $databaseDetails = ($databaseInfo | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    throw "Tidak dapat menentukan lokasi database SIMON dari DATABASE_URL/SIAMS_DATA. Detail: $databaseDetails"
}
$databaseBackend = $databaseInfo[0].ToString().Trim()
$databasePath = $databaseInfo[1].ToString().Trim()
$permissionPaths = @($dataPath, $databaseDataPath)
$permissionPaths = @($permissionPaths | Select-Object -Unique)
foreach ($permissionPath in $permissionPaths) {
    New-Item -ItemType Directory -Path $permissionPath -Force | Out-Null
}
$databaseIsUnderDataPath = $false
if ($databaseBackend -eq 'sqlite' -and $databasePath -ne ':memory:' -and -not $databasePath.StartsWith('file:')) {
    foreach ($permissionPath in $permissionPaths) {
        $normalizedPermissionPath = [IO.Path]::GetFullPath($permissionPath).TrimEnd('\') + '\'
        if ($databasePath.StartsWith($normalizedPermissionPath, [StringComparison]::OrdinalIgnoreCase)) {
            $databaseIsUnderDataPath = $true
            break
        }
    }
    if (-not $databaseIsUnderDataPath) {
        Write-Warning "DATABASE_URL menunjuk ke SQLite di luar folder data SIMON: '$databasePath'. Setup tidak akan mengubah ACL folder eksternal agar file lain di folder tersebut tetap aman; preflight akan memastikan lokasi database sudah dapat diakses."
    }
}
$setupUserSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
foreach ($permissionPath in $permissionPaths) {
    Invoke-Checked -Exe 'icacls.exe' -Arguments @($permissionPath, '/grant:r', "*${setupUserSid}:(OI)(CI)F", '/T', '/Q') -FailureMessage "Gagal memberikan akses sementara ke data '$permissionPath' untuk akun SID $setupUserSid."
}

try {
    if ($databaseBackend -eq 'sqlite' -and $databasePath -ne ':memory:' -and -not $databasePath.StartsWith('file:')) {
        $probeArguments = @('-m', 'tools.database_doctor', '--database', $databasePath)
        if ($databaseIsUnderDataPath) { $probeArguments += '--repair-readonly' }
        Invoke-Checked -Exe $venvPythonPath -Arguments $probeArguments -FailureMessage "Database SQLite '$databasePath' tidak lolos pemeriksaan akses. Baca bagian SIMON SQLite check/GAGAL di atas untuk penyebab spesifik; data tidak dihapus."
    }

    Write-Host "Database SIMON: $databaseBackend ($databasePath)"
    Invoke-Checked -Exe $venvPythonPath -Arguments @('-m', 'tools.server_setup') -FailureMessage "Setup konfigurasi SIMON gagal. Pastikan akun setup dapat menulis database '$databasePath' dan periksa error TLS/database di atas."

    $backendCheckCode = 'from backend.main import app; assert app.title; print(app.title)'
    $backendCheck = & $venvPythonPath '-c' $backendCheckCode 2>&1
    $backendCheckExitCode = $LASTEXITCODE
    if ($backendCheckExitCode -ne 0) {
        $backendDetails = ($backendCheck | Select-Object -Last 20 | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        throw "Validasi backend gagal saat memuat aplikasi SIMON. Pastikan dependency Python 3.12 terpasang dan database '$databasePath' dapat dibuka. Detail:`n$backendDetails"
    }
    $backendCheck | ForEach-Object { Write-Host $_ }
} catch {
    $setupFailure = $_.Exception.Message
    try {
        foreach ($permissionPath in $permissionPaths) {
            Protect-OperationalData -DataPath $permissionPath -SetupUserSid $setupUserSid
        }
    } catch {
        throw "$setupFailure`nSelain itu, gagal memulihkan permission aman folder data: $($_.Exception.Message)"
    }
    throw $setupFailure
}

# Restrict operational database, credentials, and TLS private keys to administrators/SYSTEM.
foreach ($permissionPath in $permissionPaths) {
    Protect-OperationalData -DataPath $permissionPath -SetupUserSid $setupUserSid
}

$certificatePath = Join-Path $rootPath 'data\tls\ca.crt'
if (-not (Test-Path -LiteralPath $certificatePath -PathType Leaf)) {
    throw "Sertifikat CA tidak ditemukan setelah setup: $certificatePath"
}
$certificateTrustInstalled = $true
try {
    Import-Certificate -FilePath $certificatePath -CertStoreLocation 'Cert:\LocalMachine\Root' -ErrorAction Stop | Out-Null
} catch {
    $certificateTrustInstalled = $false
    Write-Warning "CA publik SIMON tidak dapat ditambahkan ke Windows Trusted Root: $($_.Exception.Message). Server tetap dapat berjalan, tetapi browser pada PC ini mungkin menampilkan peringatan sertifikat. Jika trust lokal diperlukan, impor '$certificatePath' ke Local Computer > Trusted Root Certification Authorities menggunakan certlm.msc atau minta bantuan administrator IT."
}

$expectedPythonPath = [IO.Path]::GetFullPath($venvPythonPath)
$taskIsValid = $false
if ($existingTask) {
    $existingAction = $existingTask.Actions | Select-Object -First 1
    $existingTrigger = $existingTask.Triggers | Where-Object { $_.CimClass.CimClassName -match 'Boot' } | Select-Object -First 1
    $expectedRoot = [IO.Path]::GetFullPath($rootPath)
    if ($existingAction -and $existingTrigger) {
        $taskIsValid = (
            [IO.Path]::GetFullPath($existingAction.Execute.Trim('"')) -eq $expectedPythonPath -and
            $existingAction.Argument -eq '-m backend.run_server' -and
            [IO.Path]::GetFullPath($existingAction.WorkingDirectory) -eq $expectedRoot -and
            $existingTask.Principal.UserId -match '^(SYSTEM|NT AUTHORITY\\SYSTEM|S-1-5-18)$' -and
            $existingTask.State -ne 'Disabled'
        )
    }
}

if (-not $taskIsValid) {
    $action = New-ScheduledTaskAction -Execute $venvPythonPath -Argument '-m backend.run_server' -WorkingDirectory $rootPath
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName 'SIMONServer' -Action $action -Trigger $trigger -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force -Description 'SIMON HTTPS office server' | Out-Null
} else {
    Write-Host 'Task SIMONServer dan konfigurasi valid dipertahankan.'
}

if (-not (Get-NetFirewallRule -Name 'SIMONServerHTTPS' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'SIMONServerHTTPS' -DisplayName 'SIMON Office HTTPS 8443' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443 -RemoteAddress '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16' | Out-Null
}

Start-ScheduledTask -TaskName 'SIMONServer' -ErrorAction Stop
$healthCheckCode = @'
import ssl,sys,time,urllib.request
context=ssl.create_default_context(cafile=sys.argv[1])
for attempt in range(30):
    try:
        with urllib.request.urlopen(sys.argv[2], context=context, timeout=2) as response:
            if response.status != 200:
                raise RuntimeError(response.status)
            print(response.status)
            break
    except Exception as exc:
        if attempt == 29:
            print(type(exc).__name__, exc, file=sys.stderr)
            raise SystemExit(1)
        time.sleep(1)
'@
$healthCheck = & $venvPythonPath '-c' $healthCheckCode $certificatePath 'https://127.0.0.1:8443/' 2>&1
$healthCheckExitCode = $LASTEXITCODE
if ($healthCheckExitCode -ne 0) {
    $healthDetails = ($healthCheck | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    $serverLog = Join-Path $rootPath 'data\logs\server.log'
    if (Test-Path -LiteralPath $serverLog) {
        $logDetails = (Get-Content -LiteralPath $serverLog -Tail 20) -join [Environment]::NewLine
        throw "Server SIMON tidak lulus health check HTTPS. Detail: $healthDetails`nLog terakhir ($serverLog):`n$logDetails"
    }
    throw "Server SIMON tidak lulus health check HTTPS. Detail: $healthDetails`nLog belum tersedia: $serverLog"
}
Write-Host "HTTPS backend health check OK: HTTP $($healthCheck | Select-Object -Last 1)"

Write-Host 'SIMON siap: https://172.18.123.92:8443'
if (-not $certificateTrustInstalled) {
    Write-Host "Perhatian: CA publik belum dipercaya Windows. Impor '$certificatePath' ke Local Computer > Trusted Root Certification Authorities untuk menghilangkan peringatan browser pada PC server."
}
Write-Host 'Matikan sleep pada PC server. Log: data\logs\server.log'
Write-Host 'Jalankan make-agent-package.bat setelah binary agent tersedia.'
