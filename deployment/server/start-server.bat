@echo off
cd /d "%~dp0..\.."
.venv\Scripts\python.exe -m backend.run_server
pause
