$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Set-Location $root
function Step([string]$name,[string]$script){
 Write-Host ('--- '+$name+' ---')
 & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot $script)
 if($LASTEXITCODE -ne 0){throw ($name+' failed. Fix the error above and rerun Setup-POC.cmd.')}
}
Write-Host 'TD POC v0.15 setup. Existing PostgreSQL sources, vectors and reviews are preserved.'
Write-Host 'Requires installed Python 3.11+, .NET 10 SDK, Ollama, Codex, PostgreSQL and the approved schema.'
$configPath=Join-Path $root 'config\appsettings.json'
$config=Get-Content -LiteralPath $configPath -Raw|ConvertFrom-Json
$dataRoot=Read-Host ('Data folder ['+$config.DataRoot+']')
if($dataRoot){$config.DataRoot=$dataRoot}
if(!(Test-Path -LiteralPath (Join-Path $config.DataRoot 'current-state') -PathType Container)){throw 'Data folder must contain current-state. No source folders were modified.'}
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $configPath -Encoding UTF8
Step 'Local dependencies, embedding model and build' 'Setup-LocalModel.ps1'
Step 'Database connection (hidden password)' 'Configure-Database.ps1'
& dotnet run --project src\TD.Poc.Console\TD.Poc.Console.csproj --configuration Release --no-build -- --migrate
if($LASTEXITCODE -ne 0){throw 'Database initialization failed. Existing approved tables must already be installed; do not reset the database.'}
Step 'Video tools' 'Setup-VideoTools.ps1'
# A dedicated home prevents unrelated personal MCP servers being loaded by the POC.
# Never copy auth/config from another Codex home; complete this POC login once.
$oldCodexHome=$env:CODEX_HOME
try {
 $env:CODEX_HOME=Join-Path $root 'config\codex-home'
 New-Item -ItemType Directory -Force -Path $env:CODEX_HOME|Out-Null
 # Restrict this credential directory to the current Windows user and SYSTEM.
 $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 & icacls.exe $env:CODEX_HOME /inheritance:r /grant:r ('*'+$sid+':(OI)(CI)F') '*S-1-5-18:(OI)(CI)F' /T /Q | Out-Null
 if($LASTEXITCODE -ne 0){throw 'Could not restrict the POC credential folder permissions.'}
 $previousPreference=$ErrorActionPreference
 $ErrorActionPreference='Continue'
 & codex login status 2>&1 | ForEach-Object {Write-Host $_}
 $loginCode=$LASTEXITCODE
 $ErrorActionPreference=$previousPreference
 if($loginCode -ne 0){
  Write-Host 'Sign in to ChatGPT for this isolated POC. This does not configure an API key.'
  & codex login
  if($LASTEXITCODE -ne 0){throw 'Codex login did not finish. Rerun Setup-POC.cmd.'}
 }
}finally{$env:CODEX_HOME=$oldCodexHome}
& dotnet run --project src\TD.Poc.Console\TD.Poc.Console.csproj --configuration Release --no-build -- --preflight
if($LASTEXITCODE -ne 0){throw 'POC readiness check failed. See the activity window and runtime logs.'}
Write-Host 'SETUP PASSED. Run Start-POC.cmd. Startup scans only; /process manually imports and embeds.'
