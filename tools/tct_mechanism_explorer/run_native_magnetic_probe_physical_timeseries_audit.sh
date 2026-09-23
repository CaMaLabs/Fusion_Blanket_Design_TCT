#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/work/openmc/sweep
python3 tools/tct_mechanism_explorer/audit_native_magnetic_probe_physical_timeseries.py
