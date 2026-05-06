from pathlib import Path
import json

ROOT = Path("/home/chase/work/openmc_recovery")
PKG = ROOT / "jorek_campaign_package"

run_plan_json = PKG / "jorek_run_plan_merged.json"
out_dir = PKG / "jorek_postprocess_skeletons"
out_dir.mkdir(parents=True, exist_ok=True)

if not run_plan_json.exists():
    raise SystemExit(f"Missing required file: {run_plan_json}")

with run_plan_json.open("r", encoding="utf-8") as f:
    run_plan = json.load(f)

COMMON_SCRIPT = '''\
import json
from pathlib import Path


def load_case_outputs(case_dir: Path) -> dict:
    """
    TODO:
    Replace this with actual loading/parsing of JOREK outputs for the case.
    Return a dict of arrays / traces / diagnostics needed for postprocessing.
    """
    raise NotImplementedError("Replace with actual JOREK output loader")


def detect_events(data: dict,
                  event_detector_primary: str,
                  event_amplitude_threshold: float,
                  heat_pulse_threshold: float,
                  minimum_event_separation_steps: int):
    """
    TODO:
    Use actual JOREK variable names and time traces.

    Should return a list of event windows or event indices.
    """
    raise NotImplementedError("Replace with actual event detection logic")


def extract_elm_crash_amplitude(data: dict, events):
    """
    TODO:
    Compute crash amplitude for each detected event.
    """
    raise NotImplementedError


def extract_elm_energy_loss_per_event(data: dict, events):
    """
    TODO:
    Integrate energy change across each detected event.
    """
    raise NotImplementedError


def extract_peak_divertor_heat_flux(data: dict, target_surface: str):
    """
    TODO:
    Compute max target heat flux over time / events on selected target surface.
    """
    raise NotImplementedError


def extract_wetted_area(data: dict, target_surface: str, threshold_fraction_of_peak: float):
    """
    TODO:
    Compute wetted area above threshold on target surface.
    """
    raise NotImplementedError


def extract_elm_frequency(data: dict, events, total_runtime: float | None = None):
    """
    TODO:
    Compute ELM/event frequency using consistent normalization.
    """
    raise NotImplementedError


def extract_stability_window_shift(baseline_metrics: dict, case_metrics: dict):
    """
    TODO:
    Define comparison rule for stability window shift vs baseline.
    """
    raise NotImplementedError


def build_metrics(case_dir: Path, config: dict) -> dict:
    data = load_case_outputs(case_dir)

    events = detect_events(
        data=data,
        event_detector_primary=config["event_detector_primary"],
        event_amplitude_threshold=float(config["event_amplitude_threshold"]),
        heat_pulse_threshold=float(config["heat_pulse_threshold"]),
        minimum_event_separation_steps=int(config["minimum_event_separation_steps"]),
    )

    metrics = {
        "case_name": config["case_name"],
        "event_count": len(events),
        "elm_crash_amplitude": extract_elm_crash_amplitude(data, events),
        "elm_energy_loss_per_event": extract_elm_energy_loss_per_event(data, events),
        "peak_divertor_heat_flux": extract_peak_divertor_heat_flux(
            data,
            target_surface=config["target_surface"],
        ),
        "wetted_area": extract_wetted_area(
            data,
            target_surface=config["target_surface"],
            threshold_fraction_of_peak=float(config["wetted_area_threshold_fraction_of_peak"]),
        ),
        "elm_frequency": extract_elm_frequency(data, events),
    }

    return metrics


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", required=True, help="Directory containing outputs for this case")
    parser.add_argument("--config-json", required=True, help="Per-case postprocessing config json")
    parser.add_argument("--out", required=True, help="Output metrics json path")
    args = parser.parse_args()

    case_dir = Path(args.case_dir)
    config_path = Path(args.config_json)
    out_path = Path(args.out)

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    metrics = build_metrics(case_dir, config)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
'''

index = []

for case in run_plan["cases"]:
    case_name = case["case_name"]

    case_cfg = {
        "case_name": case_name,
        "event_detector_primary": case.get("event_detector_primary", ""),
        "event_amplitude_threshold": case.get("event_amplitude_threshold", ""),
        "heat_pulse_threshold": case.get("heat_pulse_threshold", ""),
        "minimum_event_separation_steps": case.get("minimum_event_separation_steps", ""),
        "target_surface": case.get("target_surface", ""),
        "peak_heat_flux_statistic": case.get("peak_heat_flux_statistic", ""),
        "wetted_area_threshold_fraction_of_peak": case.get("wetted_area_threshold_fraction_of_peak", ""),
        "extract_elm_crash_amplitude": case.get("extract_elm_crash_amplitude", ""),
        "extract_elm_energy_loss_per_event": case.get("extract_elm_energy_loss_per_event", ""),
        "extract_peak_divertor_heat_flux": case.get("extract_peak_divertor_heat_flux", ""),
        "extract_wetted_area": case.get("extract_wetted_area", ""),
        "extract_elm_frequency": case.get("extract_elm_frequency", ""),
        "extract_stability_window_shift": case.get("extract_stability_window_shift", ""),
    }

    cfg_path = out_dir / f"{case_name}_postprocess_config.json"
    py_path = out_dir / f"{case_name}_postprocess.py"
    md_path = out_dir / f"{case_name}_postprocess.md"

    cfg_path.write_text(json.dumps(case_cfg, indent=2), encoding="utf-8")
    py_path.write_text(COMMON_SCRIPT, encoding="utf-8")

    md_lines = [
        f"# {case_name} postprocessing skeleton",
        "",
        "## Purpose",
        "Placeholder parser/extractor for this JOREK case.",
        "",
        "## Config",
    ]
    for k, v in case_cfg.items():
        md_lines.append(f"- {k}: {v}")
    md_lines += [
        "",
        "## Replace these first",
        "- actual JOREK output loader",
        "- actual event detector variable names",
        "- actual target surface / heat-flux variable names",
        "- actual energy-loss extraction logic",
        "- actual stability-window comparison logic",
    ]
    md_path.write_text("\\n".join(md_lines), encoding="utf-8")

    index.append({
        "case_name": case_name,
        "config_json": str(cfg_path),
        "script_py": str(py_path),
        "notes_md": str(md_path),
    })

summary_json = out_dir / "index.json"
summary_md = out_dir / "README.md"

with summary_json.open("w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

readme = [
    "# JOREK Postprocessing Skeletons",
    "",
    "Per-case placeholder postprocessing scripts and configs.",
    "These are not runnable against real JOREK output until variable names and loaders are replaced.",
    "",
]
for item in index:
    readme.append(f'- {item["case_name"]}')
    readme.append(f'  - config: {item["config_json"]}')
    readme.append(f'  - script: {item["script_py"]}')
    readme.append(f'  - notes: {item["notes_md"]}')

summary_md.write_text("\\n".join(readme), encoding="utf-8")

print("Wrote:")
print(" -", summary_json)
print(" -", summary_md)
for item in index:
    print(" -", item["config_json"])
    print(" -", item["script_py"])
    print(" -", item["notes_md"])
