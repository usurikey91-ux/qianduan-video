$ErrorActionPreference = 'Continue'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WorkbenchScript = Join-Path $PSScriptRoot 'workbench.ps1'
$RuntimeDirectory = Join-Path $ProjectRoot '.runtime'
$StatePath = Join-Path $RuntimeDirectory 'processes.json'
$StatusLog = Join-Path $RuntimeDirectory 'watchdog.log'
$RepairLog = Join-Path $RuntimeDirectory 'watchdog-repair.log'
$CheckIntervalSeconds = 15
$mutex = [System.Threading.Mutex]::new($false, 'Local\ContentWorkbench5174Watchdog')

if (-not $mutex.WaitOne(0, $false)) {
  exit 0
}

New-Item -ItemType Directory -Force -Path $RuntimeDirectory | Out-Null
Set-Location -LiteralPath $ProjectRoot

$Services = @(
  @{ name = 'frontend'; port = 5174; uri = 'http://127.0.0.1:5174/'; expected = '<title>自媒体内容拆解工作台</title>' },
  @{ name = 'backend'; port = 5409; uri = 'http://127.0.0.1:5409/benchmark/douyin/accounts'; expected = '"code":200' },
  @{ name = 'opencli-admin'; port = 8031; uri = 'http://127.0.0.1:8031/docs'; expected = 'OpenCLI Admin' },
  @{ name = 'video-jiexi'; port = 4200; uri = 'http://127.0.0.1:4200/'; expected = 'Video Jiexi' }
)

function Write-Status([string]$Message) {
  Add-Content -LiteralPath $StatusLog -Encoding UTF8 -Value ('[{0:yyyy-MM-dd HH:mm:ss}] {1}' -f (Get-Date), $Message)
}

function Get-PortOwner([int]$Port) {
  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($listener) { return [int]$listener.OwningProcess }
  return 0
}

function Read-State {
  if (-not (Test-Path -LiteralPath $StatePath)) { return @() }
  try {
    $state = Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    return @($state.services)
  }
  catch {
    Write-Status ('Could not read runtime state: ' + $_.Exception.Message)
    return @()
  }
}

function Test-ServiceHealth($Service) {
  try {
    $response = Invoke-WebRequest -Uri $Service.uri -UseBasicParsing -TimeoutSec 5
    return $response.StatusCode -eq 200 -and $response.Content.Contains($Service.expected)
  }
  catch {
    return $false
  }
}

function Stop-KnownManagedProcess($Service, $State) {
  $owner = Get-PortOwner ([int]$Service.port)
  if (-not $owner) { return $true }

  $record = @($State) | Where-Object {
    $_.name -eq $Service.name -and
    [int]$_.port -eq [int]$Service.port -and
    [int]$_.ownerPid -eq $owner -and
    $_.managed
  } | Select-Object -First 1

  if (-not $record) {
    Write-Status ("{0} is unhealthy, but port {1} belongs to an unmanaged PID {2}; leaving it untouched." -f $Service.name, $Service.port, $owner)
    return $false
  }

  Write-Status ("Stopping unhealthy managed service {0} (PID {1})." -f $Service.name, $owner)
  & taskkill.exe /PID $owner /T /F *> $null
  if ($record.launcherPid -and (Get-Process -Id ([int]$record.launcherPid) -ErrorAction SilentlyContinue)) {
    Stop-Process -Id ([int]$record.launcherPid) -Force -ErrorAction SilentlyContinue
  }
  return $true
}

function Repair-Workbench($UnhealthyServices) {
  $state = @(Read-State)
  $safeToStart = $true

  foreach ($service in $UnhealthyServices) {
    if (-not (Stop-KnownManagedProcess $service $state)) {
      $safeToStart = $false
    }
  }

  if (-not $safeToStart) {
    Write-Status 'Repair paused because an unhealthy port is owned by an unmanaged process.'
    return
  }

  try {
    Write-Status ('Repairing services: ' + (($UnhealthyServices | ForEach-Object { $_.name }) -join ', '))
    & $WorkbenchScript start *> $RepairLog
    Write-Status 'Workbench repair command completed.'
  }
  catch {
    Write-Status ('Workbench repair failed: ' + $_.Exception.Message)
  }
}

try {
  Write-Status 'Workbench watchdog started.'
  while ($true) {
    $unhealthy = @($Services | Where-Object { -not (Test-ServiceHealth $_) })
    if ($unhealthy.Count -gt 0) {
      Repair-Workbench $unhealthy
    }
    Start-Sleep -Seconds $CheckIntervalSeconds
  }
}
finally {
  $mutex.ReleaseMutex()
  $mutex.Dispose()
  Write-Status 'Workbench watchdog stopped.'
}
