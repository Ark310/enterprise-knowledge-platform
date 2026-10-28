@echo off
cd /d "%~dp0"
dotnet run --project src\TD.Poc.Console\TD.Poc.Console.csproj --configuration Release -- --migrate
if errorlevel 1 echo FAILED. Read the error above.
pause
