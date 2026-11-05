@echo off
cd /d "%~dp0.."
if not exist .venv-build\Scripts\python.exe py -3.12 -m venv .venv-build
if errorlevel 1 goto failed
.venv-build\Scripts\python.exe -m pip install -r tools\requirements-build.txt
if errorlevel 1 goto failed
.venv-build\Scripts\python.exe -m tools.build_agent
if errorlevel 1 goto failed
echo Agent template selesai di release\SIMONAgent-template.zip
pause
exit /b 0
:failed
echo Build gagal.
pause
exit /b 1
