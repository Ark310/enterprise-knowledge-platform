@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Ensure-Ollama.ps1"
if errorlevel 1 (pause & exit /b 1)
dotnet run --project src\TD.Poc.Launcher\TD.Poc.Launcher.csproj --configuration Release --no-build -- --cli
if errorlevel 1 echo FAILED. Run Setup-POC.cmd if needed.
pause
