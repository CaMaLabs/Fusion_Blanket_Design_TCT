from pathlib import Path
import re

targets = ["verify_candidate_openmc.py", "run_radius_head_to_head.py"]

for fname in targets:
    p = Path(fname)
    if not p.exists():
        continue

    s = p.read_text()

    # find output dict construction
    pattern = r"(\{[^{}]*\"net_electric\"[^{}]*\})"

    def repl(m):
        block = m.group(1)
        if "blanket_thickness_cm" not in block:
            block = block.rstrip("}") + ', "blanket_thickness_cm": design.get("blanket_thickness_cm")}'
        return block

    s = re.sub(pattern, repl, s, flags=re.DOTALL)

    p.write_text(s)
    print("patched:", fname)
