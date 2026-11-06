@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-user.ps1"
set "SIMON_INSTALL_EXIT=%errorlevel%"
if not "%SIMON_INSTALL_EXIT%"=="0" echo Instalasi gagal. Lihat %%LOCALAPPDATA%%\SIMON\install-user.log dan pesan di atas.
pause
exit /b %SIMON_INSTALL_EXIT%
