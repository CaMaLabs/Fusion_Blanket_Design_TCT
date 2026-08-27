# TCT Mechanism Explorer

A constrained mechanism-search harness for native M3D-C1 TCT studies.

The explorer **does not mutate M3D-C1 physics equations**. It searches an allowlisted
control layer: actuator family, sign, amplitude, geometry, timing, waveform, trigger-like
timing parameters, and combinations of already implemented native operators.

The default live profile targets the existing Ubuntu environment used by
`validation_runs/m3dc1_tct_*`:

- M3D-C1 checkout: `/home/ubuntu/M3DC1-official`
- baseline: `/home/ubuntu/m3dc1_runs/TCT_MECHANISM_BASELINE`
- executable: `/home/ubuntu/M3DC1-official/build-ubuntu-2d/unstructured/m3dc1_2d`
- run root: `/home/ubuntu/m3dc1_runs/TCT_EXPLORER`
- Spack env: `m3dc1-deps`

## What it searches

Initial mechanism families:

- `magnetic_pulse` — native `imag_control` / `mag_ctrl_*` operator
- `current_drive` — native `icd_source=1`
- `current_redistribution` — native `icd_source=4` center/shoulder redistribution
- `hybrid_mag_redistribution` — magnetic operator plus redistribution

Excluded from the evolvable layer by design:

- resistivity (`eta`)
- viscosity (`nu`)
- GEM perturbation seed (`eps`)
- initial sheet-width parameter (`gem_sheet_scale`)
- mesh, solver, and equilibrium physics
- arbitrary source-code mutation

A candidate is rejected before launch if it attempts to write a non-allowlisted
M3D-C1 input key.

## Evaluation ladder

Each candidate proceeds through increasingly expensive gates:

1. prepare/dry-run safety validation
2. zero-amplitude family equivalence
3. short impulse reachability
4. sheet-authority test
5. sustained-control test
6. topology/reconnection test
7. actuator-energy / net-current penalties
8. optional physical lithium mapping and Fiflis/Ruzic gate

Negative results are retained in the JSONL history.

## Install / pull

From the repository root:

```bash
git fetch origin
git switch agent/tct-mechanism-explorer
cd tools/tct_mechanism_explorer
```

No third-party Python packages are required for the search engine itself. Field
extraction uses `h5dump`; in the M3D-C1 environment activate Spack first.

```bash
source "$HOME/spack/share/spack/setup-env.sh"
spack env activate m3dc1-deps
```

Run unit tests:

```bash
python3 -m unittest discover -s tests -v
```

Create a starter config:

```bash
python3 -m tct_explorer.cli init --output explorer.json
```

Validate candidate generation without launching M3D-C1:

```bash
python3 -m tct_explorer.cli dry-run --config explorer.json --count 8
```

Verify zero-amplitude equivalence for every enabled mechanism family:

```bash
python3 -m tct_explorer.cli verify-zero --config explorer.json
```

Run a small live search:

```bash
python3 -m tct_explorer.cli search \
  --config explorer.json \
  --population 8 \
  --generations 4 \
  --seed 8776
```

Resume from the same output directory:

```bash
python3 -m tct_explorer.cli search \
  --config explorer.json \
  --population 8 \
  --generations 8 \
  --seed 8776 \
  --resume
```

## Optional agent supervisor

The numerical search is deterministic without an LLM. An optional supervisor
can propose mechanism-family weights or bounded candidate genomes between
generations.

Set `agent.command` in the config to a local command. The explorer sends one JSON
document on stdin and expects one JSON document on stdout:

```json
{
  "mechanism_weights": {
    "magnetic_pulse": 2.0,
    "current_redistribution": 0.5
  },
  "proposals": [
    {
      "mechanism": "magnetic_pulse",
      "params": {
        "amp": -0.01,
        "t_on": 0.10,
        "duration": 0.05
      }
    }
  ],
  "notes": "favor time-localized magnetic candidates"
}
```

Agent proposals are validated against the same mechanism registry and numeric
bounds as evolutionary mutations. The agent cannot introduce new C1input keys.

## Ruzic/Fiflis constraint

The explorer can call the repository's canonical
`liquid_lithium_stability.ruzic_fiflis_2016` implementation when a **physical**
mapping from the normalized M3D-C1 command to local `ΔB` has been supplied.

By default this mapping is disabled and candidates are marked
`LITHIUM_DIMENSIONAL_TRANSFER_UNRESOLVED`. The tool never inserts normalized
M3D-C1 amplitudes directly into the Ruzic equations.

The Ruzic gate is a reduced surface-retention/ejection screen, not proof of
liquid-lithium-to-plasma actuator transfer or reactor survivability.

## Outputs

Under `search.output_dir`:

- `history.jsonl` — every evaluated candidate, including failures
- `checkpoint.json` — generation and RNG state
- `pareto_front.json` — non-dominated candidates
- `mechanism_stats.json` — success/failure counts by family
- `runs/<candidate-id>/<stage>/` — generated C1input, launch command, compact metrics
- `agent/` — supervisor request/response records when enabled

Each evaluation records hashes of generated inputs, executable path, baseline
path, stage, return code, and extracted metrics.

## Claim boundary

This is a computational mechanism-discovery and controller-search harness. A
good candidate is evidence that a particular native M3D-C1 control mapping
produces favorable behavior in the tested case. It is not experimental
validation, reactor stabilization, ELM suppression, lithium-current transfer
validation, ignition proof, or net-power validation.
