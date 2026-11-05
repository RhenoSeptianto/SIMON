@echo off
powershell.exe -NoProfile -Command "Get-ScheduledTask -TaskName SIMONServer | Select-Object TaskName,State; Get-ScheduledTaskInfo -TaskName SIMONServer"
pause
