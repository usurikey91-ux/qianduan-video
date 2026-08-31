param(
  [ValidateSet('start', 'stop', 'restart', 'status')]
  [string]$Action = 'start',
  [switch]$OpenBrowser
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $ProjectRoot '.runtime'
$StatePath = Join-Path $RuntimeDir 'processes.json'
$ConfigPath = if ($env:WORKBENCH_RUNTIME_CONFIG) { $env:WORKBENCH_RUNTIME_CONFIG } else { Join-Path $ProjectRoot 'runtime.local.json' }

function Read-RuntimeConfig {
  if (-not (Test-Path -LiteralPath $ConfigPath)) { return @{} }
  return Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
}

function Resolve-ServiceRoot([string]$ConfigValue, [string]$EnvironmentName, [string[]]$Candidates, [string]$Marker) {
  $values = @()
  if ($ConfigValue) { $values += $ConfigValue }
  $environmentValue = [Environment]::GetEnvironmentVariable($EnvironmentName)
  if ($environmentValue) { $values += $environmentValue }
  foreach ($candidate in $Candidates) { $values += (Join-Path (Split-Path -Parent $ProjectRoot) $candidate) }
  foreach ($value in $values) {
    try { $resolved = [IO.Path]::GetFullPath($value) } catch { continue }
    if (Test-Path -LiteralPath (Join-Path $resolved $Marker)) { return $resolved }
  }
  return ''
}

function Get-PortOwner([int]$Port) {
  $row = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($row) { return [int]$row.OwningProcess }
  return 0
}

function Wait-Port([int]$Port, [int]$TimeoutSeconds = 30) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    $owner = Get-PortOwner $Port
    if ($owner) { return $owner }
    Start-Sleep -Milliseconds 500
  }
  return 0
}

function Start-ServiceProcess([string]$Name, [int]$Port, [string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory) {
  $existingOwner = Get-PortOwner $Port
  if ($existingOwner) {
    Write-Host ("[ready] {0} already listens on {1} (PID {2})" -f $Name, $Port, $existingOwner)
    return @{ name = $Name; port = $Port; ownerPid = $existingOwner; managed = $false }
  }
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  $stdout = Join-Path $RuntimeDir ("{0}.out.log" -f $Name)
  $stderr = Join-Path $RuntimeDir ("{0}.err.log" -f $Name)
  $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
  $owner = Wait-Port $Port 45
  if (-not $owner) {
    $detail = if (Test-Path -LiteralPath $stderr) { (Get-Content -LiteralPath $stderr -Tail 12 -ErrorAction SilentlyContinue) -join "`n" } else { '' }
    throw ("{0} failed to listen on port {1}. {2}" -f $Name, $Port, $detail)
  }
  Write-Host ("[started] {0} http://127.0.0.1:{1} (PID {2})" -f $Name, $Port, $owner)
  return @{ name = $Name; port = $Port; ownerPid = $owner; launcherPid = $process.Id; managed = $true }
}

function Read-State {
  if (-not (Test-Path -LiteralPath $StatePath)) { return @() }
  $state = Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
  return @($state.services)
}

function Stop-ServiceRecords($Services) {
  $services = @($Services)
  foreach ($service in @($services | Sort-Object port -Descending)) {
    if (-not $service.managed) { continue }
    $currentOwner = Get-PortOwner ([int]$service.port)
    if ($currentOwner -and $currentOwner -eq [int]$service.ownerPid) {
      Stop-Process -Id $currentOwner -Force -ErrorAction SilentlyContinue
      Write-Host ("[stopped] {0} (PID {1})" -f $service.name, $currentOwner)
    }
    if ($service.launcherPid -and (Get-Process -Id ([int]$service.launcherPid) -ErrorAction SilentlyContinue)) {
      Stop-Process -Id ([int]$service.launcherPid) -Force -ErrorAction SilentlyContinue
    }
  }
}

function Stop-ManagedServices {
  $services = @(Read-State)
  Stop-ServiceRecords $services
  if (Test-Path -LiteralPath $StatePath) { Remove-Item -LiteralPath $StatePath -Force }
}

function Show-Status {
  $ports = @(
    @{ name = 'frontend'; port = 5174 },
    @{ name = 'backend'; port = 5409 },
    @{ name = 'opencli-admin'; port = 8031 },
    @{ name = 'video-jiexi'; port = 4200 }
  )
  foreach ($item in $ports) {
    $owner = Get-PortOwner $item.port
    $label = if ($owner) { "online (PID $owner)" } else { 'offline' }
    Write-Host ("{0,-16} {1,-18} http://127.0.0.1:{2}" -f $item.name, $label, $item.port)
  }
}

if ($Action -eq 'status') { Show-Status; exit 0 }
if ($Action -in @('stop', 'restart')) { Stop-ManagedServices }
if ($Action -eq 'stop') { Show-Status; exit 0 }

$config = Read-RuntimeConfig
$opencliRoot = Resolve-ServiceRoot $config.opencliAdminProjectDir 'OPENCLI_ADMIN_PROJECT_DIR' @('opencli-admin', '自媒体内容拆解') 'backend\main.py'
$videoRoot = Resolve-ServiceRoot $config.videoJiexiProjectDir 'VIDEO_JIEXI_PROJECT_DIR' @('video-jiexi') 'server.js'
$backendPython = @(
  (Join-Path $ProjectRoot '.venv311\Scripts\python.exe'),
  (Join-Path $ProjectRoot '.venv\Scripts\python.exe')
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $backendPython) { throw 'Workbench Python environment is missing. Run scripts\setup-local.ps1 first.' }
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'sau_frontend\node_modules'))) { throw 'Frontend dependencies are missing. Run npm.cmd install in sau_frontend.' }

$services = @()
try {
  if ($videoRoot) {
    $services += Start-ServiceProcess 'video-jiexi' 4200 'cmd.exe' @('/d', '/c', 'npm.cmd', 'start') $videoRoot
  } else { Write-Host '[optional] video-jiexi project not found; video parsing will show a clear unavailable state.' }
  if ($opencliRoot) {
    $opencliPython = @(
      (Join-Path $opencliRoot '.venv311\Scripts\python.exe'),
      (Join-Path $opencliRoot '.venv\Scripts\python.exe')
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($opencliPython) {
      $services += Start-ServiceProcess 'opencli-admin' 8031 $opencliPython @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8031') $opencliRoot
    } else { Write-Host '[optional] OpenCLI Admin Python environment is missing; monitoring will be unavailable.' }
  } else { Write-Host '[optional] OpenCLI Admin project not found; monitoring will be unavailable.' }
  if ($opencliRoot -and -not $env:OPENCLI_ADMIN_BASE_URL) { $env:OPENCLI_ADMIN_BASE_URL = 'http://127.0.0.1:8031/api/v1' }
  if ($videoRoot -and -not $env:VIDEO_JIEXI_BASE_URL) { $env:VIDEO_JIEXI_BASE_URL = 'http://127.0.0.1:4200' }
  $services += Start-ServiceProcess 'backend' 5409 $backendPython @('sau_backend.py') $ProjectRoot
  $services += Start-ServiceProcess 'frontend' 5174 'cmd.exe' @('/d', '/c', 'npm.cmd', 'run', 'dev', '--', '--host', '127.0.0.1') (Join-Path $ProjectRoot 'sau_frontend')
} catch {
  Stop-ServiceRecords $services
  throw
}

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
@{ startedAt = (Get-Date).ToString('o'); services = $services } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatePath -Encoding UTF8
Write-Host ''
Show-Status
Write-Host ''
Write-Host 'Workbench is ready: http://127.0.0.1:5174'
if ($OpenBrowser) { Start-Process 'http://127.0.0.1:5174' }
