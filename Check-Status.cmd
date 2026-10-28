@echo off
cd /d "%~dp0"
dotnet run --project src\TD.Poc.Console\TD.Poc.Console.csproj --configuration Release --no-build -- --status
if errorlevel 1 echo FAILED. Read the error above.
pause
