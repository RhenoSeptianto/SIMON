@echo off
powershell.exe -NoProfile -Command "Get-Service SIMONAgent | Select-Object Name,Status,StartType; if (Test-Path -LiteralPath (Join-Path $env:ProgramData 'SIAMS\agent.log')) { Get-Content -LiteralPath (Join-Path $env:ProgramData 'SIAMS\agent.log') -Tail 15 }"
pause
