@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-server.ps1"
if errorlevel 1 echo Setup gagal. Baca pesan di atas.
pause
