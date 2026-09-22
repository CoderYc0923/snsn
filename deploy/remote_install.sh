#!/usr/bin/env bash
# Run on the server after artifacts are uploaded to /tmp/snsn-ci/
set -euo pipefail

WWW_DIR="${SNSN_WWW_DIR:-/opt/snsn/frontend}"
RELEASE_DIR="/opt/snsn/releases"
API_TAR=""
WWW_TAR=""

for f in /tmp/snsn-ci/snsn-api-*-release.tar.gz; do
  [[ -f "$f" ]] && API_TAR="$f" && break
done
for f in /tmp/snsn-ci/snsn-www-*.tar.gz; do
  [[ -f "$f" ]] && WWW_TAR="$f" && break
done

mkdir -p /opt/snsn/data/tmp "$RELEASE_DIR" "$WWW_DIR" /opt/snsn/.venv 2>/dev/null || true

if [[ -n "$API_TAR" ]]; then
  echo "[snsn] install backend from $API_TAR"
  ver="$(basename "$API_TAR" | sed -E 's/snsn-api-(.+)-release\.tar\.gz/\1/')"
  dest="$RELEASE_DIR/$ver"
  rm -rf "$dest"
  mkdir -p "$dest"
  tar -xzf "$API_TAR" -C "$dest" --strip-components=1

  if [[ ! -x /opt/snsn/.venv/bin/python ]]; then
    python3.11 -m venv /opt/snsn/.venv
    /opt/snsn/.venv/bin/pip install -U pip
  fi
  /opt/snsn/.venv/bin/pip install --upgrade "$dest"/snsn_api-*-py3-none-any.whl

  if [[ ! -f /opt/snsn/.env ]]; then
    cp "$dest/.env.example" /opt/snsn/.env
    chmod 600 /opt/snsn/.env
    echo "[snsn] created /opt/snsn/.env — edit secrets before first real traffic"
  fi

  if [[ -f "$dest/snsn-api.service" ]]; then
    cp "$dest/snsn-api.service" /etc/systemd/system/snsn-api.service
    systemctl daemon-reload
  fi
  systemctl enable snsn-api >/dev/null 2>&1 || true
  systemctl restart snsn-api
  sleep 1
  curl -sf "http://127.0.0.1:8000/api/health" | head -c 200 || true
  echo
fi

if [[ -n "$WWW_TAR" ]]; then
  echo "[snsn] install frontend to $WWW_DIR from $WWW_TAR"
  mkdir -p "$WWW_DIR"
  # Replace contents; keep directory itself
  find "$WWW_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  tar -xzf "$WWW_TAR" -C "$WWW_DIR"
  if id nginx >/dev/null 2>&1; then
    chown -R nginx:nginx "$WWW_DIR"
  fi
  find "$WWW_DIR" -type d -exec chmod 755 {} \;
  find "$WWW_DIR" -type f -exec chmod 644 {} \;
fi

echo "[snsn] deploy done"
rm -rf /tmp/snsn-ci
