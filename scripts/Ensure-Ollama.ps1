$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$config=Get-Content (Join-Path $root 'config\appsettings.json') -Raw | ConvertFrom-Json
function Test-Ollama {try {$null=Invoke-RestMethod ($config.OllamaUrl+'/api/tags') -TimeoutSec 3;return $true}catch{return $false}}
if(!(Test-Ollama)) {
 $exe=(Get-Command ollama -ErrorAction Stop).Source
 Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Minimized
 for($i=0;$i -lt 20;$i++){if(Test-Ollama){break};Start-Sleep -Seconds 1}
 if(!(Test-Ollama)){throw 'Ollama did not become ready. Run ollama serve in CMD and inspect its error.'}
}
Write-Host 'Ollama ready. Existing workloads were not stopped or reconfigured.'
