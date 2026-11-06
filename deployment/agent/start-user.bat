@echo off
"%~dp0SIMONAgent\SIMONAgent.exe" --background --config "%~dp0config.json"
if errorlevel 1 pause
