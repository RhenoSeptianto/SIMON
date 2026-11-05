param([string]$Server='https://172.18.123.92:8443')
$ErrorActionPreference='Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Klik kanan install.bat > Run as administrator' }
$uri=[Uri]$Server
if ($uri.Scheme -ne 'https' -or -not $uri.Host) { throw 'Server harus berupa URL HTTPS' }
$source=Join-Path $PSScriptRoot 'SIMONAgent'
$ca=Join-Path $PSScriptRoot 'ca.crt'
if (-not (Test-Path -LiteralPath (Join-Path $source 'SIMONAgent.exe'))) { throw 'Paket binary SIMONAgent tidak lengkap. Jangan memindahkan hanya file exe.' }
if (-not (Test-Path -LiteralPath $ca)) { throw 'ca.crt belum ada. Buat paket agent dari PC server lewat make-agent-package.bat.' }
$destination=Join-Path $env:ProgramFiles 'SIMON\Agent'
$configDir=Join-Path $env:ProgramData 'SIMON'
$stateDir=Join-Path $env:ProgramData 'SIAMS'
$exe=Join-Path $destination 'SIMONAgent.exe'
$binaryPath='"{0}" --service' -f $exe
$existing=Get-CimInstance Win32_Service -Filter "Name='SIMONAgent'"
if ($existing -and $existing.PathName -ne $binaryPath) { throw 'Service SIMONAgent sudah ada dengan path berbeda. Periksa service sebelum update.' }
if ($existing) {
    Stop-Service -Name SIMONAgent -ErrorAction Stop
    (Get-Service SIMONAgent).WaitForStatus('Stopped',[TimeSpan]::FromSeconds(30))
}
New-Item -ItemType Directory -Force -Path $destination,$configDir,$stateDir | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse -Force
Copy-Item -LiteralPath $ca -Destination (Join-Path $configDir 'ca.crt') -Force
@{server=$Server.TrimEnd('/');ca_file=(Join-Path $configDir 'ca.crt');state=$stateDir} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $configDir 'config.json') -Encoding UTF8
foreach ($folder in @($configDir,$stateDir)) {
    & icacls.exe $folder /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T /Q | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Gagal mengatur permission state/config' }
}
if (-not $existing) { New-Service -Name SIMONAgent -BinaryPathName $binaryPath -DisplayName 'SIMON Hardware Agent' -StartupType Automatic -Description 'Read-only hardware monitoring. Outbound HTTPS only.' | Out-Null }
& sc.exe config SIMONAgent start= auto | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Gagal mengatur automatic startup' }
& sc.exe failure SIMONAgent reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Gagal mengatur service recovery' }
& sc.exe failureflag SIMONAgent 1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Gagal mengatur recovery flag' }
Start-Service SIMONAgent
Write-Host 'SIMONAgent terpasang. Otomatis berjalan saat Windows dinyalakan, tanpa login.'
Write-Host "Server: $Server"
Write-Host "Log: $stateDir\agent.log"
