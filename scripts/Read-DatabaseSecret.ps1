param([Parameter(Mandatory=$true)][string]$SecretPath)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$encrypted=(Get-Content -LiteralPath $SecretPath -Raw).Trim()
if([string]::IsNullOrWhiteSpace($encrypted)){throw 'Encrypted database settings file is empty. Run Configure-Database.cmd again.'}
$secure=ConvertTo-SecureString -String $encrypted
$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { [Console]::Out.Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
