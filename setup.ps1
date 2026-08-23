#Requires -Version 5.1
<#
  One-command bootstrap for Project Metis: installs backend (uv) and app (npm) dependencies.
#>
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "==> Backend: uv sync" -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
uv sync
Pop-Location

Write-Host "==> App: npm install" -ForegroundColor Cyan
Push-Location (Join-Path $root "app")
npm install
Pop-Location

Write-Host "==> Done. See README.md for how to run each half." -ForegroundColor Green
