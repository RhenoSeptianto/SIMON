param([string]$Server='https://172.18.123.92:8443',[string]$StoreCode='')
$ErrorActionPreference='Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Klik kanan install.bat > Run as administrator' }
function Invoke-AgentAcl {
    param([string[]]$AclArguments)
    & icacls.exe @AclArguments | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Gagal mengatur permission agent. Jalankan installer sebagai Administrator.' }
}

function Restore-AgentSetupAccess {
    param([string]$Folder,[string]$SetupUserSid)
    Invoke-AgentAcl -AclArguments @($Folder,'/grant:r',"*${SetupUserSid}:(OI)(CI)F",'/T','/Q')
    foreach ($file in @(Get-ChildItem -LiteralPath $Folder -File -Force -Recurse -ErrorAction Stop)) {
        # Repair files left inaccessible by older installers before overwriting CA/config.
        Invoke-AgentAcl -AclArguments @($file.FullName,'/grant:r',"*${SetupUserSid}:F",'/Q')
    }
}

function Protect-AgentData {
    param([string]$Folder,[string]$SetupUserSid)
    $targets=@(Get-ChildItem -LiteralPath $Folder -Force -Recurse -ErrorAction Stop | Sort-Object { $_.FullName.Length } -Descending)
    $targets+=Get-Item -LiteralPath $Folder -Force
    foreach ($target in $targets) {
        $rights=if($target.PSIsContainer){'(OI)(CI)F'}else{'F'}
        $aclArguments=@($target.FullName,'/inheritance:r','/grant:r',"*S-1-5-18:$rights","*S-1-5-32-544:$rights")
        if($SetupUserSid -notin @('S-1-5-18','S-1-5-32-544')) { $aclArguments+=@('/remove:g',"*$SetupUserSid") }
        $aclArguments+='/Q'
        Invoke-AgentAcl -AclArguments $aclArguments
    }
}

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
$setupSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
try {
    foreach ($folder in @($configDir,$stateDir)) { Restore-AgentSetupAccess -Folder $folder -SetupUserSid $setupSid }
    $configPath=Join-Path $configDir 'config.json'
    $previousCode=''
    if(Test-Path -LiteralPath $configPath) { $previousCode=(Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json).store_code }
    if(-not $StoreCode) {
        $prompt=if($previousCode){"Kode store (Enter untuk tetap $previousCode)"}else{'Masukkan kode store'}
        $StoreCode=Read-Host $prompt
        if(-not $StoreCode -and $previousCode) { $StoreCode=$previousCode }
    }
    $StoreCode=$StoreCode.Trim()
    if(-not $StoreCode -or $StoreCode.Length -gt 40) { throw 'Kode store wajib diisi, maksimal 40 karakter. Jalankan installer lagi.' }
    Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse -Force
    Copy-Item -LiteralPath $ca -Destination (Join-Path $configDir 'ca.crt') -Force
    @{server=$Server.TrimEnd('/');ca_file=(Join-Path $configDir 'ca.crt');state=$stateDir;store_code=$StoreCode;sentinel_xml=(Join-Path $env:ProgramFiles 'SIMON\HDSentinel.xml')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $configDir 'config.json') -Encoding UTF8
} finally {
    foreach ($folder in @($configDir,$stateDir)) { Protect-AgentData -Folder $folder -SetupUserSid $setupSid }
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
Write-Host "Kode store: $StoreCode"
Write-Host "Sumber disk: $env:ProgramFiles\SIMON\HDSentinel.xml"
Write-Host "Log: $stateDir\agent.log"
