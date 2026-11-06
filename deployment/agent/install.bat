@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set "SIMON_INSTALL_EXIT=%errorlevel%"
if not "%SIMON_INSTALL_EXIT%"=="0" (
  echo [%date% %time%] Installer/PowerShell gagal, exit code %SIMON_INSTALL_EXIT%.>> "%~dp0install.log"
  echo Instalasi gagal. Baca install.log. Jika PowerShell diblokir, periksa kebijakan keamanan dengan tim IT.
)
pause
exit /b %SIMON_INSTALL_EXIT%
