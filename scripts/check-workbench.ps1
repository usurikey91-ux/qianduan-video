param([switch]$Json)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
function Get-DirectoryBytes([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return [int64]0 }
  return [int64]((Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum)
}
function Test-Port([int]$Port) { return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1) }
function Test-Http([string]$Uri) { try { $r=Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5; return @{ok=$true;status=$r.StatusCode} } catch { return @{ok=$false;status=0} } }
$result = [ordered]@{
  checkedAt=(Get-Date).ToString('o'); project=$ProjectRoot
  sizes=[ordered]@{runtimeMb=[math]::Round((Get-DirectoryBytes (Join-Path $ProjectRoot '.runtime'))/1MB,1); pythonEnvMb=[math]::Round((Get-DirectoryBytes (Join-Path $ProjectRoot '.venv311'))/1MB,1); frontendNodeModulesMb=[math]::Round((Get-DirectoryBytes (Join-Path $ProjectRoot 'sau_frontend\node_modules'))/1MB,1)}
  ports=[ordered]@{frontend5174=Test-Port 5174;backend5409=Test-Port 5409;legacy4200=Test-Port 4200}
  endpoints=[ordered]@{frontend=Test-Http 'http://127.0.0.1:5174/';backend=Test-Http 'http://127.0.0.1:5409/benchmark/douyin/accounts';videoJiexi=Test-Http 'http://127.0.0.1:5409/integrations/video-jiexi/status'}
  dependencies=[ordered]@{python=[bool](Get-Command python.exe -ErrorAction SilentlyContinue);node=[bool](Get-Command node.exe -ErrorAction SilentlyContinue);npm=[bool](Get-Command npm.cmd -ErrorAction SilentlyContinue);git=[bool](Get-Command git.exe -ErrorAction SilentlyContinue)}
}
if ($Json) { $result | ConvertTo-Json -Depth 8; exit 0 }
Write-Host 'Workbench health and footprint check'
Write-Host ("  runtime: {0} MB" -f $result.sizes.runtimeMb)
Write-Host ("  python env: {0} MB" -f $result.sizes.pythonEnvMb)
Write-Host ("  frontend node_modules: {0} MB" -f $result.sizes.frontendNodeModulesMb)
Write-Host ("  5174 frontend: {0}" -f ($(if($result.ports.frontend5174){'online'}else{'offline'})))
Write-Host ("  5409 backend: {0}" -f ($(if($result.ports.backend5409){'online'}else{'offline'})))
Write-Host ("  4200 legacy parser: {0}" -f ($(if($result.ports.legacy4200){'listening (unexpected)'}else{'closed'})))
Write-Host ("  video-jiexi endpoint: {0}" -f ($(if($result.endpoints.videoJiexi.ok){'reachable'}else{'unavailable'})))
