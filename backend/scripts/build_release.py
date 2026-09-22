#!/usr/bin/env python3
"""Build wheel/sdist and a deployable release tarball (medium-enterprise style).

Usage (from backend/):
  python scripts/build_release.py
  # or: make release
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
BUNDLE_NAME_TMPL = "snsn-api-{version}-release"


def read_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("version not found in pyproject.toml")
    return m.group(1)


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def clean() -> None:
    for path in (DIST, BUILD, ROOT / "snsn_api.egg-info"):
        if path.exists():
            shutil.rmtree(path)


def build_artifacts() -> tuple[Path, Path]:
    run([sys.executable, "-m", "pip", "install", "-U", "pip", "build"])
    run([sys.executable, "-m", "build", "--outdir", str(DIST)])
    wheels = sorted(DIST.glob("snsn_api-*-py3-none-any.whl"))
    sdists = sorted(DIST.glob("snsn_api-*.tar.gz"))
    if not wheels or not sdists:
        raise SystemExit("build produced no wheel/sdist")
    return wheels[-1], sdists[-1]


def write_install_md(bundle: Path, version: str, wheel_name: str) -> None:
    (bundle / "INSTALL.md").write_text(
        f"""# SnSn API {version} — install on server

Artifacts in this folder:

- `{wheel_name}` — install into the server venv
- `.env.example` — copy once to `/opt/snsn/.env` (do not overwrite secrets)
- `snsn-api.service` — systemd unit

## First install

```bash
sudo mkdir -p /opt/snsn/data/tmp /opt/snsn/releases /opt/snsn/frontend

# Prefer extracting the release tarball (includes dotfiles like .env.example).
# Do NOT use: cp -a some-dir/* dest/  — shell globs skip .* files.
sudo mkdir -p /opt/snsn/releases/{version}
sudo tar -xzf /path/to/snsn-api-{version}-release.tar.gz \\
  -C /opt/snsn/releases/{version} --strip-components=1
ls -la /opt/snsn/releases/{version}   # must show .env.example

cd /opt/snsn
sudo python3.11 -m venv .venv
sudo .venv/bin/pip install -U pip
sudo .venv/bin/pip install "/opt/snsn/releases/{version}/{wheel_name}"

sudo cp -n /opt/snsn/releases/{version}/.env.example /opt/snsn/.env
sudo chmod 600 /opt/snsn/.env
# edit /opt/snsn/.env — set SNSN_TMP_DIR=/opt/snsn/data/tmp and secrets

sudo cp /opt/snsn/releases/{version}/snsn-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now snsn-api
curl -s http://127.0.0.1:8000/api/health
```

Frontend static files go to `/opt/snsn/frontend/` (Nginx `root`).

## Upgrade

```bash
sudo mkdir -p /opt/snsn/releases/{version}
sudo tar -xzf /path/to/snsn-api-{version}-release.tar.gz \\
  -C /opt/snsn/releases/{version} --strip-components=1
sudo .venv/bin/pip install --upgrade "/opt/snsn/releases/{version}/{wheel_name}"
sudo systemctl restart snsn-api
```

Do not upload Windows `.venv`. Keep `/opt/snsn/.env` on the server only.
""",
        encoding="utf-8",
    )


def write_unit(bundle: Path) -> None:
    (bundle / "snsn-api.service").write_text(
        """[Unit]
Description=SnSn API
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/opt/snsn
EnvironmentFile=/opt/snsn/.env
ExecStart=/opt/snsn/.venv/bin/snsn-api start
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
""",
        encoding="utf-8",
    )


def make_bundle(version: str, wheel: Path) -> Path:
    name = BUNDLE_NAME_TMPL.format(version=version)
    bundle = DIST / name
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)

    shutil.copy2(wheel, bundle / wheel.name)
    shutil.copy2(ROOT / ".env.example", bundle / ".env.example")
    write_unit(bundle)
    write_install_md(bundle, version, wheel.name)

    tar_path = DIST / f"{name}.tar.gz"
    if tar_path.exists():
        tar_path.unlink()
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(bundle, arcname=name)
    return tar_path


def main() -> None:
    version = read_version()
    print(f"[snsn] building release {version}")
    clean()
    wheel, sdist = build_artifacts()
    tar_path = make_bundle(version, wheel)
    print("[snsn] done")
    print(f"  wheel : {wheel}")
    print(f"  sdist : {sdist}")
    print(f"  bundle: {tar_path}")
    print("Upload the .tar.gz to the server, extract, follow INSTALL.md")


if __name__ == "__main__":
    main()
