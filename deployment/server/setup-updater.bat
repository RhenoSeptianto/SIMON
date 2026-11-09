@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-updater.ps1"
if errorlevel 1 echo Pemasangan helper gagal. Baca pesan di atas.
pause
