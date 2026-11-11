@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0migrate-postgresql.ps1"
if errorlevel 1 echo Migrasi gagal. Database SQLite lama tidak dihapus.
pause
