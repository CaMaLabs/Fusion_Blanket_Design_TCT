#!/usr/bin/env python3
"""Repair the source=0 restart transport audit with the documented HDF5 payload."""
from __future__ import annotations
import json, re, shutil
from pathlib import Path
import pulse_train_audit as pta
import restart_transport_audit as audit

TIME_RE = re.compile(r"^time_(\d+)\.h5$")
REPAIR_TAG = "documented_C1_plus_selected_plot_slice"


def remove_target(path: Path) -> None:
    if not (path.exists() or path.is_symlink()):
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_item(source: Path, target: Path) -> None:
    remove_target(target)
    if source.is_symlink():
        target.symlink_to(source.readlink())
    elif source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


def restart_plot(previous: Path) -> tuple[Path, int, float]:
    krows = pta.c1ke(previous)
    if not krows:
        raise RuntimeError(f"{previous}: missing C1ke rows; cannot select restart plot")
    last = krows[-1]
    ntime = int(round(float(last["ntime"])))
    physical_time = float(last["time"])
    candidate = previous / f"time_{ntime:03d}.h5"
    if candidate.exists():
        return candidate, ntime, physical_time
    candidates = []
    for path in previous.glob("time_*.h5"):
        match = TIME_RE.match(path.name)
        if match:
            candidates.append((int(match.group(1)), path))
    if not candidates:
        raise RuntimeError(f"{previous}: no time_*.h5 restart plot exists")
    plot_index, path = max(candidates, key=lambda item: item[0])
    if plot_index != ntime:
        raise RuntimeError(
            f"{previous}: C1ke final ntime={ntime} but final plot is {path.name}; "
            "ntimepr=1 audit requires exact agreement"
        )
    return path, plot_index, physical_time


def copy_restart(previous: Path, current: Path) -> dict:
    c1_source = previous / "C1.h5"
    if not c1_source.exists():
        raise RuntimeError(f"missing restart source {c1_source}")
    selected_plot, plot_index, physical_time = restart_plot(previous)
    copied, skipped = [], []
    for item in sorted(previous.iterdir(), key=lambda p: p.name):
        if item.name in audit.EXECUTION_FILES or item.name == "C1ke":
            skipped.append(item.name)
            continue
        if TIME_RE.match(item.name):
            skipped.append(item.name)
            continue
        copy_item(item, current / item.name)
        copied.append(item.name)
    selected_target = current / selected_plot.name
    copy_item(selected_plot, selected_target)
    copied.append(selected_plot.name)
    c1_target = current / "C1.h5"
    if not c1_target.exists():
        raise RuntimeError("restart payload did not include C1.h5")
    seed_plots = sorted(p.name for p in current.glob("time_*.h5"))
    if seed_plots != [selected_plot.name]:
        raise RuntimeError("restart target must contain exactly selected seed plot; got " + ", ".join(seed_plots))
    input_path = current / "C1input"
    text = input_path.read_text()
    text = pta.replace_or_add(text, "iread_hdf5", "1")
    text = pta.replace_or_add(text, "irestart", "1")
    text = pta.replace_or_add(text, "irestart_slice", str(plot_index))
    input_path.write_text(text)
    manifest = {
        "source_directory": str(previous),
        "source_C1_sha256": audit.sha256(c1_source),
        "seed_C1_sha256": audit.sha256(c1_target),
        "selected_plot_file": selected_plot.name,
        "selected_plot_index": plot_index,
        "selected_plot_time": physical_time,
        "source_plot_sha256": audit.sha256(selected_plot),
        "seed_plot_sha256": audit.sha256(selected_target),
        "copied": copied,
        "skipped": skipped,
        "policy": "C1.h5 + exactly selected final time_nnn.h5 + support state; C1ke/older plots excluded",
    }
    audit.dump(current / "restart_seed_manifest.json", manifest)
    return manifest


def extract(directory: Path) -> list[dict[str, float]]:
    h5 = pta.H5()
    krows = pta.c1ke(directory)
    flux = h5.data(directory / "C1.h5", "/scalars/Reconnected_Flux")
    out = []
    for local_index, krow in enumerate(krows):
        ntime = int(round(float(krow.get("ntime", local_index))))
        time_file = directory / f"time_{ntime:03d}.h5"
        if not time_file.exists():
            raise RuntimeError(
                f"{directory}: C1ke ntime={ntime} has no {time_file.name}; refusing positional matching"
            )
        flux_index = ntime if 0 <= ntime < len(flux) else local_index
        row = {
            "time": float(krow["time"]),
            "magnetic_energy": float(krow["emagp"] + krow["emagt"] + krow["emag3"]),
            "Reconnected_Flux": float(flux[flux_index]) if 0 <= flux_index < len(flux) else float("nan"),
        }
        row.update(audit.profile(h5, time_file))
        out.append(row)
    return out


def annotate_summary(rc: int) -> None:
    summary = audit.OUT / "restart_transport_summary.json"
    if not summary.exists():
        return
    report = json.loads(summary.read_text())
    report.setdefault("audit", {})["restart_policy"] = (
        "documented HDF5 restart: C1.h5 + selected time_nnn.h5; explicit iread_hdf5=1, irestart_slice=N"
    )
    report["restart_transport_repair"] = {
        "tag": REPAIR_TAG,
        "base_return_code": rc,
        "seed_plot_is_restart_state": True,
        "fresh_output_pairing": "C1ke ntime -> time_{ntime:03d}.h5",
        "older_plot_slices_copied": False,
    }
    audit.dump(summary, report)


def main() -> int:
    audit.copy_restart = copy_restart
    audit.extract = extract
    rc = audit.main()
    annotate_summary(rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
