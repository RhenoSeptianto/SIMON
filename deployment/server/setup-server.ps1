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

    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code: $LASTEXITCODE)"
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

$pythonLauncherPath = Resolve-PythonLauncher
if (-not $pythonLauncherPath) {
    $winget = Get-Command 'winget.exe' -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw 'Python 3.12 x64 belum terpasang dan winget tidak tersedia untuk instalasi otomatis. Instal "App Installer" dari Microsoft Store, lalu jalankan setup lagi, atau instal Python 3.12 x64 dari https://www.python.org/downloads/windows/.'
    }

    Write-Host 'Python belum ditemukan. Menginstal Python 3.12 x64 untuk semua pengguna lewat winget...'
    Invoke-Checked -Exe $winget.Source -Arguments @(
        'install', '--id', 'Python.Python.3.12', '--exact', '--scope', 'machine',
        '--silent', '--accept-package-agreements', '--accept-source-agreements'
    ) -FailureMessage 'Instalasi otomatis Python 3.12 x64 gagal. Pastikan PC terhubung ke internet dan winget/App Installer tersedia; kemudian instal Python 3.12 x64 manual dari https://www.python.org/downloads/windows/.'

    Refresh-ProcessPath
    $pythonLauncherPath = Resolve-PythonLauncher
    if (-not $pythonLauncherPath) {
        throw 'Python berhasil dipasang, tetapi Python Launcher (py.exe) belum dapat ditemukan. Buka terminal baru lalu jalankan setup lagi; jika masih gagal, instal Python 3.12 x64 dengan opsi Python Launcher dari https://www.python.org/downloads/windows/.'
    }
}

$pythonInfo = & $pythonLauncherPath '-3.12-64' '-c' 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.maxsize > 2**32, sep=chr(124))' 2>&1
$pythonCheckExitCode = $LASTEXITCODE
$pythonInfoLine = ''
if ($pythonInfo) { $pythonInfoLine = ($pythonInfo | Select-Object -Last 1).ToString().Trim() }
if ($pythonCheckExitCode -ne 0 -or $pythonInfoLine -ne '3|12|True') {
    $detectedPython = ($pythonInfo | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    throw "Python 3.12 x64 wajib tersedia. Tidak dapat memvalidasinya melalui Python Launcher -3.12-64. Detail: $detectedPython`nInstal Python 3.12 x64 dari https://www.python.org/downloads/windows/ dan pastikan Python Launcher terpasang, lalu jalankan setup kembali."
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
$listeners = Get-NetTCPConnection -LocalPort 8443 -State Listen -ErrorAction Stop
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
Invoke-Checked -Exe $venvPythonPath -Arguments @('-m', 'tools.server_setup') -FailureMessage 'Setup konfigurasi SIMON gagal. Periksa error TLS/database di atas.'

$backendCheckCode = 'from backend.main import app; assert app.title; print(app.title)'
$backendCheck = & $venvPythonPath '-c' $backendCheckCode 2>&1
$backendCheckExitCode = $LASTEXITCODE
if ($backendCheckExitCode -ne 0) {
    $backendDetails = ($backendCheck | Select-Object -Last 20 | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    throw "Validasi backend gagal saat memuat aplikasi SIMON. Pastikan dependency Python 3.12 terpasang dan database dapat dibuka. Detail:`n$backendDetails"
}
$backendCheck | ForEach-Object { Write-Host $_ }

# Restrict operational database, credentials, and TLS private keys to administrators/SYSTEM.
Invoke-Checked -Exe 'icacls.exe' -Arguments @((Join-Path $rootPath 'data'), '/inheritance:r', '/grant:r', '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F', '/T', '/Q') -FailureMessage 'Gagal mengamankan permission folder data.'

$certificatePath = Join-Path $rootPath 'data\tls\ca.crt'
if (-not (Test-Path -LiteralPath $certificatePath -PathType Leaf)) {
    throw "Sertifikat CA tidak ditemukan setelah setup: $certificatePath"
}
Import-Certificate -FilePath $certificatePath -CertStoreLocation 'Cert:\LocalMachine\Root' | Out-Null

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
Write-Host 'Matikan sleep pada PC server. Log: data\logs\server.log'
Write-Host 'Jalankan make-agent-package.bat setelah binary agent tersedia.'
