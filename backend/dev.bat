@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [snsn] missing .venv - run once:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -e .
  exit /b 1
)

REM Prefer WinGet FFmpeg shims / package bins so health check sees ffmpeg+ffprobe.
set "WG_LINKS=%LOCALAPPDATA%\Microsoft\WinGet\Links"
if exist "%WG_LINKS%\ffmpeg.exe" set "PATH=%WG_LINKS%;%PATH%"

for /d %%D in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*") do (
  if exist "%%D\ffmpeg-*\full_build\bin\ffmpeg.exe" (
    for /d %%B in ("%%D\ffmpeg-*\full_build\bin") do set "PATH=%%~fB;%PATH%"
  )
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [snsn] warning: ffmpeg not on PATH — install with: winget install Gyan.FFmpeg
)

".venv\Scripts\python.exe" -m app.cli dev %*
