#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${DASHBOARD_REPO:-/home/ubuntu/Fusion_Blanket_Design_TCT}"
HOST="${DASHBOARD_HOST:-0.0.0.0}"
PORT="${DASHBOARD_PORT:-8765}"

exec python3 "${SCRIPT_DIR}/server.py" --repo "${REPO}" --host "${HOST}" --port "${PORT}"
