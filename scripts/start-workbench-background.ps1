# Background entry point for the Windows logon scheduled task.
# Keep this wrapper small so the scheduled task can remain stable while the
# workbench implementation evolves in scripts/workbench.ps1.

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WorkbenchScript = Join-Path $PSScriptRoot 'workbench.ps1'
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
  Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ("[{0}] starting workbench" -f (Get-Date).ToString('o'))
  if (-not $PowerShell7) {
    throw 'PowerShell 7 executable was not found. Install PowerShell 7 or set a known path in this wrapper.'
  }
  # Use an absolute PowerShell 7 path. Scheduled tasks do not reliably inherit
  # the interactive user PATH, and Windows PowerShell cannot parse the UTF-8
  # workbench script reliably on all systems.
  & $PowerShell7 -NoProfile -ExecutionPolicy Bypass -File $WorkbenchScript start *>> $LogPath
  if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "workbench.ps1 exited with code $LASTEXITCODE"
  }
  Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ("[{0}] workbench startup completed" -f (Get-Date).ToString('o'))
} catch {
  Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ("[{0}] workbench startup failed: {1}" -f (Get-Date).ToString('o'), $_.Exception.Message)
  throw
}
