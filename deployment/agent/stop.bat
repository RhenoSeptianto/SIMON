@echo off
powershell.exe -NoProfile -Command "Stop-Service SIMONAgent; Get-Service SIMONAgent"
pause
