# -*- coding: utf-8 -*-
"""Independent recomputation of the corpus-experiment statistics from the per-run file.

Input: out/e2e_runs.csv (200 runs = 5 variants x 40 seeds, paired by seed).
Output:
  out/e2e_paired_ci.csv  - paired differences S3 - X: mean, 95% t interval, 95% BCa bootstrap (10,000),
                           Wilcoxon with Holm correction, A12 (independent samples) and paired A12;
  out/e2e_tost.csv       - equivalence of S3 and S2 (TOST, paired t test, margin +-delta);
  out/e2e_recompute_check.csv - recomputed Friedman chi2 and p compared with the published values."""
import os, sys
import numpy as np, pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
RUNS = os.path.join(OUT, sys.argv[1] if len(sys.argv) > 1 else "e2e_runs.csv")
METRICS = ["PCR", "PCRw", "TPP", "MRSR", "F1", "P", "R", "MTTD", "LA", "FAR"]
LOWER_BETTER = {"MTTD", "FAR"}
MARGIN = {"F1": 0.02, "PCRw": 0.02, "PCR": 0.02, "TPP": 0.02, "MRSR": 0.02, "P": 0.02, "R": 0.02,
          "LA": 0.02, "FAR": 0.02, "MTTD": 0.5}


def holm(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    adj = np.empty_like(p)
    run = 0.0
    for k, i in enumerate(o):
        run = max(run, (len(p) - k) * p[i])
        adj[i] = min(1.0, run)
    return adj


def main():
    R = pd.read_csv(RUNS)
    variants = [v for v in ["S0", "S1", "S2", "S3-O", "A-RB", "A-RX", "A-AM", "A-RV", "S3-9D"] if v in set(R.variant)]
    rows, check = [], []
    rng = np.random.default_rng(20261027)
    for m in METRICS:
        piv = R.pivot(index="seed", columns="variant", values=m)
        allv = ["S3"] + variants
        full = piv[allv].dropna()
        fr = stats.friedmanchisquare(*[full[v] for v in allv])
        check.append(dict(metric=m, k=len(allv), N=len(full), friedman_chi2=fr.statistic, friedman_p=fr.pvalue))
        block = []
        for v in variants:
            pair = piv[["S3", v]].dropna()
            d = (pair["S3"] - pair[v]).to_numpy()
            n = len(d)
            mean, sd = d.mean(), d.std(ddof=1)
            if sd > 0:
                h = stats.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
                bs = stats.bootstrap((pair["S3"].to_numpy(), pair[v].to_numpy()), lambda a, b: np.mean(a - b),
                                     paired=True, vectorized=False, n_resamples=10000, confidence_level=0.95,
                                     method="BCa", random_state=rng)
                lo_b, hi_b = bs.confidence_interval
                try:
                    pw = stats.wilcoxon(pair["S3"], pair[v]).pvalue
                except ValueError:
                    pw = np.nan
            else:
                h, lo_b, hi_b, pw = 0.0, mean, mean, np.nan
            u = stats.mannwhitneyu(pair["S3"], pair[v], alternative="two-sided").statistic
            a12 = u / (n * n)
            a12p = (np.sum(d > 0) + 0.5 * np.sum(d == 0)) / n          # paired A12 (share of seeds where S3 is larger)
            block.append(dict(metric=m, comparison=f"S3 − {v}", n=n, mean_S3=pair["S3"].mean(), mean_other=pair[v].mean(),
                              diff=mean, sd_diff=sd, t_lo=mean - h, t_hi=mean + h, bca_lo=lo_b, bca_hi=hi_b,
                              wilcoxon_p=pw, A12=a12, A12_paired=a12p,
                              favours_S3=(mean < 0) if m in LOWER_BETTER else (mean > 0)))
        ps = [b["wilcoxon_p"] for b in block]
        ok = ~np.isnan(ps)
        adj = np.full(len(ps), np.nan)
        adj[ok] = holm(np.array(ps)[ok])
        for b, a in zip(block, adj):
            b["p_holm"] = a
        rows += block
    ci = pd.DataFrame(rows)
    tag = os.path.splitext(os.path.basename(RUNS))[0].replace("e2e_runs", "")
    ci.to_csv(os.path.join(OUT, f"e2e_paired_ci{tag}.csv"), index=False)
    # TOST: S3 and S2 are equivalent within +-delta if both one-sided p < 0.05 (equivalently, the 90% CI lies inside the margin)
    tost = []
    for m in METRICS:
        pair = R.pivot(index="seed", columns="variant", values=m)[["S3", "S2"]].dropna()
        d = (pair["S3"] - pair["S2"]).to_numpy()
        n, mean, se = len(d), d.mean(), d.std(ddof=1) / np.sqrt(len(d))
        dl = MARGIN[m]
        p_lo = 1 - stats.t.cdf((mean + dl) / se, n - 1)
        p_hi = stats.t.cdf((mean - dl) / se, n - 1)
        h90 = stats.t.ppf(0.95, n - 1) * se
        tost.append(dict(metric=m, margin=dl, diff=mean, ci90_lo=mean - h90, ci90_hi=mean + h90,
                         p_lower=p_lo, p_upper=p_hi, p_tost=max(p_lo, p_hi), equivalent=max(p_lo, p_hi) < 0.05))
    pd.DataFrame(tost).to_csv(os.path.join(OUT, f"e2e_tost{tag}.csv"), index=False)
    pd.DataFrame(check).to_csv(os.path.join(OUT, f"e2e_recompute_check{tag}.csv"), index=False)
    pd.set_option("display.width", 220)
    print(pd.DataFrame(check).round(4).to_string())
    print(ci[ci.metric.isin(["F1", "PCRw", "TPP", "MRSR", "MTTD"])][["metric", "comparison", "diff", "t_lo", "t_hi", "bca_lo", "bca_hi", "p_holm", "A12_paired"]].round(4).to_string())
    print(pd.DataFrame(tost).round(4).to_string())


if __name__ == "__main__":
    main()
