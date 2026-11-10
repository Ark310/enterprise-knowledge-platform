param([Parameter(Mandatory=$true)][string]$Prefix,[long]$StartByte=0)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$Host.UI.RawUI.WindowTitle='TD '+(Split-Path $Prefix -Leaf)+' activity'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class TDRoleConsole {
 [DllImport("kernel32.dll")] static extern IntPtr GetStdHandle(int h);
 [DllImport("kernel32.dll")] static extern bool GetConsoleMode(IntPtr h,out uint m);
 [DllImport("kernel32.dll")] static extern bool SetConsoleMode(IntPtr h,uint m);
 public static void Configure(){uint m;var h=GetStdHandle(-10);if(GetConsoleMode(h,out m))SetConsoleMode(h,(m|0x80u)&~0x40u);}
}
'@
[TDRoleConsole]::Configure()
Write-Host 'One window follows this entire agent phase. Q requests cancellation. Closing this viewer does not cancel the host.'
$stream=[IO.File]::Open($Prefix+'.log',[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
$null=$stream.Seek($StartByte,[IO.SeekOrigin]::Begin)
$reader=[IO.StreamReader]::new($stream,[Text.Encoding]::UTF8,$true)
try {
 while($true){
  while(($line=$reader.ReadLine()) -ne $null){Write-Host $line}
  if([Console]::KeyAvailable){$key=[Console]::ReadKey($true);if($key.Key -eq 'Q'){[IO.File]::WriteAllText($Prefix+'.cancel','operator requested cancellation');Write-Host 'Cancellation requested...'}}
  $stateStream=$null;$stateReader=$null
  try{
   $stateStream=[IO.File]::Open($Prefix+'.status.json',[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
   $stateReader=[IO.StreamReader]::new($stateStream,[Text.Encoding]::UTF8,$true)
   $state=$stateReader.ReadToEnd()|ConvertFrom-Json
  }catch{$state=$null}finally{if($stateReader){$stateReader.Dispose()}elseif($stateStream){$stateStream.Dispose()}}
  if($state -and $state.state -ne 'RUNNING'){
   while(($line=$reader.ReadLine()) -ne $null){Write-Host $line}
   Write-Host ($state.state+': '+$state.step);break
  }
  Start-Sleep -Milliseconds 300
 }
}finally{$reader.Dispose()}
Read-Host 'Press Enter to close this completed activity window'|Out-Null
