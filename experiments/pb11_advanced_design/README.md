# PB11 Advanced Design Bridge

Lightweight surrogate studies for a DT-TCT compact tokamak with auxiliary edge/wall fuels, p-B11 vapor/wall reaction layers, direct conversion, RF/plasma-mirror controls, spin organization, graphene-backed heat spreading, dynamic volume compression, and guided edge-racetrack transport.

Primary entry point:

```bash
python m3dc1_tct_hybrid_bridge.py --no-sweeps
```

Recent high-value result files:

- `racetrack_replacement_penalized_full.txt`: best current full-DT hybrid after stricter hardware-recirculation penalties.
- `racetrack_forced_resonant_full.txt`: forced resonant racetrack comparison.
- `racetrack_replacement_penalized_half.txt`: reduced-DT / auxiliary-primary search.
- `racetrack_forced_resonant_half.txt`: forced resonant racetrack under reduced-DT conditions.
- `current_case_table.txt`: A-H baseline case table regenerated after the latest bridge updates.

Current surrogate conclusion:

- Pure/reference DT-TCT case F: net power proxy `8.639`, ignition margin proxy `9.024`.
- Best full-DT auxiliary hybrid: net `12.624`, ignition `12.184`, auxiliary gross `3.275`, auxiliary fraction `20.0%`, TBR `1.283`, liquid-lithium heat `2.666`, Be/B4C heat `2.354`.
- Forced resonant racetrack reduces physical recirculation from `100k` to about `15.7k` hardware passes and lowers wall heat, but remains slightly net-negative versus the unconstrained best.

This is a surrogate screening model, not a validated physics result. Use it to prioritize MHD/M3DC1 cases and sensitivity studies, not as a design claim.
