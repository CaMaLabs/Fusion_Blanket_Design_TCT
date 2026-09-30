#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TCABR NetCDF Toolbox
A set of utility functions for working with TCABR Dataset NetCDF files.

Version: 1.0.0
Date: 2026-08-09
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from netCDF4 import Dataset
from typing import Union, List, Optional, Tuple
import os


def get_disruption_time(netcdf_path: str, shot_id: int) -> str:
    """
    Get the disruption time for a specific shot from a NetCDF file.
    
    Parameters:
    - netcdf_path: Path to the NetCDF file
    - shot_id: Shot number (e.g., 15842)
    
    Returns:
    - String with disruption time in ms if disruptive, or "There were no disruption in this shot" if normal
    """
    if not os.path.exists(netcdf_path):
        return f"Error: File {netcdf_path} not found"
    
    try:
        with Dataset(netcdf_path, 'r') as nc:
            shot_name = str(shot_id)
            
            if shot_name not in nc.groups:
                return f"Error: Shot {shot_id} not found in NetCDF file"
            
            grp = nc.groups[shot_name]
            
            # Get shot_type attribute
            shot_type = getattr(grp, 'shot_type', 'Unknown')
            
            if shot_type == "Normal":
                return "There were no disruption in this shot"
            elif shot_type == "Disruptive":
                disruption_time = getattr(grp, 'disruption_time', None)
                if disruption_time is not None:
                    return disruption_time
                else:
                    return "There were no disruption in this shot"
            else:
                return f"Error: Unknown shot type '{shot_type}'"
                
    except Exception as e:
        return f"Error: {str(e)}"


def get_signal_data(netcdf_path: str, shot_id: int, 
                   diagnostics: Union[str, List[str]], 
                   raw: bool = False) -> pd.DataFrame:
    """
    Get processed data for specified diagnostics from a shot.
    
    Parameters:
    - netcdf_path: Path to the NetCDF file
    - shot_id: Shot number (e.g., 15842)
    - diagnostics: Single diagnostic name or list of diagnostic names
    - raw: If True, returns raw data (without sigscale). If False, returns calibrated data (data * sigscale)
    
    Returns:
    - DataFrame with columns: each diagnostic has its own time column and data column
      Format: {diag_name}_time_ms, {diag_name}_value
    """
    if not os.path.exists(netcdf_path):
        raise FileNotFoundError(f"File {netcdf_path} not found")
    
    # Convert single diagnostic to list
    if isinstance(diagnostics, str):
        diagnostics = [diagnostics]
    
    with Dataset(netcdf_path, 'r') as nc:
        shot_name = str(shot_id)
        
        if shot_name not in nc.groups:
            raise ValueError(f"Shot {shot_id} not found in NetCDF file")
        
        grp = nc.groups[shot_name]
        
        # Store data for each diagnostic with its own time vector
        result_data = {}
        max_length = 0
        
        for diag_name in diagnostics:
            if diag_name not in grp.variables:
                print(f"Warning: Diagnostic '{diag_name}' not found in shot {shot_id}")
                continue
            
            signal_var = grp.variables[diag_name]
            
            # Get raw data
            raw_data = signal_var[:]
            
            # Get sigscale
            sigscale = getattr(signal_var, 'sigscale', 1.0)
            
            # Apply sigscale if not raw
            if raw:
                data = raw_data
            else:
                data = raw_data * sigscale
            
            # Get time vector from dimension
            time_array = None
            if len(signal_var.dimensions) > 0:
                dim_name = signal_var.dimensions[0]
                if dim_name in grp.variables:
                    time_var = grp.variables[dim_name]
                    time_us = time_var[:]  # Time in microseconds
                    time_ms = time_us / 1000  # Convert to ms
                    time_array = time_ms
            
            if time_array is None:
                print(f"Warning: No time vector found for {diag_name}")
                continue
            
            # Store both time and data
            result_data[diag_name] = {
                'time': time_array,
                'data': data
            }
            
            # Track maximum length for alignment (if needed)
            max_length = max(max_length, len(time_array))
        
        if not result_data:
            raise ValueError(f"No valid diagnostics found for shot {shot_id}")
        
        # Create DataFrame with separate columns for each diagnostic
        # Each diagnostic gets its own time and value columns
        df_dict = {}
        
        for diag_name, diag_info in result_data.items():
            time_col = f"{diag_name}_time_ms"
            data_col = f"{diag_name}_value"
            
            # Ensure arrays are 1D
            time_vals = diag_info['time'].flatten() if diag_info['time'].ndim > 1 else diag_info['time']
            data_vals = diag_info['data'].flatten() if diag_info['data'].ndim > 1 else diag_info['data']
            
            df_dict[time_col] = time_vals
            df_dict[data_col] = data_vals
        
        # Create DataFrame
        df = pd.DataFrame(df_dict)
        
        # If there are multiple diagnostics, align by index (row number)
        # Each diagnostic keeps its own time vector
        # If lengths differ, rows will have NaN for missing values
        if len(diagnostics) > 1:
            # Pad shorter arrays with NaN to match the longest
            max_len = max(len(df) for col in df.columns if col.endswith('_time_ms'))
            
            for col in df.columns:
                if len(df[col]) < max_len:
                    pad_len = max_len - len(df[col])
                    df[col] = np.concatenate([df[col].values, np.full(pad_len, np.nan)])
        
        return df

def generate_histograms(netcdf_path: str, 
                       diagnostics: Union[str, List[str]],
                       time_window: Tuple[float, float] = (60.0, 100.0),
                       shot_type: Optional[str] = None,
                       output_dir: str = '.',
                       bins: Union[str, int] = 'fd',
                       xlim: Optional[Tuple[float, float]] = None,
                       filename_prefix: str = 'histogram'):
    """
    Generate histogram plots for specified diagnostics across all shots.
    
    Parameters:
    - netcdf_path: Path to the NetCDF file
    - diagnostics: Single diagnostic name or list of diagnostic names
    - time_window: Tuple (t_min, t_max) in ms for computing mean (default: 60.0, 100.0)
    - shot_type: Filter by shot type ('Normal', 'Disruptive', or None for all)
    - output_dir: Directory to save the histograms
    - bins: Number of bins or binning method (default: 'fd')
    - xlim: Optional tuple (xmin, xmax) for x-axis limits
    - filename_prefix: Prefix for output filenames
    
    Returns:
    - Dictionary with diagnostic names as keys and lists of mean values as values
    """
    if not os.path.exists(netcdf_path):
        raise FileNotFoundError(f"File {netcdf_path} not found")
    
    # Convert single diagnostic to list
    if isinstance(diagnostics, str):
        diagnostics = [diagnostics]
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    t_min, t_max = time_window
    all_means = {diag: [] for diag in diagnostics}
    total_shots = 0
    shots_with_data = {diag: 0 for diag in diagnostics}
    
    print(f"Processing histograms for: {', '.join(diagnostics)}")
    print(f"Time window: {t_min} - {t_max} ms")
    print(f"Shot type filter: {shot_type if shot_type else 'All'}")
    
    with Dataset(netcdf_path, 'r') as nc:
        # Get all shot groups
        shot_names = list(nc.groups.keys())
        total_shots = len(shot_names)
        print(f"Total shots in file: {total_shots}")
        
        for shot_name in shot_names:
            grp = nc.groups[shot_name]
            
            # Check shot type filter
            if shot_type is not None:
                current_type = getattr(grp, 'shot_type', None)
                if current_type != shot_type:
                    continue
            
            # Process each diagnostic
            for diag_name in diagnostics:
                if diag_name not in grp.variables:
                    continue
                
                signal_var = grp.variables[diag_name]
                
                # Get data and sigscale
                raw_data = signal_var[:]
                sigscale = getattr(signal_var, 'sigscale', 1.0)
                data = raw_data * sigscale
                
                # Get time vector
                if len(signal_var.dimensions) == 0:
                    continue
                
                dim_name = signal_var.dimensions[0]
                if dim_name not in grp.variables:
                    continue
                
                time_var = grp.variables[dim_name]
                time_us = time_var[:]  # Time in microseconds
                time_ms = time_us / 1000  # Convert to ms
                
                # Find indices within time window
                mask = (time_ms >= t_min) & (time_ms <= t_max)
                
                if np.any(mask):
                    mean_val = np.mean(data[mask])
                    all_means[diag_name].append(mean_val)
                    shots_with_data[diag_name] += 1
    
    # Generate histograms
    print("\nGenerating histograms...")
    results = {}
    
    for diag_name in diagnostics:
        means = all_means[diag_name]
        n_shots = shots_with_data[diag_name]
        
        if len(means) == 0:
            print(f"  Warning: No data found for {diag_name}")
            results[diag_name] = np.array([])
            continue
        
        # Convert to numpy array
        means_array = np.array(means)
        results[diag_name] = means_array
        
        # Create histogram
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.hist(means_array, bins=bins, color='blue', alpha=0.7, edgecolor='black')
        
        # Set title and labels
        shot_type_str = f"{shot_type} " if shot_type else ""
        ax.set_title(f"Distribution of mean {diag_name} - {shot_type_str}Shots ({t_min}-{t_max} ms)", fontsize=12)
        ax.set_xlabel(f"Mean {diag_name}", fontsize=11)
        ax.set_ylabel("Counts", fontsize=11)
        ax.grid(True, alpha=0.3)
        
        # Set x-axis limits if provided
        if xlim is not None:
            ax.set_xlim(xlim)
        
        # Add statistics
        stats_text = f"n = {len(means_array)}\nmean = {np.mean(means_array):.4f}\nstd = {np.std(means_array):.4f}"
        ax.text(0.95, 0.95, stats_text, transform=ax.transAxes,
                ha='right', va='top', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Save figure
        shot_type_suffix = f"_{shot_type}" if shot_type else ""
        filename = f"{filename_prefix}_{diag_name}{shot_type_suffix}.png"
        filepath = os.path.join(output_dir, filename)
        
        plt.tight_layout()
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"  Saved: {filepath} ({len(means_array)} shots)")
    
    return results

def monte_carlo_analysis(netcdf_path: str,
                         output_dir: str = '.',
                         n_iter: int = 10000,
                         sigma_main: float = 0.10,
                         sigma_levels: List[float] = [0.02, 0.05, 0.10],
                         min_criteria: int = 4,
                         t_start: float = 0.050,
                         t_end: float = 0.100,
                         diag_ip: str = 'IPlasma',
                         diag_vloop: str = 'VLoop',
                         diag_mirnov: str = 'BbMirnovN01',
                         seed: int = 42,
                         chunk: int = 1000):
    """
    Perform Monte Carlo sensitivity analysis for disruption labels.
    
    Extracts features from NetCDF, perturbs thresholds with Gaussian noise,
    and calculates P(disruptive) for each shot.
    
    Parameters:
    - netcdf_path: Path to NetCDF file
    - output_dir: Directory to save results (default: '.')
    - n_iter: Number of Monte Carlo iterations (default: 10000)
    - sigma_main: Sigma for main figure (default: 0.10)
    - sigma_levels: List of sigma values for sensitivity sweep (default: [0.02, 0.05, 0.10])
    - min_criteria: Number of criteria that must be met (1-4, default: 4)
    - t_start: Flat-top start time in seconds (default: 0.050)
    - t_end: Flat-top end time in seconds (default: 0.100)
    - diag_ip: Name of plasma current diagnostic (default: 'IPlasma')
    - diag_vloop: Name of loop voltage diagnostic (default: 'VLoop')
    - diag_mirnov: Name of Mirnov diagnostic (default: 'BbMirnovN01')
    - seed: Random seed for reproducibility (default: 42)
    - chunk: Iterations per chunk for memory safety (default: 1000)
    
    Returns:
    - Dictionary with results: {'df': DataFrame, 'p_dis': array, 'category': array}
    
    Outputs:
    - shot_mc_results.csv: Per-shot P(disruptive) + category
    - mc_label_robustness.pdf/png: 3-panel figure
    - Console table: Label sensitivity vs sigma
    """
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print("="*60)
    print("MONTE CARLO SENSITIVITY ANALYSIS")
    print("="*60)
    print(f"NetCDF: {netcdf_path}")
    print(f"Window: {t_start*1000:.0f}-{t_end*1000:.0f} ms")
    print(f"Mirnov: {diag_mirnov}")
    print(f"Min criteria: {min_criteria}")
    print(f"Iterations: {n_iter}")
    print("="*60)
    
    # ============================================================
    # STEP 1: Extract features from NetCDF
    # ============================================================
    print("\n[1/4] Extracting features from NetCDF...")
    
    # Nominal thresholds
    T_NOM = {
        "dIp_dt": -50.0,      # kA/ms
        "delta": 30.0,        # %
        "Vloop": 5.0,         # V
        "mirnov": 5.0         # x background
    }
    
    FEAT_COLS = ["min_dIp_dt", "max_delta_Ip_pct", "max_Vloop", "max_mirnov_ratio"]
    
    def _get_signal_data(shot_group, signal_name):
        """Extract physical data and time vector from NetCDF group."""
        if signal_name not in shot_group.variables:
            return None, None
        
        signal_var = shot_group.variables[signal_name]
        raw_data = signal_var[:]
        sigscale = getattr(signal_var, 'sigscale', 1.0)
        
        if len(signal_var.dimensions) == 0:
            return None, None
        
        dim_name = signal_var.dimensions[0]
        if dim_name not in shot_group.variables:
            return None, None
        
        time_var = shot_group.variables[dim_name]
        time_us = time_var[:]
        time_s = time_us * 1e-6
        
        return raw_data * sigscale, time_s
    
    def _process_shot(shot_group, shot_id):
        """Extract 4 features from a single shot."""
        ip, t_ip = _get_signal_data(shot_group, diag_ip)
        vloop, t_vloop = _get_signal_data(shot_group, diag_vloop)
        mirnov, t_mirnov = _get_signal_data(shot_group, diag_mirnov)
        
        if ip is None or vloop is None or mirnov is None:
            return None
        
        mask_ip = (t_ip >= t_start) & (t_ip <= t_end)
        mask_vloop = (t_vloop >= t_start) & (t_vloop <= t_end)
        mask_mirnov = (t_mirnov >= t_start) & (t_mirnov <= t_end)
        
        if np.sum(mask_ip) < 10 or np.sum(mask_vloop) < 10 or np.sum(mask_mirnov) < 10:
            return None
        
        ip_ft = ip[mask_ip]
        vloop_ft = vloop[mask_vloop]
        mirnov_ft = mirnov[mask_mirnov]
        
        # Feature 1: min_dIp_dt (kA/ms)
        dt_ip = t_ip[1] - t_ip[0] if len(t_ip) > 1 else 1e-6
        dIp_dt = np.gradient(ip_ft, dt_ip)
        min_dIp_dt = np.min(dIp_dt / 1000.0)
        
        # Feature 2: max_delta_Ip_pct (%)
        ip_nom = np.mean(ip_ft)
        if ip_nom > 10:
            max_delta_ip_pct = np.max(((ip_nom - ip_ft) / ip_nom) * 100.0)
        else:
            max_delta_ip_pct = 0.0
        
        # Feature 3: max_Vloop (V)
        max_vloop = np.max(vloop_ft)
        
        # Feature 4: max_mirnov_ratio (x background)
        bg_mask = (t_mirnov >= t_start) & (t_mirnov < (t_start + 0.010))
        if np.sum(bg_mask) > 0:
            mirnov_bg = np.mean(np.abs(mirnov[bg_mask]))
            if mirnov_bg > 1e-6:
                mirnov_ratio = np.max(np.abs(mirnov_ft)) / mirnov_bg
            else:
                mirnov_ratio = 0.0
        else:
            mirnov_ratio = 0.0
        
        # Determine label from shot_type attribute
        shot_type = getattr(shot_group, 'shot_type', 'Unknown')
        label = 1 if shot_type == 'Disruptive' else 0
        
        return {
            'shot_id': shot_id,
            'label_original': label,
            'min_dIp_dt': min_dIp_dt,
            'max_delta_Ip_pct': max_delta_ip_pct,
            'max_Vloop': max_vloop,
            'max_mirnov_ratio': mirnov_ratio
        }
    
    # Extract features
    results = []
    shots_skipped = 0
    
    with Dataset(netcdf_path, 'r') as nc:
        shot_ids = list(nc.groups.keys())
        print(f"  Total shots: {len(shot_ids)}")
        
        for i, shot_id in enumerate(shot_ids):
            if (i + 1) % 500 == 0:
                print(f"  Extracted {i+1}/{len(shot_ids)} shots...")
            
            shot_group = nc.groups[shot_id]
            result = _process_shot(shot_group, int(shot_id))
            
            if result is not None:
                results.append(result)
            else:
                shots_skipped += 1
    
    df = pd.DataFrame(results)
    n = len(df)
    
    print(f"  Extracted: {n} shots")
    print(f"  Skipped: {shots_skipped} shots")
    print(f"  Disruptive: {df['label_original'].sum()}")
    print(f"  Normal: {n - df['label_original'].sum()}")
    
    if n == 0:
        raise ValueError("No data extracted from NetCDF file!")
    
    # ============================================================
    # STEP 2: Define helper functions for Monte Carlo
    # ============================================================
    print("\n[2/4] Running Monte Carlo simulation...")
    
    def _rule_counts(f, T, min_criteria):
        """Number of criteria met (vectorized)."""
        c = (f["min_dIp_dt"].values < T["dIp_dt"]).astype(np.int8)
        c += (f["max_delta_Ip_pct"].values > T["delta"])
        c += (f["max_Vloop"].values > T["Vloop"])
        c += (f["max_mirnov_ratio"].values > T["mirnov"])
        return c
    
    def _monte_carlo(f, sigma, n_iter, rng, min_criteria):
        """P(disruptive) per shot under Gaussian threshold perturbation."""
        counts = np.zeros(n, dtype=np.int32)
        for s in range(0, n_iter, chunk):
            m = min(chunk, n_iter - s)
            if sigma == 0:
                c = _rule_counts(f, T_NOM, min_criteria)[:, None]
            else:
                T1 = rng.normal(T_NOM["dIp_dt"], abs(T_NOM["dIp_dt"]) * sigma, m)
                T2 = rng.normal(T_NOM["delta"], T_NOM["delta"] * sigma, m)
                T3 = rng.normal(T_NOM["Vloop"], T_NOM["Vloop"] * sigma, m)
                T4 = rng.normal(T_NOM["mirnov"], T_NOM["mirnov"] * sigma, m)
                c = (f["min_dIp_dt"].values[:, None] < T1[None, :]).astype(np.int8)
                c += (f["max_delta_Ip_pct"].values[:, None] > T2[None, :])
                c += (f["max_Vloop"].values[:, None] > T3[None, :])
                c += (f["max_mirnov_ratio"].values[:, None] > T4[None, :])
            counts += (c >= min_criteria).sum(axis=1)
        return counts / n_iter
    
    rng = np.random.default_rng(seed)
    
    # Nominal rule vs curated labels
    nom_label = (_rule_counts(df, T_NOM, min_criteria) >= min_criteria).astype(int)
    tp = int(((nom_label == 1) & (df["label_original"] == 1)).sum())
    fp = int(((nom_label == 1) & (df["label_original"] == 0)).sum())
    fn = int(((nom_label == 0) & (df["label_original"] == 1)).sum())
    tn = int(((nom_label == 0) & (df["label_original"] == 0)).sum())
    
    print(f"  Nominal rule vs curated labels: TP={tp} FP={fp} FN={fn} TN={tn}")
    if (tp + fn) > 0 and (tn + fp) > 0:
        print(f"    Sensitivity: {tp/(tp+fn):.2%}, Specificity: {tn/(tn+fp):.2%}")
    
    # Main Monte Carlo run
    print(f"  Running with sigma={sigma_main:.0%}...")
    p_dis = _monte_carlo(df, sigma_main, n_iter, rng, min_criteria)
    
    P_LOW, P_HIGH = 0.05, 0.95
    cat = np.select([p_dis < P_LOW, p_dis > P_HIGH],
                    ["Non-disruptive", "Disruptive"], default="Ambiguous")
    n_amb = int((cat == "Ambiguous").sum())
    n_nd = int((cat == "Non-disruptive").sum())
    n_d = int((cat == "Disruptive").sum())
    
    print(f"  Robust normal: {n_nd} | Ambiguous: {n_amb} ({n_amb/n:.2%}) | Robust disruptive: {n_d}")
    
    # ============================================================
    # STEP 3: Sensitivity sweep
    # ============================================================
    print("\n[3/4] Performing sensitivity sweep...")
    
    rows = []
    for sg in sigma_levels:
        p = _monte_carlo(df, sg, n_iter, rng, min_criteria)
        amb = int(((p > P_LOW) & (p < P_HIGH)).sum())
        flip = int((p.round() != nom_label).sum())
        rows.append([f"{sg:.0%}", amb, f"{amb/n:.2%}", flip])
    
    tab = pd.DataFrame(rows, columns=["sigma", "ambiguous shots", "fraction", "majority-flipped"])
    print("\nSensitivity of labels to threshold uncertainty:")
    print(tab.to_string(index=False))
    
    # ============================================================
    # STEP 4: Save results and generate figures
    # ============================================================
    print("\n[4/4] Saving results and generating figures...")
    
    # Save CSV
    df["p_dis"] = p_dis
    df["category"] = cat
    csv_path = os.path.join(output_dir, "shot_mc_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"  Saved: {csv_path}")
    
    # Generate figure
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "axes.linewidth": 0.8
    })
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))
    
    # Panel (a): Histogram of P(dis)
    ax1.hist(p_dis, bins=50, color="#2171B5", edgecolor="white", linewidth=0.5)
    ax1.axvspan(P_LOW, P_HIGH, color="#D9D9D9", alpha=0.4, zorder=0)
    ax1.axvline(P_LOW, color="#CB181D", ls="--", lw=1.2)
    ax1.axvline(P_HIGH, color="#CB181D", ls="--", lw=1.2)
    ax1.set_xlabel("Probability of disruption classification ($P_{dis}$)")
    ax1.set_ylabel("Number of discharges")
    ax1.set_title(f"(a) Label confidence (sigma={sigma_main:.0%})")
    ax1.text(0.5, 0.92, f"Robust: {100*(n_nd+n_d)/n:.1f}%  |  Ambiguous: {100*n_amb/n:.1f}%",
             transform=ax1.transAxes, ha="center", fontsize=9,
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#2171B5", alpha=0.85))
    
    # Panel (b): Sensitivity sweep
    fr = [100 * r[1] / n for r in rows]
    ax2.plot([s*100 for s in sigma_levels], fr, "o-", color="#CB181D", lw=1.5)
    ax2.set_xlabel("Threshold uncertainty sigma (%)")
    ax2.set_ylabel("Ambiguous shots (%)")
    ax2.set_title("(b) Sensitivity sweep")
    ax2.grid(alpha=0.3)
    
    fig.tight_layout()
    
    pdf_path = os.path.join(output_dir, "mc_label_robustness.pdf")
    png_path = os.path.join(output_dir, "mc_label_robustness.png")
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    
    print(f"  Saved: {pdf_path}")
    print(f"  Saved: {png_path}")
    
    print("\n" + "="*60)
    print("MONTE CARLO ANALYSIS COMPLETED!")
    print("="*60)
    
    return {'df': df, 'p_dis': p_dis, 'category': cat}

# ============================================================
# Example usage
# ============================================================
if __name__ == "__main__":
    # Example 1: Get disruption time
    print("="*60)
    print("Example 1: Get disruption time")
    print("="*60)
    result = get_disruption_time('tcabr_data.nc', 15842)
    print(f"Shot 15842: {result}")
    
    # Example 2: Get signal data
    print("\n" + "="*60)
    print("Example 2: Get signal data (calibrated)")
    print("="*60)
    df = get_signal_data('tcabr_data.nc', 15842, ['IPlasma', 'VLoop'])
    print(df.head())
    
    print("\n" + "="*60)
    print("Example 3: Get signal data (raw)")
    print("="*60)
    df_raw = get_signal_data('tcabr_data.nc', 15842, ['IPlasma', 'VLoop'], raw=True)
    print(df_raw.head())
    
    # Example 3: Generate histograms
    print("\n" + "="*60)
    print("Example 4: Generate histograms")
    print("="*60)
    
    # Histograms for all shots
    generate_histograms(
        'tcabr_data.nc',
        ['IPlasma', 'VLoop'],
        time_window=(60, 100),
        output_dir='histograms',
        filename_prefix='all'
    )
    
    # Histograms for disruptive shots only
    generate_histograms(
        'tcabr_data.nc',
        ['IPlasma', 'VLoop'],
        time_window=(60, 100),
        shot_type='Disruptive',
        output_dir='histograms',
        filename_prefix='disruptive'
    )
    
    # Histograms for normal shots only
    generate_histograms(
        'tcabr_data.nc',
        ['IPlasma', 'VLoop'],
        time_window=(60, 100),
        shot_type='Normal',
        output_dir='histograms',
        filename_prefix='normal'
    )
    
    # Monte Carlo analysis
    print("\n" + "="*60)
    print("Monte Carlo Analysis")
    print("="*60)
    monte_carlo_analysis('tcabr_data.nc')

    print("\n" + "="*60)
    print("All examples completed successfully!")
    print("="*60)