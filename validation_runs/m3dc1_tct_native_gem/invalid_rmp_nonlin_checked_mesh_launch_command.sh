#!/usr/bin/env bash
set -euo pipefail
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/home/ubuntu/m3dc1_runs/TCT_NATIVE_RMP_NONLIN_BASELINE_3D_CLEAN"
mpirun --oversubscribe -n 64 "/home/ubuntu/M3DC1-official/build-ubuntu-3d/unstructured/m3dc1_3d" -options_file options_bjacobi.type_mumps > C1stdout 2> launcher.stderr
printf "return_code=%s\n" "$?" > run_status.txt
