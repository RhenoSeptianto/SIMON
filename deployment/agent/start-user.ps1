$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'SIMONAgent\SIMONAgent.exe') --background --config (Join-Path $PSScriptRoot 'config.json')
if($LASTEXITCODE -ne 0){throw 'Agent gagal. Lihat startup.log.'}
