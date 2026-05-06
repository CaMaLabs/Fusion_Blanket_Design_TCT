from pathlib import Path

p = Path("run_radius_head_to_head.py")
s = p.read_text()

needle = "results.append("

if needle in s:
    s = s.replace(
        needle,
        """# enforce required fields
if "blanket_thickness_cm" not in result:
    result["blanket_thickness_cm"] = design.get("blanket_thickness_cm")

results.append("""
    )

p.write_text(s)
print("patched output integrity")
