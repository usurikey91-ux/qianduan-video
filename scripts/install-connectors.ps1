param(
  [string]$PythonPath = '',
  [string]$InstallRoot = '',
  [string]$RuntimeConfigPath = '',
  [switch]$SkipLegacyDataMigration,
  [switch]$SkipVideoJiexi
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LockPath = Join-Path $ProjectRoot 'connectors.lock.json'
$Lock = Get-Content -LiteralPath $LockPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
$ManagedRoot = if ($InstallRoot) { [IO.Path]::GetFullPath($InstallRoot) } else { Join-Path $ProjectRoot '.runtime\connectors' }
$ToolsRoot = Join-Path $ProjectRoot '.runtime\tools'
$ConfigPath = if ($RuntimeConfigPath) { [IO.Path]::GetFullPath($RuntimeConfigPath) } else { Join-Path $ProjectRoot 'runtime.local.json' }

function Assert-LastExit([string]$Message) {
  if ($LASTEXITCODE -ne 0) { throw $Message }
}

function Resolve-Python {
  if ($PythonPath) {
    $resolved = [IO.Path]::GetFullPath($PythonPath)
    if (-not (Test-Path -LiteralPath $resolved)) { throw "Python does not exist: $resolved" }
    return $resolved
  }
  $candidate = @(
    (Join-Path $ProjectRoot '.venv311\Scripts\python.exe'),
    (Join-Path $ProjectRoot '.venv\Scripts\python.exe')
  ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
  if (-not $candidate) { throw 'Project Python environment is missing. Run scripts\setup-local.ps1 first.' }
  return $candidate
}

function Install-PinnedRepository(
  [string]$Name,
  [hashtable]$Definition,
  [string]$Target
) {
  $patches = @($Definition.patch, $Definition.bootstrapPatch) | Where-Object { $_ }
  $patchSignature = $patches -join ';'
  $markerPath = Join-Path $Target '.sunbird-managed.json'
  if (Test-Path -LiteralPath $markerPath) {
    $marker = Get-Content -LiteralPath $markerPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    if ($marker.commit -eq $Definition.commit -and $marker.patch -eq $patchSignature) {
      Write-Host "  [ready] $Name source"
      return
    }
    throw "$Name exists but does not match connectors.lock.json: $Target"
  }
  if (Test-Path -LiteralPath $Target) {
    throw "$Name target already exists and is not managed by this installer: $Target"
  }

  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
  Write-Host "  [clone] $Name"
  & git clone --no-checkout --filter=blob:none $Definition.repository $Target
  Assert-LastExit "Failed to clone $Name."
  & git -C $Target checkout --detach $Definition.commit
  Assert-LastExit "Failed to checkout pinned $Name commit $($Definition.commit)."

  foreach ($relativePatch in $patches) {
    $patchPath = Join-Path $ProjectRoot $relativePatch
    & git -C $Target apply --check --whitespace=nowarn $patchPath
    Assert-LastExit "$Name integration patch no longer applies to the pinned commit."
    & git -C $Target apply --whitespace=nowarn $patchPath
    Assert-LastExit "Failed to apply the $Name integration patch."
  }

  @{
    repository = $Definition.repository
    commit = $Definition.commit
    patch = $patchSignature
    installedAt = (Get-Date).ToString('o')
  } | ConvertTo-Json | Set-Content -LiteralPath $markerPath -Encoding UTF8
}

function Install-PythonProject([string]$Name, [string]$Target, [string]$Python) {
  $venvPython = Join-Path $Target '.venv\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "  [venv] $Name"
    & $Python -m venv (Join-Path $Target '.venv')
    Assert-LastExit "Failed to create the $Name virtual environment."
  }
  Write-Host "  [install] $Name dependencies"
  # Use a regular wheel install rather than editable mode. Python 3.11 reads
  # editable .pth paths using the Windows locale encoding, which breaks when
  # the cloned workbench lives under a Chinese directory name.
  & $venvPython -m pip install --disable-pip-version-check --prefer-binary $Target
  Assert-LastExit "Failed to install $Name."
  return $venvPython
}

function Install-BundledDirectory([string]$Name, [hashtable]$Definition, [string]$Target) {
  $source = Join-Path $ProjectRoot $Definition.bundledPath
  $markerPath = Join-Path $Target '.sunbird-managed.json'
  if (Test-Path -LiteralPath $markerPath) {
    $marker = Get-Content -LiteralPath $markerPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    if ($marker.bundledPath -eq $Definition.bundledPath -and $marker.version -eq $Definition.version) {
      Write-Host "  [ready] $Name source"
      return
    }
    throw "$Name exists but does not match connectors.lock.json: $Target"
  }
  if (Test-Path -LiteralPath $Target) {
    throw "$Name target already exists and is not managed by this installer: $Target"
  }
  Write-Host "  [copy] $Name"
  New-Item -ItemType Directory -Force -Path $Target | Out-Null
  Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $Target -Recurse -Force
  @{
    bundledPath = $Definition.bundledPath
    version = $Definition.version
    installedAt = (Get-Date).ToString('o')
  } | ConvertTo-Json | Set-Content -LiteralPath $markerPath -Encoding UTF8
}

$Git = Get-Command 'git.exe' -ErrorAction SilentlyContinue
if ($null -eq $Git) { throw 'Git is required to install the pinned connectors.' }
$Npm = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
if ($null -eq $Npm) { throw 'Node.js/npm is required to install OpenCLI.' }
$Python = Resolve-Python

New-Item -ItemType Directory -Force -Path $ManagedRoot, $ToolsRoot | Out-Null
$DouyinRoot = Join-Path $ManagedRoot 'douyin-mcp'
$AdminRoot = Join-Path $ManagedRoot 'opencli-admin'
$VideoRoot = Join-Path $ManagedRoot 'video-jiexi'

Write-Host 'Installing pinned local connectors:'
Install-PinnedRepository 'douyin-mcp' $Lock.douyinMcp $DouyinRoot
if (-not $SkipLegacyDataMigration -and -not (Test-Path -LiteralPath (Join-Path $DouyinRoot 'data'))) {
  $legacyDouyinData = Join-Path (Split-Path -Parent $ProjectRoot) 'mcp-tools\douyin-mcp\data'
  if (Test-Path -LiteralPath $legacyDouyinData) {
    Write-Host '  [migrate] existing local Douyin login and data'
    New-Item -ItemType Directory -Force -Path (Join-Path $DouyinRoot 'data') | Out-Null
    Get-ChildItem -LiteralPath $legacyDouyinData -Force |
      Where-Object { $_.Name -ne '.douyin-mcp.instance.lock' } |
      Copy-Item -Destination (Join-Path $DouyinRoot 'data') -Recurse -Force
  }
}
$DouyinPython = Install-PythonProject 'douyin-mcp' $DouyinRoot $Python
$DouyinCli = Join-Path $DouyinRoot '.venv\Scripts\douyin-mcp.exe'
& $DouyinCli init | Out-Null
Assert-LastExit 'douyin-mcp initialization failed.'

Install-PinnedRepository 'opencli-admin' $Lock.opencliAdmin $AdminRoot
if (-not $SkipLegacyDataMigration -and -not (Test-Path -LiteralPath (Join-Path $AdminRoot 'opencli_admin.db'))) {
  $legacyAdminDb = Join-Path (Split-Path -Parent $ProjectRoot) '自媒体内容拆解\opencli_admin.db'
  if (Test-Path -LiteralPath $legacyAdminDb) {
    Write-Host '  [migrate] existing benchmark database'
    Copy-Item -LiteralPath $legacyAdminDb -Destination (Join-Path $AdminRoot 'opencli_admin.db')
  }
}
$AdminPython = Install-PythonProject 'opencli-admin' $AdminRoot $Python

Write-Host '  [install] OpenCLI 1.8.6 (project-local)'
& $Npm.Source install --prefix $ToolsRoot --no-audit --no-fund $Lock.opencli.package
Assert-LastExit 'Failed to install OpenCLI.'
$OpenCliPath = Join-Path $ToolsRoot 'node_modules\.bin\opencli.cmd'
if (-not (Test-Path -LiteralPath $OpenCliPath)) { throw "OpenCLI executable was not created: $OpenCliPath" }

if (-not $SkipVideoJiexi) {
  Install-BundledDirectory 'video-jiexi' $Lock.videoJiexi $VideoRoot
  Write-Host '  [install] video-jiexi dependencies'
  & $Npm.Source install --prefix $VideoRoot --no-audit --no-fund
  Assert-LastExit 'Failed to install video-jiexi dependencies.'
  $FfmpegPackageRoot = Join-Path $VideoRoot 'node_modules\ffmpeg-static'
  $FfmpegExecutable = Join-Path $FfmpegPackageRoot 'ffmpeg.exe'
  if (-not (Test-Path -LiteralPath $FfmpegExecutable)) {
    Write-Host '  [install] project-local FFmpeg binary'
    Push-Location $FfmpegPackageRoot
    try {
      & node.exe install.js
      Assert-LastExit 'Failed to install the project-local FFmpeg binary.'
    }
    finally { Pop-Location }
  }
  $YtDlpExecutable = Join-Path (Split-Path -Parent $Python) 'yt-dlp.exe'
  if (-not (Test-Path -LiteralPath $YtDlpExecutable)) {
    throw 'yt-dlp is missing from the project Python environment. Re-run setup-local.ps1 without -SkipInstall.'
  }
}

$RuntimeConfig = if (Test-Path -LiteralPath $ConfigPath) {
  Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
} else { @{} }
$RuntimeConfig.douyinMcpProjectDir = $DouyinRoot
$RuntimeConfig.douyinMcpCliPath = $DouyinCli
$RuntimeConfig.opencliAdminProjectDir = $AdminRoot
$RuntimeConfig.opencliPath = $OpenCliPath
if (-not $SkipVideoJiexi) {
  $RuntimeConfig.videoJiexiProjectDir = $VideoRoot
  $RuntimeConfig.videoJiexiDownloadDir = Join-Path $VideoRoot 'downloads'
  $RuntimeConfig.ytDlpPath = $YtDlpExecutable
}
$RuntimeConfig | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

Write-Host ''
Write-Host 'Connector installation complete.'
Write-Host "Runtime config: $ConfigPath"
Write-Host 'Platform login is intentionally not automated; use the workbench account-connection page to scan the official QR code.'
