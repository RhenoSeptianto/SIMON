param([string]$Server='https://172.18.123.92:8443',[string]$StoreCode='')
$ErrorActionPreference='Stop'
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

$installLog=Join-Path $PSScriptRoot 'install.log'
Start-Transcript -LiteralPath $installLog -Append -ErrorAction Stop | Out-Null
$stage='Validasi paket'
try {
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Klik kanan install.bat > Run as administrator' }
$uri=[Uri]$Server
if ($uri.Scheme -ne 'https' -or -not $uri.Host) { throw 'Server harus berupa URL HTTPS' }
$source=Join-Path $PSScriptRoot 'SIMONAgent'
$ca=Join-Path $PSScriptRoot 'ca.crt'
if (-not (Test-Path -LiteralPath (Join-Path $source 'SIMONAgent.exe'))) { throw 'EXE tidak ditemukan. Paket tidak lengkap atau file dikarantina. Periksa riwayat antivirus.' }
if (-not (Test-Path -LiteralPath $ca)) { throw 'ca.crt belum ada. Buat paket agent dari PC server lewat make-agent-package.bat.' }
$destination=$source
$configDir=$source
$stateDir=Join-Path $source 'data'
$exe=Join-Path $destination 'SIMONAgent.exe'
$binaryPath='"{0}" --service' -f $exe
$stage='Memeriksa dan menghentikan service lama'
$existing=Get-CimInstance Win32_Service -Filter "Name='SIMONAgent'"
$legacyPath='"{0}" --service' -f (Join-Path $env:ProgramFiles 'SIMON\Agent\SIMONAgent.exe')
if ($existing -and $existing.PathName -ne $binaryPath -and $existing.PathName -ne $legacyPath) { throw 'Service SIMONAgent sudah ada dengan path berbeda. Periksa service sebelum update.' }
if ($existing -and (Get-Service SIMONAgent).Status -ne 'Stopped') {
    Stop-Service -Name SIMONAgent -ErrorAction Stop
    (Get-Service SIMONAgent).WaitForStatus('Stopped',[TimeSpan]::FromSeconds(30))
}
$stage='Menyiapkan folder dan mempertahankan identitas'
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
$setupSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
try {
    Restore-AgentSetupAccess -Folder $source -SetupUserSid $setupSid
    $legacyState=Join-Path $env:ProgramData 'SIAMS'
    if (-not (Test-Path -LiteralPath (Join-Path $stateDir 'identity.json')) -and (Test-Path -LiteralPath (Join-Path $legacyState 'identity.json'))) {
        Copy-Item -Path (Join-Path $legacyState '*') -Destination $stateDir -Recurse -Force
        Write-Host 'Identitas dan antrean lama disalin; data lama tidak dihapus.'
    }
    $configPath=Join-Path $configDir 'config.json'
    $previousCode=''
    $legacyConfig=Join-Path $env:ProgramData 'SIMON\config.json'
    if (-not (Test-Path -LiteralPath $configPath) -and (Test-Path -LiteralPath $legacyConfig)) { Copy-Item -LiteralPath $legacyConfig -Destination $configPath }
    if(Test-Path -LiteralPath $configPath) { $previousCode=(Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json).store_code }
    if(-not $StoreCode) {
        $prompt=if($previousCode){"Kode store (Enter untuk tetap $previousCode)"}else{'Masukkan kode store'}
        $StoreCode=Read-Host $prompt
        if(-not $StoreCode -and $previousCode) { $StoreCode=$previousCode }
    }
    $StoreCode=$StoreCode.Trim()
    if(-not $StoreCode -or $StoreCode.Length -gt 40) { throw 'Kode store wajib diisi, maksimal 40 karakter. Jalankan installer lagi.' }
    Copy-Item -LiteralPath $ca -Destination (Join-Path $configDir 'ca.crt') -Force
    @{server=$Server.TrimEnd('/');ca_file='ca.crt';state='data';store_code=$StoreCode;sentinel_xml='HDSentinel.xml'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $configDir 'config.json') -Encoding UTF8
    $xmlPath=Join-Path $source 'HDSentinel.xml'
    if (-not (Test-Path -LiteralPath $xmlPath)) { [IO.File]::WriteAllText($xmlPath,'') }
} finally {
    Protect-AgentData -Folder $source -SetupUserSid $setupSid
    Invoke-AgentAcl -AclArguments @($source,'/grant:r','*S-1-5-32-545:(OI)(CI)RX','/Q')
    if (Test-Path -LiteralPath (Join-Path $source 'HDSentinel.xml')) { Invoke-AgentAcl -AclArguments @((Join-Path $source 'HDSentinel.xml'),'/grant:r','*S-1-5-32-545:M','/Q') }
}
$stage='Memeriksa EXE dan koneksi HTTPS'
# A network failure does not prevent installation: the agent retries while offline.
& $exe --config (Join-Path $source 'config.json') --check-connection | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host 'PERINGATAN: pemeriksaan EXE/HTTPS gagal. Jalankan check-agent.bat untuk rincian. Agent tetap mencoba saat jaringan pulih.' }
$stage='Mendaftarkan service'
if (-not $existing) { New-Service -Name SIMONAgent -BinaryPathName $binaryPath -DisplayName 'SIMON Hardware Agent' -StartupType Automatic -Description 'Read-only hardware monitoring. Outbound HTTPS only.' | Out-Null }
if ($existing) {
    & sc.exe config SIMONAgent binPath= $binaryPath | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Gagal memperbarui lokasi service' }
}
& sc.exe config SIMONAgent start= auto | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Gagal mengatur automatic startup' }
& sc.exe failure SIMONAgent reset= 86400 actions= restart/60000/restart/60000/restart/60000 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Gagal mengatur service recovery' }
& sc.exe failureflag SIMONAgent 1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Gagal mengatur recovery flag' }
$stage='Menjalankan service'
Start-Service SIMONAgent
Start-Sleep -Seconds 3
if ((Get-Service SIMONAgent).Status -ne 'Running') { throw 'Service berhenti. Periksa check-agent.bat.' }
Write-Host 'SIMONAgent terpasang. Otomatis berjalan saat Windows dinyalakan, tanpa login.'
Write-Host "Server: $Server"
Write-Host "Kode store: $StoreCode"
Write-Host "Sumber disk: $source\HDSentinel.xml"
Write-Host "Folder permanen: $source (jangan dipindahkan)"
Write-Host "Log: $stateDir\agent.log"

Write-Host 'Untuk pemeriksaan masalah, jalankan check-agent.bat sebagai Administrator.'
} catch {
    Write-Host "GAGAL pada tahap: $stage" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Access denied bisa berasal dari izin Windows atau kebijakan keamanan. Periksa check-agent.bat dan riwayat Sangfor; belum tentu antivirus.'
    throw
} finally {
    Stop-Transcript | Out-Null
    Write-Host "Log instalasi: $installLog"
}
