from pathlib import Path
import hashlib, json, urllib.request

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation_runs" / "tcabr_cache_materialization_audit"
OUT.mkdir(parents=True, exist_ok=True)

FILES = [
    {
        "name": "tcabr_data.nc",
        "url": "https://zenodo.org/records/21843354/files/tcabr_data.nc?download=1",
        "size": 4815231741,
        "md5": "0846b3ba681aacf623a1c883f9559e51",
    },
    {
        "name": "tcabr_tools.py",
        "url": "https://zenodo.org/records/21843354/files/tcabr_tools.py?download=1",
        "size": 26997,
        "md5": "7947a127dd75af53fab0dbcbab6ac64d",
    },
]

CACHE = ROOT / "validation_runs" / "tcabr_cache"
CACHE.mkdir(parents=True, exist_ok=True)

results = []
for spec in FILES:
    dest = CACHE / spec["name"]
    if not dest.exists() or dest.stat().st_size != spec["size"]:
        with urllib.request.urlopen(spec["url"]) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(8 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    h = hashlib.md5()
    with open(dest, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    actual_size = dest.stat().st_size
    actual_md5 = h.hexdigest()
    results.append({
        "name": spec["name"],
        "path": str(dest.relative_to(ROOT)),
        "expected_size": spec["size"],
        "actual_size": actual_size,
        "expected_md5": spec["md5"],
        "actual_md5": actual_md5,
        "size_match": actual_size == spec["size"],
        "md5_match": actual_md5 == spec["md5"],
    })

ok = all(x["size_match"] and x["md5_match"] for x in results)
summary = {
    "classification": "TCABR_CACHE_MATERIALIZATION_AUDITED" if ok else "TCABR_CACHE_MATERIALIZATION_INTEGRITY_NOT_ESTABLISHED",
    "pipeline_failure": False,
    "fuel_track": "fuel_agnostic_control",
    "machine": "TCABR",
    "source": "Zenodo 10.5281/zenodo.21843354",
    "files": results,
    "materialized": ok,
    "evidence_class": "observational_provenance",
    "actuator_budgets_ms": {"prebiased_fast": 2.75, "prebiased_nominal": 5.25},
    "claim_boundary": "TCABR corpus materialization/integrity only. No precursor timing, causal TCT suppression, segmented-electrode efficacy, native M3D-C1 validation, p-B11 physics, or reactor-scale inference.",
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
raise SystemExit(0 if ok else 3)
