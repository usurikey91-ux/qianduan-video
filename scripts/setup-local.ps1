param(
  [switch]$SkipInstall,
  [switch]$SkipFrontendInstall,
  [switch]$SkipConnectorInstall,
  [string]$PythonPath = '',
  [string]$DouyinMcpProjectDir = '',
  [string]$DouyinMcpCliPath = '',
  [string]$OpenCliPath = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$ExistingPython = @(
  (Join-Path $ProjectRoot '.venv311\Scripts\python.exe'),
  (Join-Path $ProjectRoot '.venv\Scripts\python.exe')
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $ExistingPython) {
  Write-Host 'Creating project virtual environment: .venv'
  if ($PythonPath) {
    & $PythonPath -m venv .venv
  } else {
    # Prefer Python 3.11 because the project dependencies have the broadest
    # Windows wheel coverage there. Fall back to the default Python executable.
    $Created = $false
    $PyLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($null -ne $PyLauncher) {
      & $PyLauncher.Source -3.11 -c "import sys" 2>$null
      if ($LASTEXITCODE -eq 0) {
        & $PyLauncher.Source -3.11 -m venv .venv
        $Created = $true
      }
    }
    if (-not $Created) {
      python -m venv .venv
    }
  }
}

$Python = if ($ExistingPython) { $ExistingPython } else { Join-Path $ProjectRoot '.venv\Scripts\python.exe' }
if (-not $SkipInstall) {
  & $Python -m pip install --upgrade pip
  & $Python -m pip install --prefer-binary -r requirements.txt
}

if (-not $SkipFrontendInstall) {
  $Npm = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
  if ($null -eq $Npm) {
    throw '未找到 Node.js/npm。请先安装 Node.js 18 或更高版本，然后重新运行本脚本。'
  }
  Push-Location (Join-Path $ProjectRoot 'sau_frontend')
  try {
    & $Npm.Source install
    if ($LASTEXITCODE -ne 0) {
      throw '前端依赖安装失败。'
    }
  }
  finally {
    Pop-Location
  }
}

if (-not (Test-Path 'conf.py')) {
  Copy-Item 'conf.example.py' 'conf.py'
  Write-Host 'Created conf.py from conf.example.py (local and ignored by Git).'
}

New-Item -ItemType Directory -Force -Path 'db', 'videos', 'videoFile', 'cookiesFile' | Out-Null
& $Python -c "import sau_backend; sau_backend.ensure_core_tables(); print('Database tables ready')"
if ($LASTEXITCODE -ne 0) {
  throw '后端初始化失败。请检查上方 Python 错误；当前安装不能视为完成。'
}

if (-not $SkipConnectorInstall -and -not ($DouyinMcpProjectDir -or $DouyinMcpCliPath -or $OpenCliPath)) {
  & (Join-Path $PSScriptRoot 'install-connectors.ps1') -PythonPath $Python
  if ($LASTEXITCODE -ne 0) {
    throw '平台连接器安装失败。当前安装不能视为完成。'
  }
}

$RuntimeConfigPath = Join-Path $ProjectRoot 'runtime.local.json'
$RuntimeConfig = if (Test-Path -LiteralPath $RuntimeConfigPath) {
  Get-Content -LiteralPath $RuntimeConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
} else { @{} }

if ($DouyinMcpProjectDir) { $RuntimeConfig.douyinMcpProjectDir = [IO.Path]::GetFullPath($DouyinMcpProjectDir) }
if ($DouyinMcpCliPath) { $RuntimeConfig.douyinMcpCliPath = [IO.Path]::GetFullPath($DouyinMcpCliPath) }
if ($OpenCliPath) { $RuntimeConfig.opencliPath = [IO.Path]::GetFullPath($OpenCliPath) }
if ($DouyinMcpProjectDir -or $DouyinMcpCliPath -or $OpenCliPath) {
  $RuntimeConfig | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $RuntimeConfigPath -Encoding UTF8
  Write-Host 'Saved local connector paths to runtime.local.json (ignored by Git).'
}

$ToolsRoot = Join-Path (Split-Path -Parent $ProjectRoot) 'mcp-tools'
$ConfiguredDouyinProject = if ($RuntimeConfig.douyinMcpProjectDir) { [string]$RuntimeConfig.douyinMcpProjectDir } elseif ($env:DOUYIN_MCP_PROJECT_DIR) { $env:DOUYIN_MCP_PROJECT_DIR } else { Join-Path $ToolsRoot 'douyin-mcp' }
$DouyinCandidates = @(
  $(if ($RuntimeConfig.douyinMcpCliPath) { [string]$RuntimeConfig.douyinMcpCliPath }),
  $(if ($env:DOUYIN_MCP_CLI_PATH) { $env:DOUYIN_MCP_CLI_PATH }),
  (Join-Path $ConfiguredDouyinProject '.venv\Scripts\douyin-mcp.exe'),
  (Join-Path $ConfiguredDouyinProject '.venv311\Scripts\douyin-mcp.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$DouyinCli = $DouyinCandidates | Select-Object -First 1

$ConfiguredOpenCli = if ($RuntimeConfig.opencliPath) { [string]$RuntimeConfig.opencliPath } elseif ($env:OPENCLI_PATH) { $env:OPENCLI_PATH } else { '' }
$OpenCli = if ($ConfiguredOpenCli -and (Test-Path -LiteralPath $ConfiguredOpenCli)) {
  Get-Item -LiteralPath $ConfiguredOpenCli
} else {
  Get-Command 'opencli.cmd' -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host 'Platform connector check:'
if ($DouyinCli) {
  Write-Host '  [OK] Douyin creator connector'
} else {
  Write-Warning '未找到抖音创作者连接器。工作台仍可启动，但抖音扫码登录和后台同步不可用。可使用 -DouyinMcpProjectDir 指定本机目录。'
}
if ($null -ne $OpenCli) {
  Write-Host '  [OK] OpenCLI / Xiaohongshu connector'
} else {
  Write-Warning '未找到 OpenCLI。工作台仍可启动，但小红书扫码登录和后台同步不可用。可使用 -OpenCliPath 指定 opencli.cmd。'
}

Write-Host ''
Write-Host 'Local setup complete.'
Write-Host ("Backend: {0} sau_backend.py" -f $Python)
Write-Host 'Frontend: cd sau_frontend; npm.cmd run dev'
