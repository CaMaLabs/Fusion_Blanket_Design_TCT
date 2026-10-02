#!/usr/bin/env bash
set -euo pipefail

# Canonical runtime bootstrap for every TCT agent-pipeline runner.
# This prevents individual runners from silently drifting onto system Python
# or a different analysis environment.
REPO="${TCT_PIPELINE_REPO:-/home/ubuntu/work/openmc/sweep}"
AUDIT_VENV="${TCT_AUDIT_VENV:-$REPO/.venv-dudson}"
AUDIT_PYTHON="$AUDIT_VENV/bin/python"
TMP_ROOT="${TCT_TMPDIR:-/tmp/tct-${USER:-ubuntu}}"

cd "$REPO"
mkdir -p "$TMP_ROOT"
export TMPDIR="$TMP_ROOT"
export OMPI_MCA_orte_tmpdir_base="$TMP_ROOT"
export PYTHONUNBUFFERED=1

# Make the established audit venv the default for every bare python/python3
# invocation. A runner may deliberately choose another interpreter, but it
# must then do so explicitly.
if [[ ! -x "$AUDIT_PYTHON" ]]; then
  echo "TCT_RUNTIME_ERROR: canonical audit venv Python missing: $AUDIT_PYTHON" >&2
  exit 96
fi
export TCT_AUDIT_VENV="$AUDIT_VENV"
export TCT_PYTHON="$AUDIT_PYTHON"
export VIRTUAL_ENV="$AUDIT_VENV"
export PATH="$AUDIT_VENV/bin:$PATH"

# Native M3D-C1 runners historically rely on this Spack environment. Activate
# it centrally when available so runner-local activation is no longer required.
SPACK_SETUP="${TCT_SPACK_SETUP:-$HOME/spack/share/spack/setup-env.sh}"
if [[ -f "$SPACK_SETUP" ]]; then
  # shellcheck disable=SC1090
  source "$SPACK_SETUP"
  if command -v spack >/dev/null 2>&1; then
    if spack env activate m3dc1-deps >/dev/null 2>&1; then
      export TCT_M3DC1_SPACK_ENV="m3dc1-deps"
      # Spack may alter PATH; put the canonical audit venv back first.
      export PATH="$AUDIT_VENV/bin:$PATH"
    else
      echo "TCT_RUNTIME_WARN: unable to activate Spack env m3dc1-deps; runner may still provide its own environment" >&2
    fi
  fi
else
  echo "TCT_RUNTIME_WARN: Spack setup not found at $SPACK_SETUP; runner may still provide its own environment" >&2
fi

echo "TCT_RUNTIME repo=$REPO"
echo "TCT_RUNTIME python=$("$AUDIT_PYTHON" -c 'import sys; print(sys.executable)')"
echo "TCT_RUNTIME python_version=$("$AUDIT_PYTHON" -c 'import sys; print(sys.version.split()[0])')"
echo "TCT_RUNTIME venv=$AUDIT_VENV"
echo "TCT_RUNTIME tmpdir=$TMP_ROOT"
echo "TCT_RUNTIME spack_env=${TCT_M3DC1_SPACK_ENV:-unavailable}"

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <runner-path>" >&2
  exit 64
fi

RUNNER="$1"
if [[ "$RUNNER" != "$REPO"/tools/tct_mechanism_explorer/run_*.sh ]]; then
  echo "TCT_RUNTIME_ERROR: refusing non-TCT runner: $RUNNER" >&2
  exit 65
fi

exec bash "$RUNNER"
