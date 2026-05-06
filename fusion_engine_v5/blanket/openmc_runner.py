import math
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

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

        print("[RUN DEBUG] run_dir:", run_dir)
        print("[RUN DEBUG] files:", sorted(p.name for p in run_dir.iterdir()))

        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(max(1, os.cpu_count() or 1))

        try:
            p = subprocess.run(
                ["openmc"],
                cwd=run_dir,
                capture_output=True,
                text=True,
                timeout=7200,
                env=env,
            )

            if p.returncode != 0:
                return None, (p.stderr or p.stdout)[-1000:]

            sp_files = sorted(run_dir.glob("statepoint.*.h5"))
            if not sp_files:
                return None, "no_statepoint"

            sp = openmc.StatePoint(str(sp_files[-1]))

            flux = np.asarray(sp.get_tally(name="flux_mesh").mean).reshape(-1)
            h3 = np.asarray(sp.get_tally(name="h3_prod_by_layer").mean).reshape(-1)
            heat = np.asarray(sp.get_tally(name="heating_by_layer").mean).reshape(-1)

            print("[RUN DEBUG] flux size:", flux.size)
            print("[RUN DEBUG] h3 size:", h3.size)
            print("[RUN DEBUG] heat size:", heat.size)
            print("[RUN DEBUG] flux first 8:", flux[:8])
            print("[RUN DEBUG] flux last 8:", flux[-8:])

            if flux.size == 0:
                return None, "empty_flux_tally"

            n = len(flux)
            n_edge = max(1, min(4, n // 4 if n > 3 else 1))

            front = float(np.mean(flux[:n_edge]))
            back = float(np.mean(flux[-n_edge:]))

            # Preserve small but real differences.
            # 0 means no attenuation, 1 means full attenuation.
            if front > 1e-12:
                attenuation = max(0.0, min(1.0, 1.0 - (back / front)))
            else:
                attenuation = 0.0

            # Positive means flux decays outward.
            if n > 2:
                grad = float((flux[0] - flux[-1]) / max(abs(flux[0]), 1e-12))
            else:
                grad = 0.0

            # Extra debug using thirds so we can inspect shape directly.
            if n >= 3:
                inner = float(np.mean(flux[: max(1, n // 3)]))
                mid = float(np.mean(flux[max(1, n // 3): max(2, 2 * n // 3)]))
                outer = float(np.mean(flux[max(2, 2 * n // 3):]))
            else:
                inner = front
                mid = front
                outer = back

            h3_total = float(np.sum(h3))
            heat_total = float(np.sum(heat))
            front_heating_frac = float(heat[0] / heat_total) if heat_total > 0 and heat.size > 0 else 0.0

            print("[RUN DEBUG] inner/mid/outer:", inner, mid, outer)
            print("[RUN DEBUG] attenuation:", attenuation)
            print("[RUN DEBUG] gradient:", grad)
            print("[RUN DEBUG] h3_total:", h3_total)
            print("[RUN DEBUG] heat_total:", heat_total)
            print("[RUN DEBUG] front_heating_frac:", front_heating_frac)

            result = {
                "TBR": h3_total,
                "attenuation": attenuation,
                "gradient": grad,
                "blanket_heat_mw": 0.8 * plasma["pfus_mw"] * (1.0 - min(max(attenuation, 0.0), 1.0)),
                "front_heating_frac": front_heating_frac,
                "model": "openmc",
            }
            return result, None

        except Exception as e:
            return None, str(e)
