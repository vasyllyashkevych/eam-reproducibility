"""Fig. 4-6 of the manuscript (600 dpi, black-and-white safe, English labels, text >= 8 pt at 6.7 in width).

    python3 figures.py      # after controlled_drift.py and security_cvss.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
from paths import RESULTS, FIGURES, STUDY_B_RESTRICTED, DATA as PKG_DATA
OUT = RESULTS
FIGS = FIGURES
E2E = STUDY_B_RESTRICTED
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 9, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "legend.fontsize": 8.5, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 600, "savefig.bbox": "tight"})
INK, GREY, LIGHT = "#1a1a1a", "#7a7a7a", "#c8c8c8"
DIMS = ["configuration", "topological", "role", "policy", "architectural", "contextual", "semantic", "goal", "security"]


def ci(x):
    rng = np.random.default_rng(0)
    m = rng.choice(x, (5000, len(x))).mean(1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5)


def fig_controlled():
    R = pd.read_csv(OUT / "controlled_runs.csv")
    groups = [("main", "A", "A:\nwindow\n+ PDI"), ("main", "B", "B:\nreference\n+ max"),
              ("main", "C", "C:\nreference\n+ PDI"), ("main", "C0", "C0:\nreference\n+ EDI"),
              ("coverage", "C0|context", "telemetry\nonly"), ("coverage", "C0|configuration,topology,architecture", "config.\n+ structure"),
              ("coverage", "C0|context,configuration,topology,architecture", "telemetry\n+ config.\n+ structure"),
              ("sanctioned", "C0", "static\nreference"), ("sanctioned", "C0-ref", "versioned\nreference")]
    fig, ax = plt.subplots(figsize=(6.7, 3.0))
    xs, hatches = [], []
    for k, (tag, v, lab) in enumerate(groups):
        x = R[(R.tag == tag) & (R.variant == v)].macro_f1.values
        lo, hi = ci(x); m = x.mean()
        proposed = v in ("C0", "C0-ref") and not (tag == "sanctioned" and v == "C0")
        ax.bar(k, m, width=0.62, color=INK if proposed else LIGHT, edgecolor=INK, linewidth=0.6)
        ax.errorbar([k], [m], yerr=[[m - lo], [hi - m]], color=GREY if proposed else INK, capsize=2, linewidth=0.8)
        ax.text(k, m + 0.03, f"{m:.2f}", ha="center", fontsize=8.5)
    for x0 in (3.5, 6.5):
        ax.axvline(x0, color=GREY, linewidth=0.6, linestyle=":")
    ax.set_xticks(range(len(groups))); ax.set_xticklabels([g[2] for g in groups], fontsize=8)
    ax.set_ylim(0, 1.1); ax.set_ylabel("Macro-F1 of evolution-state classification")
    for x, t in ((1.5, "(a) index variants"), (5.0, "(b) evidence subsets"), (7.5, "(c) approved release")):
        ax.text(x, 1.07, t, ha="center", fontsize=8.5, style="italic")
    fig.savefig(FIGS / "fig4_study_a_macro_f1.png"); plt.close(fig)


def fig_migration_profile():
    unit_file = E2E / "e2e_units_9d.csv"
    if unit_file.exists():                       # authorised copy of the restricted unit-level table
        U = pd.read_csv(unit_file, keep_default_na=False)
        share, mean = [], []
        for d in DIMS:
            v = pd.to_numeric(U[f"d_{d}"], errors="coerce").fillna(0)
            share.append((v > 0).mean()); mean.append(v.mean())
    else:                                        # public aggregate: the figure only needs these two numbers per dimension
        A = pd.read_csv(PKG_DATA / "study_b_public" / "e2e_drift9_summary.csv").set_index("dimension")
        share = [A.loc[d, "share_pos"] for d in DIMS]; mean = [A.loc[d, "mean"] for d in DIMS]
    fig, ax = plt.subplots(figsize=(6.7, 2.6))
    x = np.arange(len(DIMS))
    ax.bar(x - 0.18, share, 0.36, color=LIGHT, edgecolor=INK, linewidth=0.6, label="share of units with drift > 0")
    ax.bar(x + 0.18, mean, 0.36, color=INK, label="mean drift value")
    ax.set_xticks(x); ax.set_xticklabels([d.capitalize() for d in DIMS], fontsize=8.5, rotation=25, ha="right")
    ax.set_ylim(0, 1); ax.set_ylabel("Value"); ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2)
    fig.savefig(FIGS / "fig5_study_b_drift_profile.png"); plt.close(fig)


def fig_security():
    P = pd.read_csv(OUT / "security_pinned_deployments.csv")
    fig, ax = plt.subplots(figsize=(6.7, 2.7))
    styles = {"urllib3": "-", "pyyaml": "--", "tqdm": "-.", "gunicorn": ":", "attrs": (0, (6, 2, 1, 2, 1, 2))}
    for repo, ls in styles.items():
        g = P[P.repo == repo]
        ys = [((g[f"d_sec_{h}d"].dropna() > 0).mean()) for h in (365, 730, 1825)]
        ax.plot([1, 2, 5], ys, linestyle=ls, marker="o", markersize=3, color=INK, linewidth=1, label=f"{repo} ({len(g)} releases)")
    ax.set_xticks([1, 2, 5]); ax.set_xlabel("Years since the release was deployed (no upgrade)")
    ax.set_ylabel("Share with security drift > 0"); ax.set_ylim(-0.04, 1); ax.set_xlim(0.7, 5.3)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.savefig(FIGS / "fig6_study_c_pinned_releases.png"); plt.close(fig)


if __name__ == "__main__":
    FIGS.mkdir(exist_ok=True)
    fig_controlled(); fig_migration_profile(); fig_security()
    print(sorted(p.name for p in FIGS.glob("*.png")))
