#!/usr/bin/env python3
"""Supplementary leave-one-drift-dimension-out analysis for PAPER021433, Study A.

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


def analyze(code_dir: Path, out_dir: Path):
    sys.path.insert(0, str(code_dir.resolve()))
    import controlled_drift as cd
    from controlled_drift import md

    out_dir.mkdir(parents=True, exist_ok=True)
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

    # Radar: percentage-point decrease in macro-F1 after removing a dimension.
    n = len(df)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    vals = df.drop_macro_f1.to_numpy()*100
    fig, ax = plt.subplots(figsize=(9.4, 8.2), subplot_kw={'polar': True})
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.plot(np.r_[angles,angles[0]], np.r_[vals,vals[0]], marker='o', linewidth=2.2, markersize=6)
    ax.fill(np.r_[angles,angles[0]], np.r_[vals,vals[0]], alpha=.14)
    ax.set_xticks(angles)
    ax.set_xticklabels([n.title() for n in df.dimension], fontsize=12)
    ax.tick_params(axis='x', pad=17)
    ax.set_yticks([0,3,6,9,12])
    ax.set_yticklabels(['0','3','6','9','12'], fontsize=9)
    ax.set_ylim(0, 13)
    ax.set_rlabel_position(15)
    ax.grid(alpha=.55)
    ax.set_title('Study A | Leave-one-drift-dimension-out ablation', fontsize=15, weight='bold', pad=37)
    fig.text(.50, .05, 'Decrease in macro-F1 (percentage points)  |  Baseline: 0.9683  |  40 paired test runs',
             ha='center', fontsize=10)
    fig.subplots_adjust(left=.10,right=.90,top=.82,bottom=.12)
    for ext in ('png','svg'):
        fig.savefig(out_dir/f'Fig_LOFO_Radar_StudyA.{ext}', dpi=400, bbox_inches='tight')
    plt.close(fig)

    # Signed values + paired bootstrap CIs are easier to compare on a second chart.
    order=df.sort_values('drop_macro_f1', ascending=True)
    center=order.drop_macro_f1.to_numpy()*100
    left=(order.drop_macro_f1-order.ci95_low).to_numpy()*100
    right=(order.ci95_high-order.drop_macro_f1).to_numpy()*100
    fig, ax=plt.subplots(figsize=(9.2, 6.4))
    y_pos=np.arange(len(order))
    bars=ax.barh(y_pos, center, xerr=[left,right], capsize=3, alpha=.85)
    ax.set_yticks(y_pos, [x.title() for x in order.dimension], fontsize=11)
    ax.axvline(0, linewidth=.9)
    ax.set_xlabel('Decrease in macro-F1 after exclusion (percentage points)', fontsize=11)
    ax.set_xlim(-0.8, max(13.7, max(center)*1.12))
    ax.set_title('Study A | Contribution of each drift dimension', fontsize=15, weight='bold')
    ax.grid(axis='x', alpha=.25)
    ax.set_axisbelow(True)
    for idx, v in enumerate(center):
        ax.text(v+0.35,idx,f'{v:+.2f}', va='center', fontsize=10)
    fig.text(.50, .035, 'Points: mean paired effect across 40 seeds. Error bars: 95% paired bootstrap CI.',
             ha='center', fontsize=10)
    fig.subplots_adjust(left=.20,right=.97,top=.88,bottom=.13)
    for ext in ('png','svg'):
        fig.savefig(out_dir/f'Fig_LOFO_Bars_StudyA.{ext}', dpi=400, bbox_inches='tight')
    plt.close(fig)
    print(df[['dimension','without_macro_f1','drop_macro_f1','ci95_low','ci95_high']].to_string(index=False,float_format=lambda v:f'{v:.4f}'))
    print(f'Original C0 macro-F1 = {baseline:.6f}; saved to {out_dir}')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--code-dir', type=Path, required=True, help='Directory with controlled_drift.py and multidrift_eval.py')
    parser.add_argument('--output-dir', type=Path, default=Path('lofo_results'))
    args=parser.parse_args()
    analyze(args.code_dir,args.output_dir)
