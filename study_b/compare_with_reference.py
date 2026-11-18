"""Compare regenerated Study B outputs with the author's original outputs in study_b/reference/.

Writes study_b/logs/study_b_comparison.json and prints one line per file. Exit status 1 on a mismatch
outside the stated tolerance (except the documented non-deterministic first corpus-experiment run).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

H = Path(__file__).resolve().parent
REF = H / "reference"
TOL = 1e-9
TIMING = {"t_adapt", "overhead_ms_step", "workload_ms_step"}


def frame_diff(new, ref, keys):
    a = pd.read_csv(new, keep_default_na=False).sort_values(keys).reset_index(drop=True)
    b = pd.read_csv(ref, keep_default_na=False).sort_values(keys).reset_index(drop=True)
    if a.shape != b.shape or list(a.columns) != list(b.columns):
        return dict(equal=False, reason=f"shape/columns differ {a.shape} vs {b.shape}")
    worst, col = 0.0, None
    for c in a.columns:
        if c in TIMING:            # wall-clock measurements depend on the machine; reported, not compared
            continue
        x, y = pd.to_numeric(a[c], errors="coerce"), pd.to_numeric(b[c], errors="coerce")
        if x.notna().all() and y.notna().all():
            d = float(np.nanmax(np.abs(x.values - y.values))) if len(x) else 0.0
            if d > worst:
                worst, col = d, c
        elif not (a[c].astype(str) == b[c].astype(str)).all():
            return dict(equal=False, reason=f"text column {c} differs")
    return dict(equal=worst <= TOL, max_abs_diff=worst, column=col)


def mean_f1(path, variants=None):
    R = pd.read_csv(path)
    g = R.groupby("variant").F1.mean()
    return {k: round(float(v), 4) for k, v in g.items() if variants is None or k in variants}


res = {}
pairs = [("e2e/out/e2e_units.csv", "e2e_units.csv", ["unit"]),
         ("e2e/out/e2e_objects.csv", "e2e_objects.csv", ["unit", "obj_id"] if "obj_id" in pd.read_csv(REF / "e2e_objects.csv", nrows=1).columns else ["unit"]),
         ("e2e/out/e2e_units_9d.csv", "e2e_units_9d.csv", ["unit"]),
         ("e2e/out/e2e_drift9_summary.csv", "e2e_drift9_summary.csv", ["dimension"]),
         ("e2e/out/ont_indep_gold.csv", "ont_indep_gold.csv", ["unit"]),
         ("e2e/out/e2e_runs.csv", "e2e_runs.csv", ["seed", "variant"]),
         ("e2e/out/e2e_runs_ext.csv", "e2e_runs_ext.csv", ["seed", "variant"]),
         ("ops/out/ops_runs_method.csv", "ops_runs_method.csv", ["seed", "variant"])]
fail = False
for new, ref, keys in pairs:
    p = H / new
    if not p.exists():
        res[new] = dict(equal=False, reason="not produced"); fail = True
        print(f"MISSING  {new}"); continue
    r = frame_diff(p, REF / ref, keys)
    res[new] = r
    fail |= not r["equal"]
    print(("SAME     " if r["equal"] else "DIFFERS  ") + new, {k: v for k, v in r.items() if k != "equal"})

# Table 7 in the paper is the deterministic run (study_b/reference/e2e_runs.csv). The author's first run, made
# before set iteration in derive() was deterministic, is kept in reference/first_run/ for information only.
new5 = mean_f1(H / "e2e/out/e2e_runs.csv")
first5 = mean_f1(REF / "first_run" / "e2e_runs_first_nondeterministic_run.csv")
ext5 = mean_f1(REF / "e2e_runs_ext.csv", set(new5))
res["table7_F1_regenerated"] = new5
res["table7_F1_first_nondeterministic_run"] = first5
res["table7_F1_deterministic_rerun"] = ext5
res["table7_max_abs_diff_vs_first_run"] = max(abs(new5[k] - first5[k]) for k in new5)
res["table7_equal_to_deterministic_rerun"] = all(abs(new5[k] - ext5[k]) < 1e-4 for k in new5)
print("Table 7 F1 regenerated        ", new5)
print("first run (information only)  ", first5, "max |diff| =", round(res["table7_max_abs_diff_vs_first_run"], 4))
print("equal to deterministic re-run:", res["table7_equal_to_deterministic_rerun"])
fail |= not res["table7_equal_to_deterministic_rerun"]

fp_new = H / "out_check" / "boundary_failure_prediction.csv"
if fp_new.exists():
    r = frame_diff(fp_new, H.parent / "data" / "study_b_public" / "boundary_failure_prediction.csv", ["indicator"])
    res["boundary_failure_prediction.csv"] = r; fail |= not r["equal"]
    print(("SAME     " if r["equal"] else "DIFFERS  ") + "boundary_failure_prediction.csv (Table 10)", r)

(H / "logs").mkdir(exist_ok=True)
(H / "logs" / "study_b_comparison.json").write_text(json.dumps(res, indent=1, default=str))
sys.exit(1 if fail else 0)
