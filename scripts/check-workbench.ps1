param([switch]$Json)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot
function Get-DirectoryBytes([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return [int64]0 }
  return [int64]((Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum)
}
function Test-Port([int]$Port) { return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1) }
function Test-Http([string]$Uri, [int]$TimeoutSeconds = 5) { try { $r=Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec $TimeoutSeconds; return @{ok=$true;status=$r.StatusCode} } catch { return @{ok=$false;status=0} } }
function Test-Frontend {
  try {
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5174/' -UseBasicParsing -TimeoutSec 5
    return @{ ok=($response.StatusCode -eq 200 -and $response.Content.Contains('<title>自媒体内容拆解工作台</title>')); status=$response.StatusCode }
  } catch { return @{ok=$false;status=0} }
}
function Test-Parser {
  try {
    $response = Invoke-RestMethod -Uri 'http://127.0.0.1:5409/integrations/video-jiexi/status' -TimeoutSec 20
    return @{
      ok=($response.code -eq 200 -and $response.data.health.ok -eq $true -and $response.data.health.appId -eq 'video-jiexi-local-v1')
      embedded=($response.data.embedded -eq $true)
      downloadDir=$response.data.health.downloadDir
    }
  } catch { return @{ok=$false;embedded=$false;downloadDir=''} }
}
$result = [ordered]@{
  checkedAt=(Get-Date).ToString('o'); project=$ProjectRoot
  sizes=[ordered]@{runtimeMb=[math]::Round((Get-DirectoryBytes (Join-Path $ProjectRoot '.runtime'))/1MB,1); pythonEnvMb=[math]::Round((Get-DirectoryBytes (Join-Path $ProjectRoot '.venv311'))/1MB,1); frontendNodeModulesMb=[math]::Round((Get-DirectoryBytes (Join-Path $ProjectRoot 'sau_frontend\node_modules'))/1MB,1)}
  ports=[ordered]@{frontend5174=Test-Port 5174;backend5409=Test-Port 5409;opencliAdmin8031=Test-Port 8031;collectorBrowser9222=Test-Port 9222}
  endpoints=[ordered]@{frontend=Test-Frontend;backend=Test-Http 'http://127.0.0.1:5409/benchmark/douyin/accounts';opencliAdmin=Test-Http 'http://127.0.0.1:8031/api/v1/health';collectorBrowser=Test-Http 'http://127.0.0.1:9222/json/version';videoJiexiProxy=Test-Parser}
  dependencies=[ordered]@{python=[bool](Get-Command python.exe -ErrorAction SilentlyContinue);node=[bool](Get-Command node.exe -ErrorAction SilentlyContinue);npm=[bool](Get-Command npm.cmd -ErrorAction SilentlyContinue);git=[bool](Get-Command git.exe -ErrorAction SilentlyContinue)}
}
if ($Json) { $result | ConvertTo-Json -Depth 8; exit 0 }
Write-Host 'Workbench health and footprint check'
Write-Host ("  runtime: {0} MB" -f $result.sizes.runtimeMb)
Write-Host ("  python env: {0} MB" -f $result.sizes.pythonEnvMb)
Write-Host ("  frontend node_modules: {0} MB" -f $result.sizes.frontendNodeModulesMb)
Write-Host ("  5174 workbench: {0}" -f ($(if($result.endpoints.frontend.ok){'online'}elseif($result.ports.frontend5174){'wrong service'}else{'offline'})))
Write-Host ("  5409 backend: {0}" -f ($(if($result.ports.backend5409){'online'}else{'offline'})))
Write-Host ("  8031 OpenCLI Admin: {0}" -f ($(if($result.endpoints.opencliAdmin.ok){'online'}elseif($result.ports.opencliAdmin8031){'unhealthy'}else{'offline'})))
Write-Host ("  9222 collector browser: {0}" -f ($(if($result.endpoints.collectorBrowser.ok){'online'}elseif($result.ports.collectorBrowser9222){'unhealthy'}else{'offline'})))
Write-Host ("  video-jiexi backend proxy: {0}" -f ($(if($result.endpoints.videoJiexiProxy.ok){'reachable'}else{'unavailable'})))
