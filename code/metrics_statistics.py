"""Study B: recompute Tables 7-8 and the reported statistics from the public per-run metric files.

This script starts from the per-run metric files in data/study_b_public/ (one row per seed and variant;
they are the outputs of Study B levels 1-2, so no database is needed) and recomputes every aggregate
and test reported in Section 7.2:

    python3 metrics_statistics.py      ->  docs/results/study_b_table7.csv, docs/results/study_b_table8.csv,
                                       docs/results/study_b_statistics.json
"""
import json

import numpy as np
import pandas as pd
from scipy import stats

from paths import DATA, RESULTS

B = DATA / "study_b_public"


def holm(pvals):
    order = np.argsort(pvals)
    adj = np.empty(len(pvals))
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[idx]))
        adj[idx] = running
    return adj


def paired_t_ci(d, level=0.95):
    d = np.asarray(d, float)
    se = d.std(ddof=1) / np.sqrt(len(d))
    t = stats.t.ppf(0.5 + level / 2, len(d) - 1)
    return float(d.mean()), float(d.mean() - t * se), float(d.mean() + t * se)


def a12(x, y):
    x, y = np.asarray(x), np.asarray(y)
    gt = (x[:, None] > y[None, :]).sum(); eq = (x[:, None] == y[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(x) * len(y)))


def tost_paired(d, margin):
    d = np.asarray(d, float)
    n = len(d); se = d.std(ddof=1) / np.sqrt(n); m = d.mean()
    p_lower = 1 - stats.t.cdf((m + margin) / se, n - 1)
    p_upper = stats.t.cdf((m - margin) / se, n - 1)
    return float(max(p_lower, p_upper))


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = {}
    # ---------------------------------------------------------------- Table 7: corpus experiment, 40 runs per variant
    R = pd.read_csv(B / "e2e_runs.csv")
    T7 = R.groupby("variant").agg(PCRw=("PCRw", "mean"), MRSR=("MRSR", "mean"), P=("P", "mean"), R=("R", "mean"),
                                  F1=("F1", "mean"), F1_sd=("F1", "std"), MTTD=("MTTD", "mean"), LA=("LA", "mean"),
                                  FAR=("FAR", "mean"), slots_optimized=("slots_optimized", "mean"),
                                  t_adapt_s=("t_adapt", "mean"), runs=("seed", "nunique"))
    T7.to_csv(RESULTS / "study_b_table7.csv")
    F = R.pivot(index="seed", columns="variant", values="F1")
    fr = stats.friedmanchisquare(*[F[c] for c in ["S0", "S1", "S2", "S3", "S3-O"]])
    out["sim_friedman_chi2"] = float(fr.statistic); out["sim_friedman_p"] = float(fr.pvalue)
    comps = ["S0", "S1", "S2", "S3-O"]
    p = [stats.wilcoxon(F["S3"], F[c]).pvalue for c in comps]
    out["sim_wilcoxon_holm_S3_vs"] = dict(zip(comps, map(float, holm(np.array(p)))))
    out["sim_A12_S3_vs"] = {c: a12(F["S3"], F[c]) for c in comps}
    out["sim_tost_S3_S2_F1_margin_0.02_p"] = tost_paired(F["S3"] - F["S2"], 0.02)
    # deterministic re-run with all ten variants (comparison mechanisms, S3-9D)
    X = pd.read_csv(B / "e2e_runs_ext.csv")
    sim_ext = X.groupby("variant").F1.mean()
    out["sim_ext_F1"] = {k: float(v) for k, v in sim_ext.items()}
    FX = X.pivot(index="seed", columns="variant", values="F1")
    out["sim_ext_S3_minus_ARV"] = paired_t_ci(FX["S3"] - FX["A-RV"])
    # ---------------------------------------------------------------- Table 8: PostgreSQL 17 testbed, 10 runs per variant
    O = pd.read_csv(B / "ops_runs_method.csv")
    T8 = O.groupby("variant").agg(object_probes=("probes_obj", "mean"), P=("P", "mean"), R=("R", "mean"), F1=("F1", "mean"),
                                  F1_sd=("F1", "std"), MTTD=("MTTD", "mean"), LA=("LA", "mean"),
                                  overhead_ms_step=("overhead_ms_step", "mean"), workload_ms_step=("workload_ms_step", "mean"),
                                  runs=("seed", "nunique"))
    T8.to_csv(RESULTS / "study_b_table8.csv")
    TB = O.pivot(index="seed", columns="variant", values="F1")
    others = [c for c in TB.columns if c != "S3"]
    pv = np.array([stats.wilcoxon(TB["S3"], TB[c]).pvalue for c in others])
    out["testbed_wilcoxon_holm_S3_vs"] = dict(zip(others, map(float, holm(pv))))
    out["testbed_S3_minus_S0"] = paired_t_ci(TB["S3"] - TB["S0"])
    out["testbed_S3_minus_ARV"] = paired_t_ci(TB["S3"] - TB["A-RV"])
    out["testbed_S2_minus_S3"] = paired_t_ci(TB["S2"] - TB["S3"])
    common = sorted(set(sim_ext.index) & set(TB.columns))
    rho = stats.spearmanr(sim_ext[common], TB[common].mean())
    out["sim_vs_testbed_spearman"] = [float(rho.statistic), float(rho.pvalue), len(common)]
    # ---------------------------------------------------------------- drift profile shares (aggregate, Fig. 4)
    D = pd.read_csv(B / "e2e_drift9_summary.csv").set_index("dimension")
    out["drift_share_nonzero"] = {k: float(v) for k, v in D.share_pos.items()}
    # ---------------------------------------------------------------- failure prediction (Table 10, precomputed by code/boundary_real.py from the Study B unit table)
    FP = pd.read_csv(B / "boundary_failure_prediction.csv").set_index("indicator")
    out["failure_prediction_auc"] = {k: [float(r.auc), float(r.auc_lo), float(r.auc_hi)] for k, r in FP.iterrows()}
    (RESULTS / "study_b_statistics.json").write_text(json.dumps(out, indent=2))
    print(T7[["PCRw", "MRSR", "P", "R", "F1", "F1_sd", "MTTD"]].round(3).to_string())
    print(T8[["object_probes", "P", "R", "F1", "F1_sd", "MTTD", "LA"]].round(3).to_string())
    print(json.dumps({k: v for k, v in out.items() if not isinstance(v, dict)}, indent=1))


if __name__ == "__main__":
    main()
