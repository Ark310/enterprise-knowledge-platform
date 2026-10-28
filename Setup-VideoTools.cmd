@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Setup-VideoTools.ps1"
if errorlevel 1 (echo FAILED. See the error above. & pause & exit /b 1)
pause
