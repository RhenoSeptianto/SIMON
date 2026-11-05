@echo off
powershell.exe -NoProfile -Command "Stop-ScheduledTask -TaskName SIMONServer"
pause
