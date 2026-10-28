$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Set-Location $root
if(!(Get-Command dotnet -ErrorAction SilentlyContinue)){throw 'Install the .NET 10 SDK first.'}
if(!(Get-Command codex -ErrorAction SilentlyContinue)){throw 'Codex is not on PATH. Open a fresh terminal after installation.'}
if(!(Get-Command ollama -ErrorAction SilentlyContinue)){throw 'Ollama is not on PATH. This machine already has it installed; open a fresh terminal.'}
$python=$null
foreach($candidate in @('C:\Program Files\Python311\python.exe','python.exe','python3.exe')) {
 try {$null=& $candidate -c 'import sys; assert sys.version_info >= (3,11)' 2>$null;if($LASTEXITCODE -eq 0){$python=$candidate;break}}catch{}
}
if(!$python){throw 'Python 3.11+ not found. Install Python with its launcher/PATH option, then rerun setup.'}
& $python -m venv .venv
if($LASTEXITCODE -ne 0){throw 'Virtual environment creation failed'}
& '.\.venv\Scripts\python.exe' -m pip install -r tools\requirements.txt
if($LASTEXITCODE -ne 0){throw 'Python dependency install failed'}
& (Join-Path $PSScriptRoot 'Ensure-Ollama.ps1')
$config=Get-Content config\appsettings.json -Raw | ConvertFrom-Json
& ollama pull $config.EmbeddingModel
if($LASTEXITCODE -ne 0){throw 'Embedding model download failed'}
$body=@{model=$config.EmbeddingModel;input='TD model readiness check';truncate=$false;keep_alive='30m';options=@{num_ctx=4096;num_batch=64}}|ConvertTo-Json -Depth 5
$r=Invoke-RestMethod -Method Post -Uri ($config.OllamaUrl+'/api/embed') -ContentType 'application/json' -Body $body -TimeoutSec 600
Write-Host ('Model ready. Dimensions: '+$r.embeddings[0].Count)
& dotnet build TD.Poc.sln --configuration Release --nologo -m:1
if($LASTEXITCODE -ne 0){throw 'Solution build failed'}
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
if($LASTEXITCODE -ne 0){throw 'Offline evidence tests failed'}
Write-Host 'Setup passed. Run Configure-Database.cmd, then Initialize-Database.cmd. Existing reasoning models were not changed.'
Write-Host 'For visual frame evidence, ffmpeg must be on PATH or configured as FFmpegExecutable. Run Setup-VideoTools.cmd if needed.'
