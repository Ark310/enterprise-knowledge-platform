param([Parameter(Mandatory=$true)][string]$Prefix)
$ErrorActionPreference='Stop'
$Host.UI.RawUI.WindowTitle='TD Agent Activity - '+(Split-Path $Prefix -Leaf)
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class TDConsoleMode {
 [DllImport("kernel32.dll")] static extern IntPtr GetStdHandle(int h);
 [DllImport("kernel32.dll")] static extern bool GetConsoleMode(IntPtr h,out uint m);
 [DllImport("kernel32.dll")] static extern bool SetConsoleMode(IntPtr h,uint m);
 public static void DisableQuickEdit(){uint m;var h=GetStdHandle(-10);if(GetConsoleMode(h,out m))SetConsoleMode(h,(m|0x80u)&~0x40u);}
}
'@
[TDConsoleMode]::DisableQuickEdit()
Write-Host 'Read-only activity viewer. Q requests cancellation of THIS agent. Closing this viewer does not stop it.'
Write-Host 'Private internal reasoning is not displayed. Events and elapsed time are execution status.'
$stream=[System.IO.File]::Open($Prefix+'-activity.log',[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::ReadWrite)
$reader=New-Object System.IO.StreamReader($stream)
try {
 while($true) {
  while(($line=$reader.ReadLine()) -ne $null){Write-Host $line}
  if([Console]::KeyAvailable){$key=[Console]::ReadKey($true);if($key.Key -eq 'Q'){Set-Content -LiteralPath ($Prefix+'.cancel') -Value 'operator requested cancellation';Write-Host 'Cancellation requested; waiting for host acknowledgement...'}}
  $statusPath=$Prefix+'-status.json'
  if(Test-Path -LiteralPath $statusPath){
   try{$s=Get-Content -LiteralPath $statusPath -Raw|ConvertFrom-Json}catch{$s=$null}
   if($s -and $s.state -ne 'RUNNING'){
    while(($line=$reader.ReadLine()) -ne $null){Write-Host $line}
    Write-Host ('Final execution status: '+$s.state+'. Return to the main window for validation and database-save results.')
    break
   }
  }
  Start-Sleep -Milliseconds 300
 }
}finally{$reader.Dispose()}
Read-Host 'Press Enter to close this activity window' | Out-Null
