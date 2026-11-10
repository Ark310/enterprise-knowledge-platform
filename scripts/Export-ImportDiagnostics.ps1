$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$runtime=Join-Path $root 'runtime'
$staging=Join-Path $env:TEMP ('import-diagnostics-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $staging|Out-Null
try {
 foreach($name in @('import-state.json','import-timeouts.json','import-traces')) {
  $p=Join-Path $runtime $name
  if(Test-Path -LiteralPath $p){Copy-Item -LiteralPath $p -Destination $staging -Recurse}
 }
 $workerLogs=Join-Path $runtime 'diagnostics\workers'
 if(Test-Path -LiteralPath $workerLogs){
  New-Item -ItemType Directory -Path (Join-Path $staging 'worker-errors')|Out-Null
  Get-ChildItem -LiteralPath $workerLogs -Filter '*-stderr.txt' -File|Sort-Object LastWriteTime -Descending|Select-Object -First 30|Copy-Item -Destination (Join-Path $staging 'worker-errors')
 }
 'Import diagnostics only. Credentials and login files are excluded. Internal file paths may be present.'|Set-Content (Join-Path $staging 'README.txt') -Encoding UTF8
 $destination=Join-Path $root ('TD-import-diagnostics-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.zip')
 Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $destination -Force
 Write-Host ('Import diagnostics: '+$destination)
}finally{Remove-Item -LiteralPath $staging -Recurse -Force}
