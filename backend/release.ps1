# Build a release package (wheel + deploy tarball). Same idea as npm run build.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
  $py = 'python'
}

& $py (Join-Path $PSScriptRoot 'scripts\build_release.py')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host 'Upload dist\snsn-api-*-release.tar.gz to the server.'
