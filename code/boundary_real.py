"""Failure prediction on the Oracle -> PostgreSQL migration (Study B, Table 10).

Question: does the per-unit drift vector, computed from source code and measured environment assumptions,
(1) predict which migrated units fail on PostgreSQL 17, and (2) point to the kind of failure?
Reference: independent execution-based failures (docs/study_b/e2e/out/ont_indep_gold.csv) with the
testbed artefacts (missing stub objects, schema renaming) excluded. Inputs are read only.

    python3 boundary_real.py      # needs the unit tables from `bash docs/study_b/run_study_b_offline.sh` (or set EAM_STUDY_B_DIR)
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).parent
from paths import RESULTS, STUDY_B_UNITS
OUT = RESULTS
E2E = STUDY_B_UNITS
DIMS = ["d_configuration", "d_topological", "d_role", "d_policy", "d_architectural", "d_contextual",
        "d_semantic", "d_goal", "d_security"]
# failure class -> drift dimensions expected to reflect it (fixed before looking at the lifts)
EXPECTED = {"privilege_context": ["d_policy", "d_security"], "dynamic_sql_safety": ["d_security"],
            "txn_semantics": ["d_contextual"], "null_semantics": ["d_semantic", "d_contextual"],
            "temporal_semantics": ["d_semantic", "d_contextual"], "type_coercion": ["d_configuration", "d_semantic"],
            "error_handling": ["d_semantic"], "remote_dependency": ["d_security", "d_topological"],
            "package_state": ["d_architectural"]}


def auc(score, y):
    return float(stats.mannwhitneyu(score[y], score[~y]).statistic / (y.sum() * (~y).sum())) if y.any() and (~y).any() else np.nan


def boot_auc(score, y, n=2000, seed=0):
    rng = np.random.default_rng(seed); vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].any() and (~y[i]).any():
            vals.append(auc(score[i], y[i]))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main():
    OUT.mkdir(exist_ok=True)
    U = pd.read_csv(E2E / "e2e_units_9d.csv", keep_default_na=False)
    G = pd.read_csv(E2E / "ont_indep_gold.csv", keep_default_na=False)
    for c in DIMS + ["lines"]:
        U[c] = pd.to_numeric(U[c], errors="coerce").fillna(0.0)
    tested = set(G.unit.astype(int))
    genuine = G[G.prop != "excluded"]
    classes = genuine.groupby("unit").prop.apply(set)
    V = U[U.unit.isin(tested)].copy().reset_index(drop=True)
    y = V.unit.isin(classes.index).values
    w = np.full(len(DIMS), 1 / len(DIMS))
    V["EDI"] = V[DIMS].values @ w
    V["size_loc"] = V["lines"]
    rows = []
    for c in DIMS + ["EDI", "size_loc"]:
        s = V[c].values; lo, hi = boot_auc(s, y)
        x = s > 0
        tp = (x & y).sum(); p = tp / max(x.sum(), 1); r = tp / y.sum()
        rows.append(dict(indicator=c, auc=auc(s, y), auc_lo=lo, auc_hi=hi, flagged=float(x.mean()),
                         precision=p, recall=r, f1=2 * p * r / (p + r) if p + r else 0.0))
    A = pd.DataFrame(rows)
    A.to_csv(OUT / "boundary_failure_prediction.csv", index=False)
    # partial association: does EDI add anything beyond size? (Spearman on residuals)
    r_size = stats.spearmanr(V.EDI, V.size_loc)
    # diagnostic specificity: lift of each dimension in units of a failure class vs. units without failures
    clean = ~y
    L = []
    for cls, exp in EXPECTED.items():
        units = set(classes[classes.apply(lambda s: cls in s)].index)
        m = V.unit.isin(units).values
        if m.sum() == 0:
            continue
        for c in DIMS:
            pc, p0 = (V.loc[m, c] > 0).mean(), (V.loc[clean, c] > 0).mean()
            L.append(dict(failure_class=cls, n_units=int(m.sum()), dim=c, share_in_class=pc, share_clean=p0,
                          lift=pc / p0 if p0 else np.inf, mean_in_class=V.loc[m, c].mean(), mean_clean=V.loc[clean, c].mean(),
                          expected=c in exp))
    L = pd.DataFrame(L)
    L.to_csv(OUT / "boundary_class_lift.csv", index=False)
    spec = []
    for cls, g in L.groupby("failure_class"):
        g = g.assign(delta=g.mean_in_class - g.mean_clean).sort_values("delta", ascending=False).reset_index(drop=True)
        best_exp = g[g.expected].index.min()
        spec.append(dict(failure_class=cls, n_units=int(g.n_units.iloc[0]), top_dim=g.dim.iloc[0],
                         expected=";".join(EXPECTED[cls]), rank_of_expected=int(best_exp) + 1,
                         delta_expected=float(g.loc[best_exp, "delta"]), delta_top=float(g.delta.iloc[0])))
    Sp = pd.DataFrame(spec).sort_values("n_units", ascending=False)
    Sp.to_csv(OUT / "boundary_specificity.csv", index=False)
    pd.set_option("display.width", 220)
    print(f"units evaluated: {len(V)}, with genuine failures: {int(y.sum())} ({y.mean():.3f}); "
          f"EDI vs size Spearman rho={r_size.statistic:.3f}")
    print(A.round(3).to_string(index=False))
    print(Sp.round(3).to_string(index=False))
    # chance level for rank_of_expected with k expected dims among 9: expected best rank
    exp_rank = {k: np.mean([min(np.random.default_rng(i).permutation(9)[:len(v)]) + 1 for i in range(5000)]) for k, v in EXPECTED.items()}
    weighted = (Sp.rank_of_expected * Sp.n_units).sum() / Sp.n_units.sum()
    chance = sum(exp_rank[c] * n for c, n in zip(Sp.failure_class, Sp.n_units)) / Sp.n_units.sum()
    top1 = (Sp.rank_of_expected == 1).sum()
    print(f"unit-weighted rank of the expected dimension: {weighted:.2f} (chance {chance:.2f}); expected dim ranked first in {top1}/{len(Sp)} classes")
    pd.Series(dict(units=len(V), failing=int(y.sum()), edi_size_rho=float(r_size.statistic), weighted_rank=weighted,
                   chance_rank=chance, top1=int(top1), classes=len(Sp))).to_json(OUT / "boundary_summary.json")


if __name__ == "__main__":
    main()
