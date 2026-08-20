#!/usr/bin/env bash
set -eu
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
cd "/home/ubuntu/m3dc1_runs/KPRAD_2D_48rank_official"
mpirun --oversubscribe -n 48 "/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d" -pc_factor_mat_solver_type mumps > C1stdout 2>&1
