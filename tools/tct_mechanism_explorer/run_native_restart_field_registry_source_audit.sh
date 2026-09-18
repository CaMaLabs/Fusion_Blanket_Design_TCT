#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
python3 -u tools/tct_mechanism_explorer/native_restart_field_registry_source_audit.py
