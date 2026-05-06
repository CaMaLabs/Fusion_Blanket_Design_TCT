#!/usr/bin/env python3
from pathlib import Path
import re
import shutil
import sys

TARGET = Path("fusion_engine_v5/engine/reactor_simulation.py")


def must_replace(text: str, pattern: str, repl: str, desc: str) -> str:
    new_text, n = re.subn(pattern, repl, text, flags=re.MULTILINE | re.DOTALL)
    if n != 1:
        raise RuntimeError(f"Expected exactly 1 match for {desc}, got {n}")
    return new_text


def main() -> None:
    if not TARGET.exists():
        print(f"[!] File not found: {TARGET}")
        sys.exit(1)

    original = TARGET.read_text(encoding="utf-8")
    backup = TARGET.with_suffix(TARGET.suffix + ".bak_event_severity")
    shutil.copy2(TARGET, backup)
    print(f"[+] Backup written: {backup}")

    text = original

    # 1) Add severity-aware net electric correction immediately after raw net_electric is read.
    text = must_replace(
        text,
        r'''(?P<block>
rid_penalty\s*=\s*0\.0\s*\n
net_electric\s*=\s*_safe_float\(plant\.get\("net_electric",\s*0\.0\),\s*0\.0\)\s*\n
if\s+net_electric\s*>\s*0\.0:\s*\n
\s+rid_penalty\s*\+=\s*2500\.0\s*\*\s*max\(0\.0,\s*500\.0\s*-\s*net_electric\)\s*\*\*\s*2\s*\n
if\s+rid_penalty\s*<\s*4\.0e7:\s*\n
\s+rid_penalty\s*=\s*ADJ\(0\.0,\s*\(2500\.0\s*-\s*net_electric\)\s*\)\s*\n
if\s+rid_penalty\s*>\s*1\.5\s*\*\s*\(net_electric\s*-\s*4000\.0\)\s*:
\s+rid_penalty\s*\+=\s*1\.5\s*\*\s*\(net_electric\s*-\s*4000\.0\)\s*
)''',
        r'''rid_penalty = 0.0
net_electric_raw = _safe_float(plant.get("net_electric", 0.0), 0.0)

# ------------------------------------------------------------------
# Event-severity-weighted power accounting
# Old behavior effectively punished raw event/fail activity too hard.
# New behavior ties pnet reduction to BOTH event frequency and severity.
# ------------------------------------------------------------------
fail_rate = _safe_float(mc.get("fail_rate", 0.0), 0.0)

# Prefer explicit severity if present; otherwise derive a bounded proxy.
event_severity = _safe_float(mc.get("damage_per_event", 0.0), None)
if event_severity is None:
    # Lower TCT/plasma stability => more severe events.
    stability = _safe_float(tct.get("stability", 1.0), 1.0)
    tct_used = _safe_float(tct.get("used", 0.0), 0.0)
    # Severity proxy stays bounded and nonzero when instability exists.
    event_severity = max(0.02, min(1.0, 1.0 - stability + 0.10 * tct_used))

# Normalize microscopic damage-per-event values into a usable multiplier if needed.
if event_severity < 1.0e-3:
    event_severity = min(1.0, max(0.02, event_severity * 1.0e5))

# Frequency × severity controls electrical penalty, not frequency alone.
event_loss_frac = max(0.0, min(0.60, 0.35 * fail_rate * event_severity))
net_electric = max(0.0, net_electric_raw * (1.0 - event_loss_frac))

if net_electric > 0.0:
    rid_penalty += 2500.0 * max(0.0, 500.0 - net_electric) ** 2
if rid_penalty < 4.0e7:
    rid_penalty += max(0.0, 2500.0 - net_electric)
if net_electric > 4000.0:
    rid_penalty += 1.5 * (net_electric - 4000.0)
''',
        "net_electric block",
    )

    # 2) Replace the old hard fail-rate score penalty with a softer, non-duplicative one.
    text = must_replace(
        text,
        r'''-\s*2000\.0\s*\*\s*_safe_float\(mc\.get\("fail_rate",\s*0\.0\),\s*0\.0\)''',
        r'''- 200.0 * _safe_float(mc.get("fail_rate", 0.0), 0.0)''',
        "score fail_rate penalty",
    )

    # 3) Surface the adjusted accounting in outputs.
    text = must_replace(
        text,
        r'''("Annual_cost_musd":\s*float\(annual_cost_musd\),\s*\n)''',
        r'''\1        "Net_electric_raw": float(net_electric_raw),
        "Event_severity": float(event_severity),
        "Event_loss_frac": float(event_loss_frac),
''',
        "result output block",
    )

    TARGET.write_text(text, encoding="utf-8")
    print(f"[+] Patched: {TARGET}")
    print("[+] Done. Re-run your optimizer/sim and compare Net_electric_raw vs adjusted outputs.")


if __name__ == "__main__":
    main()

