from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "run_liquid_lithium_stability.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_liquid_lithium_stability", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_liquid_lithium_matrix_schema_and_regressions():
    module = _load_module()
    rows = module.run_matrix()
    summary = module._summarize(rows, duration=8.0)
    module._run_regression_checks(summary)

    assert summary["status"] == "REDUCED_MODEL_PRIORITIZATION_ONLY"
    assert summary["scenario_count"] >= 14
    assert summary["best_scenario"] == "combined_porous_microtexture_plasma"

    by_name = {row["scenario"]: row for row in rows}
    assert by_name["combined_porous_microtexture_plasma"]["regime_label"] == "stable"
    assert by_name["falsification_high_heat_flux_vapor_blanketing"]["regime_label"] == "vapor-film dominated"
    assert by_name["falsification_plasma_shear_too_weak"]["regime_label"] != "stable"
