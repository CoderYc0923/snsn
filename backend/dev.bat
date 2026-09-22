@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [snsn] missing .venv - run once:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -r requirements.txt
  echo   .venv\Scripts\pip install -e .
  exit /b 1
)

".venv\Scripts\python.exe" -m app.cli dev %*