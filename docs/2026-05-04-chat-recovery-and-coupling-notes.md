# 2026-05-04 Chat Recovery and Coupling Notes

## Context

This note captures the relevant recovery work from the ChatGPT session around the `fusion_engine_v5` / reactor optimizer stack. It is intended as a repo-side breadcrumb so the local Ubuntu working tree changes can be reconciled safely instead of relying on terminal history/screenshots.

The active local path during the session was:

```text
~/work/openmc/sweep
```

The main local files involved were:

```text
run_evo_reactor_search.py
fusion_engine_v5/engine/reactor_simulation.py
fusion_engine_v5/engine/lithium_wall.py
fusion_engine_v5/blanket/openmc_dataset_model.py
fusion_engine_v5/engine/reactor_simulation.py.bak
```

## Repo comparison status

The GitHub repo visible through the connector currently appears sparse compared with the local tree. Code search for the active runtime files did not find `run_evo_reactor_search.py`, `reactor_simulation.py`, or `openmc_dataset_model.py` in the remote repo. The repo does contain the high-level project docs, including `README.md` and docs under `docs/`.

Because the current working source files are only on the local Ubuntu machine, this note should be treated as a synchronization checklist rather than a replacement for committing the actual local `.py` files.

## What was restored / changed locally during chat

### 1. Restored module-coupled reactor simulation base

The earlier backup file:

```text
fusion_engine_v5/engine/reactor_simulation.py.bak
```

showed the more coupled version of the model, wired into:

```python
from .plasma_model import evaluate_case
from .tct_control import run_tct_controller
from .lithium_wall import lithium_wall_temperature, mhd_drag_power, pumping_power_from_heat
from .power_balance import plant_power_balance
from .engineering_limits import engineering_penalty
from ..blanket.openmc_dataset_model import evaluate_blanket
from ..blanket.openmc_runner import run_openmc_validation
```

The working direction was to use this as the base instead of continuing to patch a corrupted/indented version.

### 2. Fixed `mhd_drag_power()` signature mismatch

Observed real signature from `fusion_engine_v5/engine/lithium_wall.py`:

```python
def mhd_drag_power(B_T, velocity_m_s, conductivity_S_m, rho_kg_m3, half_width_m, wetted_area_m2=200.0):
```

The reactor simulation call needed to pass all required arguments, e.g.:

```python
mhd_power = mhd_drag_power(
    _safe_float(design.get("B0", 0.0)),
    _safe_float(design.get("lithium_velocity", 0.0)),
    1.0e6,
    500.0,
    0.05,
    200.0,
)
```

### 3. Added missing traceback import

`run_evo_reactor_search.py` used `traceback.format_exc()` in exception handling but did not import `traceback`.

Needed:

```python
import traceback
```

### 4. Disabled multiprocessing temporarily

Multiprocessing was causing noisy failures / import instability while debugging. The local search was patched from:

```python
evaluated = pool.map(evaluate, population)
```

to:

```python
evaluated = [evaluate(x) for x in population]
```

This was intentionally temporary for stable debugging. Re-enable parallelism only after the serial path is clean.

### 5. Relaxed hard feasibility gates

The restored coupled model was much harsher. The search initially produced zero feasible candidates every generation. HARD_LIMITS were loosened locally toward:

```python
HARD_LIMITS = {
    "TBR_min": 1.02,
    "wall_load_max": 20.0,
    "capex_max": 60.0,
    "net_electric_min": 200.0,
    "net_electric_max": 20000.0,
}
```

Also, hard penalties in `reactor_simulation.py` were relaxed from full-scale reactor assumptions, including roughly:

```python
if net_electric < 1500.0:
    hard_fail_penalty += 50000.0 + 500.0 * (1500.0 - net_electric)

if _safe_float(blanket["TBR"]) < 0.95:
    hard_fail_penalty += 100000.0 + 20000.0 * (0.95 - _safe_float(blanket["TBR"]))
```

### 6. Made empty history write safe

When no feasible candidates were collected, the run crashed writing `history[0].keys()`. The intended safe block is:

```python
if history:
    with open(OUTDIR / "history.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=history[0].keys())
        writer.writeheader()
        writer.writerows(history)
else:
    print("No feasible results collected — skipping CSV write.")
```

### 7. Disabled feasible-only filtering for recovery

To prevent reseeding forever, the feasible-only kill filter was replaced with logging:

```python
feasible_count = sum(1 for x in evaluated if x.get("feasible"))
print(f"GEN {gen:03d} | feasible={feasible_count}/{len(evaluated)}")
```

A later debug block printed failed evaluation errors when feasible count was zero.

### 8. Added schema compatibility for Pareto objectives

The optimizer expected an objective key named `R`, but newer/evaluation paths used revenue names such as `annual_revenue_musd`. Local patches added `R` compatibility in successful results / `extract_objectives()`.

The robust `extract_objectives()` direction was:

```python
def extract_objectives(item):
    r = item.get("result", {})
    d = item.get("design", {})

    defaults = {
        "net_electric": -1e18,
        "wall_load": 1e18,
        "raw_wall_load": 1e18,
        "TBR": 0.0,
        "capex_billion": 1e18,
        "bootstrap": 0.0,
        "R": 0.0,
        "a": 1e18,
        "B0": 1e18,
        "kappa": 1e18,
        "Ip": 1e18,
        "Ti": 1e18,
        "Te": 1e18,
        "H98": 1e18,
        "fG": 1e18,
        "frac_cap": 1e18,
        "lithium_thickness": 1e18,
        "blanket_thickness": 1e18,
        "lithium_velocity": 1e18,
        "reconn_trigger": 1e18,
        "conf_trigger": 1e18,
    }

    out = {}
    for key in OBJECTIVES.keys():
        if key == "R":
            val = r.get("R", r.get("annual_revenue_musd", 0.0))
        elif key in r:
            val = r.get(key, defaults.get(key, 1e18))
        elif key in d:
            val = d.get(key, defaults.get(key, 1e18))
        else:
            val = defaults.get(key, 1e18)

        try:
            out[key] = float(val)
        except Exception:
            out[key] = float(defaults.get(key, 1e18))

    return out
```

### 9. Made Pareto sorting key-safe

`dominates()` and `crowding_distance()` both had direct indexing into objectives and failed on missing `R`. They were patched toward key-safe versions that use defaults rather than `ao[key]`, `bo[key]`, or `population[i]["objectives"][key]`.

Important principle:

```python
obj.get(key, 0.0)  # for max objectives like R, bootstrap, TBR, net_electric
obj.get(key, 1e18) # for min objectives like wall_load/capex/etc.
```

### 10. Bootstrap tuple failure

The serial debug path exposed:

```text
TypeError: unsupported operand type(s) for *: 'float' and 'tuple'
```

at the score term involving `bootstrap_frac`. The intended fix was to normalize `bootstrap_frac` once upstream:

```python
bootstrap_frac = _safe_float(plasma.get("bootstrap_frac", 0.0), 0.0)
if isinstance(bootstrap_frac, tuple):
    bootstrap_frac = _safe_float(bootstrap_frac[0], 0.0)
```

and keep the score term plain:

```python
2000.0 * bootstrap_frac
```

## Report uploaded during chat

The user uploaded `tct_core_reactor_report_v15.md`. It documents the heuristic mapping v3 + wall physics evaluation. Important contents included:

- net electric mapping: `net_electric = 0.40 * pnet_mw`
- geometry scaling from net electric
- shape scaling from bootstrap
- wall modes: `solid_tungsten`, `tungsten_lithium_coated`, `static_liquid_lithium`, `flowing_liquid_lithium`, `advanced_liquid_lithium_blanket`
- controller realism profile with sensor noise, actuator lag, missed/false trigger probabilities, time evolution, and wall effect scaling
- clamp audit showing only `T_bar` hit clamps in that run
- reactor ranking tables showing liquid lithium wall modes, pass rates, wall load, wall temp, instability/burst metrics, density excess, and adjusted scores

Key interpretation from the report/chat:

The pipeline was no longer merely broken; it was exposing a physics/scaling problem. Many wall/TCT cases had good pass rates, but the density closure was demanding `n_bar_required` far above `n_bar_limit`, causing enormous penalties and collapsed adjusted scores. The next model work should focus on density closure, geometry scaling, and power target degradation instead of endless optimizer patches.

## Recommended next local actions

1. Commit the actual local code files from Ubuntu once stable:

```bash
cd ~/work/openmc/sweep
git status
git diff -- run_evo_reactor_search.py fusion_engine_v5/engine/reactor_simulation.py fusion_engine_v5/engine/lithium_wall.py fusion_engine_v5/blanket/openmc_dataset_model.py
git add run_evo_reactor_search.py fusion_engine_v5/engine/reactor_simulation.py fusion_engine_v5/engine/lithium_wall.py fusion_engine_v5/blanket/openmc_dataset_model.py
git commit -m "Recover coupled reactor search pipeline"
git push
```

2. Add/report output artifacts separately, preferably compressed and with large files excluded:

```bash
tar -czf evo_reactor_recovery_outputs.tar.gz evo_reactor_runs tct_core_reactor_report_v15.md
```

3. Fix density closure next. The immediate model issue is not the Pareto layer anymore; it is that the heuristic closure solves power by pushing density beyond the cap. Replace hard post-hoc density penalties with a pre-solve/early correction that clamps density and de-rates achievable pnet.

4. Do not re-enable multiprocessing until serial runs produce sane non-exception results.
