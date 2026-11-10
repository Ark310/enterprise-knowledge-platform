@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Export-ImportDiagnostics.ps1"
if errorlevel 1 echo FAILED. Read the error above.
pause
