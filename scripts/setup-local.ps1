param(
  [switch]$SkipInstall,
  [string]$PythonPath = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path '.venv\Scripts\python.exe')) {
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

$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not $SkipInstall) {
  & $Python -m pip install --upgrade pip
  & $Python -m pip install --prefer-binary -r requirements.txt
}

if (-not (Test-Path 'conf.py')) {
  Copy-Item 'conf.example.py' 'conf.py'
  Write-Host 'Created conf.py from conf.example.py (local and ignored by Git).'
}

New-Item -ItemType Directory -Force -Path 'db', 'videos', 'videoFile', 'cookiesFile' | Out-Null
& $Python -c "import sau_backend; sau_backend.ensure_core_tables(); print('Database tables ready')"

Write-Host ''
Write-Host 'Local setup complete.'
Write-Host 'Backend: .venv\Scripts\python.exe sau_backend.py'
Write-Host 'Frontend: cd sau_frontend; npm.cmd run dev'
