@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Setup-POC.ps1"
if errorlevel 1 (echo SETUP FAILED. Read the error above. & pause & exit /b 1)
pause
