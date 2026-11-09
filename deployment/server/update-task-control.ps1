param([ValidateSet('Get','Set','Stop','Start')][string]$Operation,[string]$Python,[string]$Root,[string]$Arguments)
$ErrorActionPreference='Stop'
switch($Operation){
 'Get' {
  $task=Get-ScheduledTask -TaskName 'SIMONServer' -ErrorAction Stop
  $action=$task.Actions | Select-Object -First 1
  @{python=$action.Execute;root=$action.WorkingDirectory;arguments=$action.Arguments} | ConvertTo-Json -Compress
 }
 'Set' {
  if(-not (Test-Path -LiteralPath $Python -PathType Leaf)){throw 'Python versi server tidak ditemukan'}
  if(-not (Test-Path -LiteralPath $Root -PathType Container)){throw 'Folder versi server tidak ditemukan'}
  $action=New-ScheduledTaskAction -Execute $Python -Argument $Arguments -WorkingDirectory $Root
  Set-ScheduledTask -TaskName 'SIMONServer' -Action $action | Out-Null
 }
 'Stop' {
  if((Get-ScheduledTask -TaskName 'SIMONServer' -ErrorAction Stop).State -notin @('Running','Queued')){return}
  Stop-ScheduledTask -TaskName 'SIMONServer' -ErrorAction Stop
  for($attempt=0;$attempt -lt 30;$attempt++){
   if((Get-ScheduledTask -TaskName 'SIMONServer').State -notin @('Running','Queued')){return}
   Start-Sleep -Seconds 1
  }
  throw 'Task server belum berhenti; database belum boleh diubah.'
 }
 'Start' {Start-ScheduledTask -TaskName 'SIMONServer' -ErrorAction Stop}
}
