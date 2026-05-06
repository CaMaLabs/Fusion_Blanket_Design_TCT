from pathlib import Path

p = Path("radius_sweep_top.py")
s = p.read_text()

needle = "base_rows = extract_rows(payload)"

if needle not in s:
    raise SystemExit("base_rows assignment not found")

replacement = '''base_rows = extract_rows(payload)

    # normalize OpenMC-specific field names into the generic names used below
    aliased_rows = []
    for r in base_rows:
        if isinstance(r, dict):
            rr = dict(r)

            if "ATTN_openmc" in rr and "attenuation" not in rr:
                rr["attenuation"] = rr["ATTN_openmc"]
            if "GRAD_openmc" in rr and "gradient" not in rr:
                rr["gradient"] = rr["GRAD_openmc"]
            if "TBR_openmc" in rr and "tbr" not in rr:
                rr["tbr"] = rr["TBR_openmc"]

            # keep uppercase aliases too, in case later code expects them
            if "attenuation" in rr and "ATTN" not in rr:
                rr["ATTN"] = rr["attenuation"]
            if "gradient" in rr and "GRAD" not in rr:
                rr["GRAD"] = rr["gradient"]
            if "tbr" in rr and "TBR" not in rr:
                rr["TBR"] = rr["tbr"]

            aliased_rows.append(rr)
        else:
            aliased_rows.append(r)
    base_rows = aliased_rows
'''

s = s.replace(needle, replacement, 1)
p.write_text(s)
print("patched OpenMC field aliasing")
