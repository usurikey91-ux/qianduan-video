param([switch]$InstallerSmoke,[switch]$WhatIf)
$ErrorActionPreference='Stop'
$RuntimeRoot=Join-Path (Split-Path -Parent $PSScriptRoot) '.runtime'
if (-not $InstallerSmoke) { Write-Host '没有执行清理。请显式指定 -InstallerSmoke。'; exit 0 }
$targets=Get-ChildItem -LiteralPath $RuntimeRoot -Directory -Filter 'installer-smoke*' -ErrorAction SilentlyContinue
if (-not $targets) { Write-Host '未找到 installer-smoke 测试目录。'; exit 0 }
foreach($target in $targets){ if($WhatIf){Write-Host "[whatif] remove $($target.FullName)"}else{Remove-Item -LiteralPath $target.FullName -Recurse -Force;Write-Host "[removed] $($target.FullName)"} }
