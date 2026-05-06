from pathlib import Path
import re

p = Path("run_radius_head_to_head.py")
if not p.exists():
    raise SystemExit("run_radius_head_to_head.py not found")

s = p.read_text(encoding="utf-8")

# Lower blanket thickness defaults wherever they appear plainly
s = re.sub(r'("blanket_thickness_cm"\s*:\s*)125\.0', r'\g<1>60.0', s)
s = re.sub(r"(blanket_thickness_cm\s*=\s*)125\.0", r"\g<1>60.0", s)

# Lower lithium thickness a bit if hard-coded
s = re.sub(r'("lithium_thickness_cm"\s*:\s*)0\.3', r'\g<1>0.15', s)
s = re.sub(r"(lithium_thickness_cm\s*=\s*)0\.3", r"\g<1>0.15", s)

# Replace the highly absorptive W_Ti_B4C blend with Be when it appears literally
s = s.replace("W_Ti_B4C_60_30_10_wt", "Be")

# If the common split appears literally, push less material toward the front
old_split = '[0.19047619047619047, 0.19047619047619047, 0.38095238095238093, 0.14285714285714285, 0.09523809523809523]'
new_split = '[0.10, 0.10, 0.30, 0.30, 0.20]'
s = s.replace(old_split, new_split)

p.write_text(s, encoding="utf-8")
print("patched run_radius_head_to_head.py")
