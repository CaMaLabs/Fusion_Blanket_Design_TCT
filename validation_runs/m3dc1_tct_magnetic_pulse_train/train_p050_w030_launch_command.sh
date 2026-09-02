#!/usr/bin/env bash
set -euo pipefail
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/tmp/m3dc1_tct_magnetic_pulse_train_runs/train_p050_w030"
set +e
timeout 1200s mpirun --oversubscribe -n 1 "/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
rc=$?
set -e
printf 'return_code=%s\n' "$rc" > run_status.txt
exit "$rc"
