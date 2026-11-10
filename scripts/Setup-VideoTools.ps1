$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$destination=Join-Path $root 'tools\ffmpeg'
if(Get-Command ffmpeg -ErrorAction SilentlyContinue){Write-Host 'ffmpeg already on PATH. No installation needed.';exit 0}
# Gyan Windows builds are linked from ffmpeg.org/download.html. Download only; no installer is executed.
$url='https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
$archive=Join-Path $env:TEMP ('td-ffmpeg-'+[guid]::NewGuid().ToString()+'.zip')
Write-Host 'Downloading Windows ffmpeg ZIP from gyan.dev (FFmpeg-listed build provider)...'
Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $archive
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $destination -Force
$exe=Get-ChildItem -LiteralPath $destination -Recurse -Filter ffmpeg.exe | Select-Object -First 1
if(!$exe){throw 'Download contained no ffmpeg.exe'}
$configPath=Join-Path $root 'config\appsettings.json'
$config=Get-Content $configPath -Raw | ConvertFrom-Json
$config|Add-Member -Force -NotePropertyName FFmpegExecutable -NotePropertyValue $exe.FullName
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $configPath -Encoding UTF8
Remove-Item -LiteralPath $archive
Write-Host 'Video tools configured. No system PATH or other applications were modified.'
