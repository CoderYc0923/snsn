# Local / ops cheat sheet.

## Install once (dev)

```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install -e .
# Linux/macOS:
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
```

Or: `make install`

## Run locally

| Mode | Command | Notes |
|------|---------|--------|
| Dev (reload) | `make dev` / `.\dev.bat` / `snsn-api dev` | default `127.0.0.1:8001` |
| Prod-like | `make start` / `snsn-api start` | no reload; host/port from `.env` |

## Release package (deploy)

```powershell
# Windows
.\release.ps1
# or
python scripts\build_release.py
```

```bash
make release
```

Produces under `dist/`:

- `snsn_api-<ver>-py3-none-any.whl` — pip install 用
- `snsn-api-<ver>-release.tar.gz` — 上传服务器（含 wheel、`.env.example`、systemd、INSTALL.md）

服务器上用 wheel 安装，不要传源码树或 Windows `.venv`。详见仓库 `docs/2026-09-21-lightweight-server-deploy.md`。
