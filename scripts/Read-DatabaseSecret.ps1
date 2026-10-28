param([Parameter(Mandatory=$true)][string]$SecretPath)
$ErrorActionPreference='Stop'
$secure=Get-Content -LiteralPath $SecretPath -Raw | ConvertTo-SecureString
$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { [Console]::Out.Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
