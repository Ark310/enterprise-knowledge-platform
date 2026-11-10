$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$parent=Join-Path $root 'runtime\knowledge-runs'
if(!(Test-Path -LiteralPath $parent)){throw 'No knowledge retrieval run exists yet.'}
$latest=Get-ChildItem -LiteralPath $parent -Directory|Sort-Object Name -Descending|Select-Object -First 1
if(!$latest){throw 'No knowledge retrieval run exists yet.'}
$destination=Join-Path $root ('TD-knowledge-'+$latest.Name+'.zip')
$staging=Join-Path $env:TEMP ('td-knowledge-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $staging|Out-Null
$warnings=New-Object System.Collections.Generic.List[string]
try{
 foreach($f in Get-ChildItem -LiteralPath $latest.FullName -Recurse -File){
  $source=$null;$target=$null
  try{
   $relative=$f.FullName.Substring($latest.FullName.Length).TrimStart('\')
   $out=Join-Path $staging $relative
   New-Item -ItemType Directory -Force -Path (Split-Path $out -Parent)|Out-Null
   $source=[IO.File]::Open($f.FullName,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
   $target=[IO.File]::Create($out);$remaining=$source.Length;$buffer=New-Object byte[] 65536
   while($remaining -gt 0){$n=$source.Read($buffer,0,[int][Math]::Min($remaining,$buffer.Length));if($n -eq 0){break};$target.Write($buffer,0,$n);$remaining-=$n}
  }catch{$warnings.Add('Could not snapshot '+$f.Name)}
  finally{if($source){$source.Dispose()};if($target){$target.Dispose()}}
 }
 @{run=$latest.Name;captured_at=(Get-Date).ToString('o');warnings=@($warnings.ToArray());note='Only this question run; no database credentials or Codex login files. Live files are best-effort snapshots.'}|ConvertTo-Json -Depth 5|Set-Content (Join-Path $staging 'export-snapshot.json') -Encoding UTF8
 Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $destination -Force
 Write-Host ('Retrieval export: '+$destination)
 foreach($w in $warnings){Write-Warning $w}
}finally{Remove-Item -LiteralPath $staging -Recurse -Force}
