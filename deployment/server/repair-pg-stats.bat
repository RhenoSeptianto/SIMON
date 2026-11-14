@echo off
setlocal
cd /d "%~dp0..\.."
echo === SIMONADO: Perbaikan Statistik PostgreSQL (pg_statistic) ===
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$urlFile = 'data\database-url.txt'; " ^
  "if (-not (Test-Path $urlFile)) { Write-Error 'File data\database-url.txt tidak ditemukan.'; exit 1 }; " ^
  "$dbName = ((Get-Content $urlFile -Raw).Trim() -split '/')[-1].Split('?')[0]; " ^
  "$psql = (Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' | Select-Object -First 1).FullName; " ^
  "if (-not $psql) { Write-Error 'psql.exe tidak ditemukan di C:\Program Files\PostgreSQL.'; exit 1 }; " ^
  "Write-Host ('Database: ' + $dbName); " ^
  "& $psql -U postgres -d $dbName -c 'REINDEX TABLE pg_toast.pg_toast_2619;' -c 'REINDEX TABLE pg_statistic;' -c 'ANALYZE;'; " ^
  "if ($LASTEXITCODE -ne 0) { " ^
  "  Write-Host 'REINDEX gagal, menjalankan pembersihan statistik planner...'; " ^
  "  & $psql -U postgres -d $dbName -c 'DELETE FROM pg_statistic;' -c 'VACUUM FULL pg_statistic;' -c 'ANALYZE;' " ^
  "}"
pause
