import math
import os
import subprocess
import tempfile
from pathlib import Path

try:
    import openmc
    OPENMC_OK = True
except Exception:
    openmc = None
    OPENMC_OK = False

from .geometry_builder import build_stack_case

def run_openmc_validation(design, plasma):
    if not OPENMC_OK:
        return None, "openmc_not_available"

    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        build_stack_case(design, run_dir)
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(max(1, os.cpu_count() or 1))

        try:
            p = subprocess.run(["openmc"], cwd=run_dir, capture_output=True, text=True, timeout=7200, env=env)
            if p.returncode != 0:
                return None, (p.stderr or p.stdout)[-1000:]

            sp_files = sorted(run_dir.glob("statepoint.*.h5"))
            if not sp_files:
                return None, "no_statepoint"

            sp = openmc.StatePoint(str(sp_files[-1]))
            flux = sp.get_tally(name="flux_mesh").mean.flatten()
            h3 = sp.get_tally(name="h3_prod_by_layer").mean.flatten()
            heat = sp.get_tally(name="heating_by_layer").mean.flatten()

            front = float(flux[0])
            back = float(flux[-1])
            attenuation = back / front if front > 0 else math.nan
            h3_total = float(sum(h3))
            heat_total = float(sum(heat))
            front_heating_frac = float(heat[0] / heat_total) if heat_total > 0 else 0.0

            result = {
                "TBR": h3_total,
                "attenuation": attenuation,
                "blanket_heat_mw": 0.8 * plasma["pfus_mw"] * (1.0 - min(max(attenuation, 0.0), 1.0)),
                "front_heating_frac": front_heating_frac,
                "model": "openmc",
            }
            return result, None
        except Exception as e:
            return None, str(e)
