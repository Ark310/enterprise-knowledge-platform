$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$latest=Get-ChildItem (Join-Path $root 'runtime\runs') -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(!$latest){throw 'No analysis run exists yet'}
$destination=Join-Path $root ('TD-review-'+$latest.Name+'.zip')
Compress-Archive -Path (Join-Path $latest.FullName '*') -DestinationPath $destination -Force
Write-Host ('Review bundle: '+$destination)
Write-Host 'Contains source excerpts and sampled frames. Share only with authorised reviewers.'
