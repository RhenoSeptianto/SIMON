$ErrorActionPreference='Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Jalankan sebagai Administrator' }
$service=Get-Service SIMONAgent -ErrorAction SilentlyContinue
if ($service) {
    if ($service.Status -ne 'Stopped') { Stop-Service SIMONAgent; $service.WaitForStatus('Stopped',[TimeSpan]::FromSeconds(30)) }
    & sc.exe delete SIMONAgent
    if ($LASTEXITCODE -ne 0) { throw 'Gagal menghapus service' }
}
Write-Host 'Service dihapus. State/UUID dan binary dipertahankan agar aman untuk reinstall.'
Write-Host 'Folder state: %PROGRAMDATA%\SIAMS. Jangan hapus jika ingin mempertahankan identitas PC.'
