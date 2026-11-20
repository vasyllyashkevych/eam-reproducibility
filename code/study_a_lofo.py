#!/usr/bin/env python3
"""Supplementary leave-one-drift-dimension-out (LOFO) analysis for PAPER021433, Study A.

Run: python3 code/study_a_lofo.py   (about 3 s; writes docs/results/study_a_lofo/*.csv, docs/figures/fig5a_study_a_lofo_radar.png and docs/figures/fig5b_study_a_lofo_paired_ci.png).
This script does not modify experimental data or the original source scripts.
It reuses controlled_drift.py and multidrift_eval.py, the calibrated C0 classifier,
training seeds 101-110, evaluation seeds 1-40, and nine named drift dimensions.
For each dimension, it masks that dimension (NaN), renormalizes the EDI weights,
removes its contribution to CriticalCheck, and recalibrates state thresholds.
"""
import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def analyze(code_dir: Path, out_dir: Path, fig_dir: Path):
    sys.path.insert(0, str(code_dir.resolve()))
    import controlled_drift as cd
    from controlled_drift import md

    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    y = md.true_states()
    train = [cd.ref_indicators(cd.generate(seed)) for seed in cd.TRAIN]
    test = [cd.ref_indicators(cd.generate(seed)) for seed in cd.TEST]
    names = cd.NAMES

    def score(data, removed):
        d = data.copy()
        if removed is not None:
            d[:, removed] = np.nan
        return md.risk(cd.edi(d)), d

    def evaluate(removed, th=None):
        if th is None:
            th = md.calibrate([score(d, removed)[0] for d in train], [y] * len(train))
        rows = []
        for seed, data in zip(cd.TEST, test):
            risk_score, dim_scores = score(data, removed)
            pred = cd.override(md.classify(risk_score, th), dim_scores)
            rows.append({'seed': seed, 'macro_f1': md.macro_f1(y, pred), 'accuracy': float(np.mean(y == pred))})
        return th, pd.DataFrame(rows)

    original_thresholds, full = evaluate(None)
    baseline = float(full.macro_f1.mean())
    assert abs(baseline - 0.9683) < 0.001, f'Expected Study A baseline ~0.9683; found {baseline}'

    result, runs = [], []
    for i, dimension in enumerate(names):
        thresholds, without = evaluate(i)
        _, without_fixed = evaluate(i, original_thresholds)
        diff = full.macro_f1.to_numpy() - without.macro_f1.to_numpy()
        rng = np.random.default_rng(31000 + i)
        sample_idxs = rng.integers(0, len(diff), size=(15000, len(diff)))
        low, high = np.quantile(diff[sample_idxs].mean(axis=1), [0.025, 0.975])
        result.append({
            'dimension': dimension, 'weight': float(cd.W[i]),
            'full_macro_f1': baseline,
            'without_macro_f1': float(without.macro_f1.mean()),
            'drop_macro_f1': float(diff.mean()),
            'ci95_low': float(low), 'ci95_high': float(high),
            'without_fixed_threshold_f1': float(without_fixed.macro_f1.mean()),
            'drop_fixed_threshold': float(baseline - without_fixed.macro_f1.mean()),
            'new_thresholds': ';'.join(f'{v:.3f}' for v in thresholds)
        })
        for j, seed in enumerate(cd.TEST):
            runs.append({'removed_dimension': dimension, 'seed': seed,
                         'full_macro_f1': float(full.macro_f1.iloc[j]),
                         'without_macro_f1': float(without.macro_f1.iloc[j]),
                         'paired_drop': float(diff[j])})
    df = pd.DataFrame(result)
    df.to_csv(out_dir/'StudyA_leave_one_dimension_out.csv', index=False, float_format='%.8f')
    pd.DataFrame(runs).to_csv(out_dir/'StudyA_LOFO_paired_runs.csv', index=False, float_format='%.8f')

    # Fig. 5 of the manuscript, two panels written as separate images (placed side by side in the paper):
    # (a) radar of the macro-F1 decrease in percentage points, (b) paired effects with 95% bootstrap intervals.
    short = {'configuration': 'Config.', 'topology': 'Topology', 'role': 'Role', 'policy': 'Policy', 'architecture': 'Arch.',
             'context': 'Context', 'semantic': 'Semantic', 'goal': 'Goal', 'security': 'Security'}
    n = len(df)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    vals = df.drop_macro_f1.to_numpy()*100
    fig, ax = plt.subplots(figsize=(7.8, 8.15), subplot_kw={'polar': True})
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.plot(np.r_[angles,angles[0]], np.r_[vals,vals[0]], marker='o', linewidth=3.0, markersize=8)
    ax.fill(np.r_[angles,angles[0]], np.r_[vals,vals[0]], alpha=.14)
    ax.set_xticks(angles)
    ax.set_xticklabels([short[d] for d in df.dimension], fontsize=15)
    ax.tick_params(axis='x', pad=14)
    ax.set_yticks([3,6,9,12])
    ax.set_yticklabels(['3','6','9','12'], fontsize=14)
    ax.set_ylim(0, 13)
    ax.set_rlabel_position(40)
    ax.grid(alpha=.55)
    ax.set_title('Nine-dimension profile', fontsize=22, pad=26)
    for ext in ('png',):
        fig.savefig(fig_dir/f'fig5a_study_a_lofo_radar.{ext}', dpi=250, bbox_inches='tight')
    plt.close(fig)

    order = df.sort_values('drop_macro_f1', ascending=False).reset_index(drop=True)   # largest decrease at the top
    center = order.drop_macro_f1.to_numpy()*100
    left = (order.drop_macro_f1-order.ci95_low).to_numpy()*100
    right = (order.ci95_high-order.drop_macro_f1).to_numpy()*100
    fig, ax = plt.subplots(figsize=(8.2, 5.6))
    y_pos = np.arange(n)
    ax.errorbar(center, y_pos, xerr=[left,right], fmt='o', markersize=9, linewidth=2.2, capsize=4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([short[d] for d in order.dimension], fontsize=14)
    ax.invert_yaxis()
    ax.axvline(0, color='0.5', linewidth=1.4)
    ax.set_xticks([0,3,6,9,12]); ax.set_xlim(-1.0, 14.2)
    ax.tick_params(axis='x', labelsize=14)
    ax.set_xlabel('Macro-F1 decrease (percentage points)', fontsize=15)
    ax.set_title('Paired effects and 95% confidence intervals', fontsize=18, pad=10)
    ax.grid(axis='x', alpha=.25)
    ax.set_axisbelow(True)
    for ext in ('png',):
        fig.savefig(fig_dir/f'fig5b_study_a_lofo_paired_ci.{ext}', dpi=250, bbox_inches='tight')
    plt.close(fig)
    print(df[['dimension','without_macro_f1','drop_macro_f1','ci95_low','ci95_high']].to_string(index=False,float_format=lambda v:f'{v:.4f}'))
    print(f'Original C0 macro-F1 = {baseline:.6f}; tables saved to {out_dir}, figures to {fig_dir}')


if __name__=='__main__':
    here = Path(__file__).resolve().parent
    parser=argparse.ArgumentParser(description='Study A leave-one-drift-dimension-out analysis (run from anywhere; defaults write into the repository).')
    parser.add_argument('--code-dir', type=Path, default=here, help='directory with controlled_drift.py and multidrift_eval.py (default: this folder)')
    parser.add_argument('--output-dir', type=Path, default=here.parent/'docs'/'results'/'study_a_lofo', help='CSV tables (default: docs/results/study_a_lofo)')
    parser.add_argument('--figures-dir', type=Path, default=here.parent/'docs'/'figures', help='Fig. 5a and 5b as separate PNG files (default: docs/figures/)')
    args=parser.parse_args()
    analyze(args.code_dir,args.output_dir,args.figures_dir)
