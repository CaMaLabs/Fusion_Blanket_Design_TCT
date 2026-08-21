#!/usr/bin/env bash
set -euo pipefail
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/home/ubuntu/m3dc1_runs/TCT_NATIVE_RMP_BASELINE_SINGLEPART"
mpirun --oversubscribe -n 1 "/home/ubuntu/M3DC1-official/build-ubuntu-2d-complex/unstructured/m3dc1_2d_complex" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
printf "return_code=%s\n" "$?" > run_status.txt


#!/usr/bin/env bash
set -euo pipefail
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/home/ubuntu/m3dc1_runs/TCT_NATIVE_CONTROLLED"
mpirun --oversubscribe -n 1 "/home/ubuntu/M3DC1-official/build-ubuntu-2d-complex/unstructured/m3dc1_2d_complex" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
printf "return_code=%s\n" "$?" > run_status.txt


#!/usr/bin/env bash
set -euo pipefail
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/home/ubuntu/m3dc1_runs/TCT_NATIVE_FALSIFICATION_REVERSE"
mpirun --oversubscribe -n 1 "/home/ubuntu/M3DC1-official/build-ubuntu-2d-complex/unstructured/m3dc1_2d_complex" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
printf "return_code=%s\n" "$?" > run_status.txt
