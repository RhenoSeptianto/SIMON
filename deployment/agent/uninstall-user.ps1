$ErrorActionPreference='Stop'
$link=Join-Path ([Environment]::GetFolderPath('Startup')) 'SIMON Agent.lnk'
if(Test-Path -LiteralPath $link){Remove-Item -LiteralPath $link}
Write-Host 'Startup SIMON untuk user ini dihapus. Agent yang sedang berjalan tidak dihentikan; logout untuk menghentikannya. Identitas dan konfigurasi dipertahankan.'
