#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${DASHBOARD_REPO:-/home/ubuntu/Fusion_Blanket_Design_TCT}"
APP_REPO="${DASHBOARD_APP_REPO:-/home/ubuntu/Fusion_Blanket_Design_TCT}"
HOST="${DASHBOARD_HOST:-0.0.0.0}"
PORT="${DASHBOARD_PORT:-8765}"
AUTO_FETCH="${DASHBOARD_AUTO_FETCH_INTERVAL:-60}"
AUTO_SELF_UPDATE="${DASHBOARD_AUTO_SELF_UPDATE_INTERVAL:-120}"

exec python3 "${SCRIPT_DIR}/server.py" \
  --repo "${REPO}" \
  --app-repo "${APP_REPO}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --auto-fetch-interval "${AUTO_FETCH}" \
  --auto-self-update-interval "${AUTO_SELF_UPDATE}"
