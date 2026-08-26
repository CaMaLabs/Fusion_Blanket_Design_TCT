#!/usr/bin/env bash
set -euo pipefail
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/home/ubuntu/m3dc1_runs/TCT_NATIVE_V2_BASELINE"
timeout 300s mpirun --oversubscribe -n 1 "/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
printf "return_code=%s\n" "$?" > run_status.txt

#!/usr/bin/env bash
set -euo pipefail
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/home/ubuntu/m3dc1_runs/TCT_NATIVE_V2_ZERO_AMP"
timeout 300s mpirun --oversubscribe -n 1 "/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
printf "return_code=%s\n" "$?" > run_status.txt

#!/usr/bin/env bash
set -euo pipefail
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/home/ubuntu/m3dc1_runs/TCT_NATIVE_V2_CONTROLLED"
timeout 300s mpirun --oversubscribe -n 1 "/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
printf "return_code=%s\n" "$?" > run_status.txt

#!/usr/bin/env bash
set -euo pipefail
export TMPDIR=/var/tmp
export OMPI_MCA_orte_tmpdir_base=/var/tmp
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/home/ubuntu/m3dc1_runs/TCT_NATIVE_V2_FALSIFICATION_DISPLACED"
timeout 300s mpirun --oversubscribe -n 1 "/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d" -pc_factor_mat_solver_type mumps > C1stdout 2> launcher.stderr
printf "return_code=%s\n" "$?" > run_status.txt

