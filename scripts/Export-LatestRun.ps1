$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$latest=Get-ChildItem (Join-Path $root 'runtime\runs') -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(!$latest){throw 'No analysis run exists yet'}
$destination=Join-Path $root ('TD-review-'+$latest.Name+'.zip')
$staging=Join-Path $env:TEMP ('td-review-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $staging | Out-Null
$warnings=New-Object System.Collections.Generic.List[string]
function Snapshot([string]$source,[string]$target){
 $inputStream=$null;$outputStream=$null
 try {
  New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent)|Out-Null
  # Read sharing permits export while the host is appending live logs.
  $inputStream=[IO.File]::Open($source,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
  $outputStream=[IO.File]::Create($target)
  # Bound the snapshot to the length observed at open, rather than following a growing file.
  $remaining=$inputStream.Length;$buffer=New-Object byte[] 65536
  while($remaining -gt 0){$n=$inputStream.Read($buffer,0,[int][Math]::Min($remaining,$buffer.Length));if($n -eq 0){break};$outputStream.Write($buffer,0,$n);$remaining-=$n}
 } catch {$warnings.Add(('Could not snapshot '+[IO.Path]::GetFileName($source)+': '+$_.Exception.Message))}
 finally{if($inputStream){$inputStream.Dispose()};if($outputStream){$outputStream.Dispose()}}
}
try {
 foreach($f in Get-ChildItem -LiteralPath $latest.FullName -Recurse -File){
  $relative=$f.FullName.Substring($latest.FullName.Length).TrimStart('\')
  Snapshot $f.FullName (Join-Path $staging $relative)
 }
 $workflow=Join-Path $root 'runtime\workflow.log'
 if(Test-Path $workflow){Snapshot $workflow (Join-Path $staging 'host-workflow.log')}
 @{run=$latest.Name;captured_at=(Get-Date).ToString('o');note='Best-effort snapshot; files can change during an active run. No credentials or Codex login files included.';warnings=@($warnings.ToArray())}|ConvertTo-Json -Depth 5|Set-Content (Join-Path $staging 'export-snapshot.json') -Encoding UTF8
 Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $destination -Force
 Write-Host ('Review bundle: '+$destination)
 foreach($warning in $warnings){Write-Warning $warning}
 Write-Host 'Contains source excerpts and sampled frames. Share only with authorised reviewers.'
}finally{Remove-Item -LiteralPath $staging -Recurse -Force}
