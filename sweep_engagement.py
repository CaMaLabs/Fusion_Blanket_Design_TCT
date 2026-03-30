#!/usr/bin/env python3
"""
Sweep Engagement Triggers - DT_TCT_v8
Grid search over trigger thresholds, outputs compact CSV
"""
import argparse, json, os
import pandas as pd
import numpy as np
from dt_tct_simulation import run_ab_test

def _unpack_run_ab_test(ret):
    """Unpack run_ab_test return - handles both Option A (3-tuple) and Option B (2-tuple)."""
    if not isinstance(ret, tuple):
        raise ValueError(f"run_ab_test returned {type(ret)}")
    if len(ret) == 2:
        (no_sum, tct_sum) = ret[0]
        (no_tail, tct_tail) = ret[1]
        return no_sum, tct_sum, no_tail, tct_tail, None, None
    if len(ret) >= 3:
        (no_sum, tct_sum) = ret[0]
        (no_tail, tct_tail) = ret[1]
        df_pair = ret[2]
        if isinstance(df_pair, tuple) and len(df_pair) == 2:
            no_df, tct_df = df_pair
        else:
            no_df, tct_df = None, None
        return no_sum, tct_sum, no_tail, tct_tail, no_df, tct_df
    raise ValueError(f"Unsupported return len={len(ret)}")

def compute_validation_metrics(tct_df):
    """Compute additional validation metrics from per-sample dataframe."""
    if tct_df is None or len(tct_df) == 0:
        return {}
    
    corr_pp = np.corrcoef(tct_df["burst_precursor"], tct_df["p_burst"])[0, 1] if "burst_precursor" in tct_df and "p_burst" in tct_df else np.nan
    corr_pb = np.corrcoef(tct_df["p_burst"], tct_df["burst"])[0, 1] if "p_burst" in tct_df and "burst" in tct_df else np.nan
    
    return {
        "corr_precursor_pburst": float(corr_pp) if not np.isnan(corr_pp) else None,
        "corr_pburst_burst": float(corr_pb) if not np.isnan(corr_pb) else None
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base_params", default="params_example.json")
    ap.add_argument("--kwargs", default="controller_kwargs_example.json")
    ap.add_argument("--label", default="DT_TCT_v8_ENG")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--n_samples", type=int, default=5000)
    args = ap.parse_args()

    with open(args.base_params, "r", encoding="utf-8") as f:
        base_params = json.load(f)
    with open(args.kwargs, "r", encoding="utf-8") as f:
        base_kwargs = json.load(f)
    
    base_kwargs["n_samples"] = args.n_samples

    # Trigger grids
    reconn_grid = [0.55, 0.60, 0.65, 0.70]
    conf_grid   = [0.55, 0.60, 0.65, 0.70]
    rad_grid    = [0.60, 0.65, 0.70, 0.75, 0.80]
    margin_grid = [0.15, 0.08, 0.04, 0.02, 0.01]

    rows = []
    idx = 0
    total_runs = len(reconn_grid) * len(conf_grid) * len(rad_grid) * len(margin_grid)
    
    print(f"Starting sweep: {total_runs} configurations...")
    
    for reconn_trigger in reconn_grid:
        for conf_trigger in conf_grid:
            for rad_trigger in rad_grid:
                for margin_trigger in margin_grid:
                    kw = dict(base_kwargs)
                    kw.update({
                        "reconn_trigger": float(reconn_trigger),
                        "conf_trigger": float(conf_trigger),
                        "rad_trigger": float(rad_trigger),
                        "margin_trigger": float(margin_trigger),
                    })

                    ret = run_ab_test(base_params, kw, label_prefix=f"{args.label}_{idx:04d}")
                    no_sum, tct_sum, no_tail, tct_tail, _, tct_df = _unpack_run_ab_test(ret)
                    
                    # Compute validation metrics
                    val_metrics = compute_validation_metrics(tct_df)

                    rows.append({
                        "idx": idx,
                        "reconn_trigger": reconn_trigger,
                        "conf_trigger": conf_trigger,
                        "rad_trigger": rad_trigger,
                        "margin_trigger": margin_trigger,
                        "tct_pass_rate": tct_sum.get("pass_rate"),
                        "tct_fail_pnet": tct_sum.get("fail_pnet_rate"),
                        "tct_burst_rate": tct_sum.get("burst_rate"),
                        "tct_pnet_p05": tct_sum.get("pnet_p05"),
                        "tct_pnet_p50": tct_sum.get("pnet_p50"),
                        "tct_pnet_p95": tct_sum.get("pnet_p95"),
                        "tct_tail_burst_frac": tct_tail.get("burst_frac_in_tail") if isinstance(tct_tail, dict) else None,
                        "corr_precursor_pburst": val_metrics.get("corr_precursor_pburst"),
                        "corr_pburst_burst": val_metrics.get("corr_pburst_burst"),
                    })
                    idx += 1

    df = pd.DataFrame(rows)
    os.makedirs(args.outdir, exist_ok=True)
    out_csv = os.path.join(args.outdir, f"{args.label}_sweep.csv")
    df.to_csv(out_csv, index=False)

    # Sort by optimization targets: max pass_rate, min fail_pnet, min burst_rate
    best = df.sort_values(
        ["tct_pass_rate", "tct_fail_pnet", "tct_burst_rate"], 
        ascending=[False, True, True]
    ).head(10)
    
    print("\n" + "="*80)
    print("TOP 10 CONFIGURATIONS (sorted by: max pass_rate, min fail_pnet, min burst_rate)")
    print("="*80)
    print(best[["idx", "reconn_trigger", "conf_trigger", "rad_trigger", "margin_trigger",
                "tct_pass_rate", "tct_fail_pnet", "tct_burst_rate", "tct_pnet_p05"]].to_string(index=False))
    print(f"\nWrote full sweep results to: {out_csv}")

if __name__ == "__main__":
    main()
