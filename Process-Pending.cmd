@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Ensure-Ollama.ps1"
if errorlevel 1 (pause & exit /b 1)
dotnet run --project src\TD.Poc.Console\TD.Poc.Console.csproj --configuration Release -- --process
if errorlevel 1 echo FAILED. Read the error above.
pause
