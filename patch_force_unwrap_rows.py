from pathlib import Path

p = Path("radius_sweep_top.py")
s = p.read_text()

needle = "base_rows = extract_rows(payload)"

if needle not in s:
    raise SystemExit("base_rows assignment not found")

replacement = '''base_rows = extract_rows(payload)

    # 🔥 force unwrap nested result layer
    new_rows = []
    for r in base_rows:
        if isinstance(r, dict) and "result" in r and isinstance(r["result"], dict):
            new_rows.append(r["result"])
        else:
            new_rows.append(r)
    base_rows = new_rows
'''

s = s.replace(needle, replacement, 1)
p.write_text(s)

print("patched base_rows unwrapping")
