@echo off
"%~dp0SIMONAgent\SIMONAgent.exe" --install-user
set "SIMON_INSTALL_EXIT=%errorlevel%"
if not "%SIMON_INSTALL_EXIT%"=="0" echo Instalasi gagal. Lihat "%~dp0install-user.log" dan pesan di atas.
if not "%SIMON_INSTALL_EXIT%"=="0" echo [%date% %time%] Installer EXE gagal, exit %SIMON_INSTALL_EXIT%.>> "%~dp0install-launcher.log"
pause
exit /b %SIMON_INSTALL_EXIT%
