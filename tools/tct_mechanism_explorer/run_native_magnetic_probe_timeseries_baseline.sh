#!/usr/bin/env bash
set -euo pipefail
REPO="/home/ubuntu/work/openmc/sweep"
BASE="/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE"
OUT="$REPO/validation_runs/m3dc1_tct_native_magnetic_probe_timeseries_baseline"
mkdir -p "$OUT"
rm -rf "$OUT/run"
mkdir -p "$OUT/run"
cp -a "$BASE"/. "$OUT/run/"
cd "$OUT/run"
rm -f C1.h5 time_*.h5 probe_run.log
python3 - <<'PY'
from pathlib import Path
import re
p=Path('C1input')
s=p.read_text()
def put(key,val):
    global s
    pat=re.compile(rf'^(\s*{re.escape(key)}\s*=\s*)(.*?)(\s*(?:!.*)?$)',re.M)
    if pat.search(s): s=pat.sub(rf'\g<1>{val}\g<3>',s,count=1)
    else: s=s.replace('\n /',f'\n  {key} = {val}\n /',1)
put('imag_probes','1')
put('mag_probe_x(1)','2.3')
put('mag_probe_z(1)','0.0')
put('mag_probe_nx(1)','1.0')
p.write_text(s)
PY
BIN="${M3DC1_BIN:-}"
if [[ -z "$BIN" ]]; then
  for c in \
    /root/M3DC1/unstructured/_localgnu-petsc-opt-25/m3dc1_2d \
    /root/M3DC1/unstructured/build-mpich325/m3dc1_2d \
    /root/M3DC1/unstructured/build-openmpi319/m3dc1_2d \
    /home/ubuntu/M3DC1/unstructured/_localgnu-petsc-opt-25/m3dc1_2d \
    /home/ubuntu/M3DC1/unstructured/build-mpich325/m3dc1_2d \
    /home/ubuntu/M3DC1/unstructured/build-openmpi319/m3dc1_2d; do
    [[ -x "$c" ]] && BIN="$c" && break
  done
fi
if [[ -z "$BIN" ]]; then
  BIN="$(find /root/M3DC1 /home/ubuntu/M3DC1 -type f -name m3dc1_2d -perm -111 -print -quit 2>/dev/null || true)"
fi
[[ -n "$BIN" && -x "$BIN" ]] || { echo 'No local m3dc1_2d binary found after explicit and bounded discovery' >&2; exit 91; }
echo "Using M3D-C1 binary: $BIN" >&2
MPI="$(command -v mpiexec.mpich || command -v mpirun || true)"
[[ -n "$MPI" ]] || { echo 'No MPI launcher found' >&2; exit 92; }
set +e
"$MPI" -np 1 "$BIN" < C1input > probe_run.log 2>&1
RC=$?
set -e
python3 - "$RC" <<'PY'
from pathlib import Path
import json,sys
rc=int(sys.argv[1]); root=Path('.'); out=root.parent
summary={
 'classification':'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_TIMESERIES_BASELINE_CAPTURED' if rc==0 else 'M3DC1_TCT_NATIVE_MAGNETIC_PROBE_TIMESERIES_BASELINE_RUN_FAILED',
 'pipeline_failure': rc!=0,
 'return_code':rc,
 'diagnostic_only':True,
 'solver_physics_modified':False,
 'probe_configuration':{'imag_probes':1,'x':2.3,'z':0.0,'nx':1.0},
 'frozen_width_gate_pct_gt':0.020,
 'frozen_Jpk_gate_pct_le':0.10,
 'claim_boundary':'Normalized native M3D-C1 magnetic diagnostic capture only; no precursor lead-time, controller-efficacy, experimental, or reactor-scale claim.',
 'hdf5_files':[p.name for p in sorted(root.glob('*.h5'))],
 'log_tail':Path('probe_run.log').read_text(errors='replace')[-12000:] if Path('probe_run.log').exists() else ''
}
try:
 import h5py
 inv={}
 for p in sorted(root.glob('*.h5')):
  names=[]
  with h5py.File(p,'r') as h:
   h.visit(names.append)
  inv[p.name]=[n for n in names if any(k in n.lower() for k in ('probe','mag','bfield','br','bz','bphi'))]
 summary['magnetic_dataset_candidates']=inv
except Exception as e: summary['hdf5_inventory_error']=str(e)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
PY
exit "$RC"
