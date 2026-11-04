@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Export-LatestRetrieval.ps1"
if errorlevel 1 echo EXPORT FAILED. Read the error above.
pause
