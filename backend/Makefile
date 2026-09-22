# SnSn API — local / CI entrypoints (same idea as npm scripts).
# On Windows without Make, use: .\dev.bat  or  .\.venv\Scripts\snsn-api.exe start

.PHONY: install install-dev sync dev start check dist release

PYTHON ?= python
VENV ?= .venv

ifeq ($(OS),Windows_NT)
  PY := $(VENV)/Scripts/python.exe
  PIP := $(VENV)/Scripts/pip.exe
  SNSN := $(VENV)/Scripts/snsn-api.exe
else
  PY := $(VENV)/bin/python
  PIP := $(VENV)/bin/pip
  SNSN := $(VENV)/bin/snsn-api
endif

install:
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

# Prefer when uv is available: reproducible lock + scripts on PATH
sync:
	uv sync
	uv pip install -e .

dev:
	$(PY) -m app.cli dev

start:
	$(PY) -m app.cli start

check:
	$(PY) -m compileall app

# Build wheel + sdist + snsn-api-<ver>-release.tar.gz
dist release:
	$(PYTHON) scripts/build_release.py
