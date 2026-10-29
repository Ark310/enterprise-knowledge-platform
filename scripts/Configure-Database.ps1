$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Write-Host 'Stores the connection encrypted for THIS Windows account. Do not share database.dpapi.'
$server=Read-Host 'PostgreSQL host [localhost]'; if(!$server){$server='localhost'}
$port=Read-Host 'PostgreSQL port [5432]'; if(!$port){$port='5432'}
$user=Read-Host 'Database username [postgres for existing local POC]';if(!$user){$user='postgres'}
$password=Read-Host 'Database password (hidden)' -AsSecureString
$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
function Quote-Libpq([string]$v){return "'"+$v.Replace('\','\\').Replace("'","\'")+"'"}
try {
 $plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
 $connection='host='+(Quote-Libpq $server)+' port='+(Quote-Libpq $port)+' dbname=knowledge_poc user='+(Quote-Libpq $user)+' password='+(Quote-Libpq $plain)
 $secure=ConvertTo-SecureString $connection -AsPlainText -Force
 $secure | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $root 'config\database.dpapi') -Encoding ASCII
 Write-Host 'Database connection saved securely.'
} finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$plain=$null;$connection=$null }
