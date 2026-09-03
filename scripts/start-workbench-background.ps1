# Background entry point for the Windows logon scheduled task.
# The watchdog remains attached to Task Scheduler and repairs managed services
# when one of the local workbench endpoints stops responding.

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WatchdogScript = Join-Path $PSScriptRoot 'workbench-watchdog.ps1'
$LogDirectory = Join-Path $ProjectRoot '.runtime'
$LogPath = Join-Path $LogDirectory 'startup.log'
$PowerShellCandidates = @(
  (Join-Path $env:LOCALAPPDATA 'Programs\PowerShell\7\pwsh.exe'),
  'C:\Program Files\PowerShell\7\pwsh.exe',
  (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe')
)
$PowerShell7 = $PowerShellCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null

try {
  Set-Location -LiteralPath $ProjectRoot
  Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ("[{0}] starting workbench watchdog" -f (Get-Date).ToString('o'))
  if (-not $PowerShell7) {
    throw 'PowerShell 7 executable was not found. Install PowerShell 7 or set a known path in this wrapper.'
  }
  & $PowerShell7 -NoProfile -ExecutionPolicy Bypass -File $WatchdogScript
  if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "workbench-watchdog.ps1 exited with code $LASTEXITCODE"
  }
  Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ("[{0}] workbench watchdog stopped" -f (Get-Date).ToString('o'))
} catch {
  Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ("[{0}] workbench watchdog failed: {1}" -f (Get-Date).ToString('o'), $_.Exception.Message)
  throw
}
