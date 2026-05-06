from pathlib import Path
import re

p = Path("run_radius_head_to_head.py")
if not p.exists():
    raise SystemExit("run_radius_head_to_head.py not found")

s = p.read_text(encoding="utf-8")

# 1) Remove the broken fragment if it was injected into plain code
s = s.replace('"blanket_thickness_cm": design.get("blanket_thickness_cm")}', '')
s = s.replace(", 'blanket_thickness_cm': design.get('blanket_thickness_cm')}", "")
s = s.replace(', "blanket_thickness_cm": 60.0}', "}")

# 2) Clean up any accidental duplicate blank lines caused by patching
s = re.sub(r'\n{3,}', '\n\n', s)

# 3) Safely propagate thickness right before results.append(result)
needle = "results.append(result)"
replacement = '''if "blanket_thickness_cm" not in result:
        result["blanket_thickness_cm"] = (
            design.get("blanket_thickness_cm")
            if isinstance(design, dict) else None
        )
    results.append(result)'''

if needle in s and replacement not in s:
    s = s.replace(needle, replacement, 1)

p.write_text(s, encoding="utf-8")
print("repaired run_radius_head_to_head.py")
