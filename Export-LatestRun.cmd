@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Export-LatestRun.ps1"
if errorlevel 1 echo Export failed. See message above.
pause
