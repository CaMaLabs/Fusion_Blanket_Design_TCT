#!/usr/bin/env python3
"""Inventory native M3D-C1 magnetic diagnostics for TCT precursor work.

This is a read-only provenance/diagnostic audit.  It does not modify M3D-C1,
the baseline, or controller physics.  The goal is to identify native magnetic
probe / Mirnov-like signals that can support a simulation-native precursor
instead of mapping FAIR-MAST absolute milliseconds into an unrelated short
Taylor-reconnection characterization window.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import h5py

BASE = Path("/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE")
H5 = BASE / "C1.h5"
C1INPUT = BASE / "C1input"
REPO = Path("/home/ubuntu/work/openmc/sweep")
OUT = REPO / "validation_runs/m3dc1_tct_native_magnetic_diagnostic_inventory"

KEYWORDS = (
    "mag",
    "probe",
    "mirnov",
    "bfield",
    "b_field",
    "bphi",
    "br",
    "bz",
    "flux",
    "toroidal",
)
MAX_CANDIDATES = 250


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def _json_scalar(value):
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        if len(value) <= 16:
            return [_json_scalar(v) for v in value]
    except Exception:
        pass
    return str(value)


def _attrs(obj) -> dict:
    return {str(k): _json_scalar(v) for k, v in obj.attrs.items()}


def _sample_dataset(ds: h5py.Dataset) -> dict:
    out = {"shape": list(ds.shape), "dtype": str(ds.dtype), "attrs": _attrs(ds)}
    try:
        if ds.shape == ():
            out["sample"] = _json_scalar(ds[()])
        elif ds.ndim == 1 and ds.shape[0] > 0:
            n = ds.shape[0]
            out["sample_first"] = [_json_scalar(v) for v in ds[: min(3, n)]]
            out["sample_last"] = [_json_scalar(v) for v in ds[max(0, n - 3) : n]]
        elif ds.ndim > 1 and all(s > 0 for s in ds.shape):
            first = tuple(0 for _ in ds.shape)
            last = tuple(s - 1 for s in ds.shape)
            out["sample_first_element"] = _json_scalar(ds[first])
            out["sample_last_element"] = _json_scalar(ds[last])
    except Exception as exc:
        out["sample_error"] = str(exc)
    return out


def _candidate(name: str, attrs: dict | None = None) -> bool:
    haystack = name.lower()
    if attrs:
        haystack += " " + " ".join(f"{k}={v}" for k, v in attrs.items()).lower()
    return any(key in haystack for key in KEYWORDS)


def _probe_input_lines() -> list[str]:
    if not C1INPUT.exists():
        return []
    lines = []
    for raw in C1INPUT.read_text(errors="replace").splitlines():
        clean = raw.strip()
        if re.search(r"(?i)(imag_probes|mag_probe|mirnov|flux_loop)", clean):
            lines.append(clean)
    return lines


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not H5.exists():
        write_json(
            OUT / "summary.json",
            {
                "classification": "M3DC1_TCT_NATIVE_MAGNETIC_DIAGNOSTIC_INVENTORY_MISSING_BASELINE_H5",
                "pipeline_failure": False,
                "h5_path": str(H5),
            },
        )
        return 0

    all_datasets: list[str] = []
    candidate_datasets: list[dict] = []
    candidate_groups: list[dict] = []

    with h5py.File(H5, "r") as h5:
        root_attrs = _attrs(h5)

        def visitor(name: str, obj) -> None:
            if isinstance(obj, h5py.Dataset):
                all_datasets.append(name)
                attrs = _attrs(obj)
                if _candidate(name, attrs) and len(candidate_datasets) < MAX_CANDIDATES:
                    item = {"path": name}
                    item.update(_sample_dataset(obj))
                    candidate_datasets.append(item)
            elif isinstance(obj, h5py.Group):
                attrs = _attrs(obj)
                if _candidate(name, attrs) and len(candidate_groups) < MAX_CANDIDATES:
                    candidate_groups.append(
                        {
                            "path": name,
                            "attrs": attrs,
                            "members_preview": list(obj.keys())[:50],
                        }
                    )

        h5.visititems(visitor)

    # Preserve the full path inventory separately so follow-up code can inspect
    # naming conventions without making the summary enormous.
    write_json(
        OUT / "hdf5_dataset_paths.json",
        {
            "h5_path": str(H5),
            "dataset_count": len(all_datasets),
            "dataset_paths": sorted(all_datasets),
        },
    )

    probe_lines = _probe_input_lines()
    classification = (
        "M3DC1_TCT_NATIVE_MAGNETIC_DIAGNOSTIC_CANDIDATES_FOUND"
        if candidate_datasets or candidate_groups or probe_lines
        else "M3DC1_TCT_NATIVE_MAGNETIC_DIAGNOSTIC_CANDIDATES_NOT_FOUND"
    )
    summary = {
        "classification": classification,
        "pipeline_failure": False,
        "audit_scope": "Read-only inventory of native M3D-C1 magnetic/probe diagnostics for simulation-native TCT precursor construction.",
        "claim_boundary": "Diagnostic/provenance inventory only; no precursor performance or controller-efficacy claim.",
        "baseline": {
            "directory": str(BASE),
            "h5_path": str(H5),
            "c1input_path": str(C1INPUT),
            "root_attrs": root_attrs,
        },
        "c1input_probe_config": probe_lines,
        "dataset_count": len(all_datasets),
        "candidate_dataset_count": len(candidate_datasets),
        "candidate_group_count": len(candidate_groups),
        "candidate_datasets": candidate_datasets,
        "candidate_groups": candidate_groups,
        "next_step_contract": (
            "Use only a physically identified native magnetic diagnostic as a precursor input. "
            "Do not silently substitute Jpk/dJdt or FAIR-MAST absolute milliseconds."
        ),
    }
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
