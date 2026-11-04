@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Ensure-Ollama.ps1"
if errorlevel 1 (pause & exit /b 1)
dotnet run --project src\TD.Poc.Launcher\TD.Poc.Launcher.csproj --configuration Release --no-build --
if errorlevel 1 echo FAILED. Read the error above. Run Setup-POC.cmd if the application has not been built.
pause
