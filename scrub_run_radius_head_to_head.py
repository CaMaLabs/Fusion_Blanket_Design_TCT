from pathlib import Path
import re

p = Path("run_radius_head_to_head.py")
s = p.read_text(encoding="utf-8")

lines = s.splitlines()

clean = []
skip = 0

for line in lines:
    if skip:
        skip -= 1
        continue

    # remove the bad dict fragment that got injected into plain code
    if '"blanket_thickness_cm": design.get("blanket_thickness_cm")' in line:
        continue

    # remove the bad output-integrity block if present
    if 'if "blanket_thickness_cm" not in result:' in line:
        skip = 3
        continue

    clean.append(line)

s = "\n".join(clean) + "\n"

# strip accidental duplicate blank lines
s = re.sub(r"\n{3,}", "\n\n", s)

p.write_text(s, encoding="utf-8")
print("scrubbed run_radius_head_to_head.py")
