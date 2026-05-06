from pathlib import Path
import re

p = Path("radius_sweep_top.py")
s = p.read_text()

# inject unwrap right after function start
pattern = r"(def expand_row_for_radius\(.*?\):\n)"
match = re.search(pattern, s)

if not match:
    raise SystemExit("expand_row_for_radius not found")

insert = '''
    # unwrap nested result if present
    if isinstance(base_row, dict) and "result" in base_row:
        base_row = base_row["result"]
'''

s = s.replace(match.group(1), match.group(1) + insert)
p.write_text(s)

print("patched row unwrapping")
