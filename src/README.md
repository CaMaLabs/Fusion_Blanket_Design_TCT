# Source Directory

Use this directory for cleaned scripts that can be run by another person.

Promotion rule: a script should only be placed here after it has:

- a clear purpose
- deterministic inputs or documented random seeds
- simple command-line or notebook instructions
- no hard-coded personal paths
- no secrets or credentials
- output paths that do not overwrite important files without warning

Suggested future structure:

```text
src/
  tct/
    run_tct_threshold_study.py
    plot_three_check_verification.py
  reactor/
    evaluate_case.py
    run_density_sweep.py
  openmc/
    build_openmc_model.py
    run_openmc_case.py
```

Keep exploratory notebooks in `archive/` until they are converted into reproducible scripts.
