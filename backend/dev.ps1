# SnSn local API — thin wrapper around `python -m app.cli dev`
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
  Write-Host '[snsn] missing .venv — run: make install'
  Write-Host '  or: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt; .\.venv\Scripts\pip install -e .'
  exit 1
}

& $py -m app.cli dev @args
