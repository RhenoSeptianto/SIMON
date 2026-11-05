@echo off
cd /d "%~dp0..\.."
.venv\Scripts\python.exe -m tools.make_agent_package
if errorlevel 1 echo Pembuatan paket gagal. Baca pesan di atas.
pause
