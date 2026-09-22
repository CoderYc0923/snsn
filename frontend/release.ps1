# Build frontend and pack dist/ into a single tar.gz for manual upload.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not (Test-Path '.\.env') -and -not $env:VITE_SNSN_API_TOKEN) {
  Write-Host '[snsn] tip: set VITE_SNSN_API_TOKEN in .env (or env) before release if API token is required'
}

npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$outDir = Join-Path $PSScriptRoot 'release'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$tarName = "snsn-www-$stamp.tar.gz"
$tarPath = Join-Path $outDir $tarName

if (Test-Path $tarPath) { Remove-Item $tarPath -Force }

# Pack contents of dist/ (not the dist folder itself) so extract goes straight into www/
Push-Location (Join-Path $PSScriptRoot 'dist')
try {
  tar -czf $tarPath .
} finally {
  Pop-Location
}

Write-Host ''
Write-Host "[snsn] built $tarPath"
Write-Host 'Upload then on server:'
Write-Host "  sudo tar -xzf $tarName -C /opt/snsn/frontend"
Write-Host '  sudo chown -R nginx:nginx /opt/snsn/frontend'
