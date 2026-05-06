from pathlib import Path
import re

p = Path("run_radius_head_to_head.py")
s = p.read_text()

# inject thickness into every design
pattern = r"(design\s*=\s*\{[^}]+\})"

def repl(m):
    block = m.group(1)
    if "blanket_thickness_cm" not in block:
        block = block.rstrip("}") + ', "blanket_thickness_cm": 60.0}'
    return block

s = re.sub(pattern, repl, s, flags=re.DOTALL)

p.write_text(s)
print("patched: forced blanket_thickness_cm into candidates")
