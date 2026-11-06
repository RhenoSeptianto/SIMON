param([string]$StoreCode='')
$ErrorActionPreference='Stop'
$exe=Join-Path $PSScriptRoot 'SIMONAgent\SIMONAgent.exe'
if($StoreCode){& $exe --install-user --store-code $StoreCode}else{& $exe --install-user}
if($LASTEXITCODE -ne 0){throw 'Installer EXE gagal. Lihat install-user.log.'}
