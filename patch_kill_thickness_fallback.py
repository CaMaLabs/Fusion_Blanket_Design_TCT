from pathlib import Path

for fname in Path(".").glob("*.py"):
    s = fname.read_text()

    if 'blanket_thickness_cm", 125.0' in s:
        s = s.replace(
            'cfg["blanket_thickness_cm"]',
            'cfg["blanket_thickness_cm"]'
        )
        fname.write_text(s)
        print("patched:", fname)
