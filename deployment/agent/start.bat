@echo off
powershell.exe -NoProfile -Command "Start-Service SIMONAgent; Get-Service SIMONAgent"
pause
