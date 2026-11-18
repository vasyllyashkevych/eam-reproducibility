"""Compare regenerated outputs with the numbers printed in the manuscript.

Reads expected/expected_results.json, computes each value from the files in results/ (never from constants),
and writes results/reproduction_summary.json and results/reproduction_summary.md.
Exit status 1 if any check fails.

    python3 check_expected.py
"""
import json
import sys

import numpy as np
import pandas as pd

from paths import PKG, RESULTS

EXP = PKG / "expected" / "expected_results.json"


def load():
    r = {}
    r["runs"] = pd.read_csv(RESULTS / "controlled_runs.csv")
    r["ctests"] = pd.read_csv(RESULTS / "controlled_tests.csv")
    r["wsens"] = pd.read_csv(RESULTS / "controlled_weight_sensitivity.csv")
    r["tsens"] = pd.read_csv(RESULTS / "controlled_theta_sensitivity.csv").set_index("theta")
    r["prf"] = pd.read_csv(RESULTS / "controlled_prf_by_dim.csv")
    r["dual"] = pd.read_csv(RESULTS / "dual_profile_runs.csv")
    r["dtests"] = pd.read_csv(RESULTS / "dual_profile_tests.csv")
    r["shock"] = pd.read_csv(RESULTS / "dual_profile_shock_runs.csv")
    r["sec"] = json.loads((RESULTS / "security_drift_summary.json").read_text())
    r["snap"] = pd.read_csv(RESULTS / "security_drift_snapshots.csv")
    r["win"] = pd.read_csv(RESULTS / "security_exposure_windows.csv")
    r["b"] = json.loads((RESULTS / "study_b_statistics.json").read_text())
    r["t7"] = pd.read_csv(RESULTS / "study_b_table7.csv").set_index("variant")
    r["t8"] = pd.read_csv(RESULTS / "study_b_table8.csv").set_index("variant")
    from paths import DATA
    BP = DATA / "study_b_public"
    r["bcounts"] = json.loads((BP / "study_b_counts.json").read_text())
    r["bstruct"] = json.loads((BP / "e2e_structure_stats.json").read_text())
    r["bmodel"] = json.loads((BP / "e2e_model_info.json").read_text())
    r["bcorr"] = pd.read_csv(BP / "e2e_drift9_corr.csv", index_col=0)
    r["bctx"] = pd.read_csv(BP / "e2e_ctx_checks.csv")
    r["bbound"] = json.loads((BP / "boundary_summary.json").read_text())
    return r


def mean(r, tag, variant, col):
    x = r["runs"]
    return float(x[(x.tag == tag) & (x.variant == variant)][col].mean())


def test_row(df, metric, comp, field, tag=None):
    q = df[(df.metric == metric) & (df.comparison == comp)]
    if tag is not None:
        q = q[q.tag == tag]
    return float(q[field].iloc[0])


def dual(r, variant, col):
    d = r["dual"]
    return float(d[d.variant == variant][col].mean())


# id -> function(results) ; ids and expected values live in expected/expected_results.json
X = {
 # ---------------- Study A (Table 5, Section 7.1)
 "A.C0.macro_f1": lambda r: mean(r, "main", "C0", "macro_f1"),
 "A.C0.accuracy": lambda r: mean(r, "main", "C0", "accuracy"),
 "A.C.macro_f1": lambda r: mean(r, "main", "C", "macro_f1"),
 "A.B.macro_f1": lambda r: mean(r, "main", "B", "macro_f1"),
 "A.A.macro_f1": lambda r: mean(r, "main", "A", "macro_f1"),
 "A.B.false_critical": lambda r: mean(r, "main", "B", "false_critical"),
 "A.C0.false_critical": lambda r: mean(r, "main", "C0", "false_critical"),
 "A.friedman_chi2": lambda r: test_row(r["ctests"], "macro_f1", "Friedman", "stat", "main"),
 "A.C0_minus_C.diff": lambda r: test_row(r["ctests"], "macro_f1", "C0 - C", "diff", "main"),
 "A.C0_minus_C.ci_low": lambda r: test_row(r["ctests"], "macro_f1", "C0 - C", "ci_low", "main"),
 "A.C0_minus_C.ci_high": lambda r: test_row(r["ctests"], "macro_f1", "C0 - C", "ci_high", "main"),
 "A.telemetry_only.macro_f1": lambda r: mean(r, "coverage", "C0|context", "macro_f1"),
 "A.config_structure.macro_f1": lambda r: mean(r, "coverage", "C0|configuration,topology,architecture", "macro_f1"),
 "A.tel_config_structure.macro_f1": lambda r: mean(r, "coverage", "C0|context,configuration,topology,architecture", "macro_f1"),
 "A.release_static.macro_f1": lambda r: mean(r, "sanctioned", "C0", "macro_f1"),
 "A.release_versioned.macro_f1": lambda r: mean(r, "sanctioned", "C0-ref", "macro_f1"),
 "A.release_static.false_critical": lambda r: mean(r, "sanctioned", "C0", "false_critical"),
 "A.release_diff": lambda r: test_row(r["ctests"], "macro_f1", "C0-ref - C0", "diff", "sanctioned"),
 "A.evidence_gap_renormalised.macro_f1": lambda r: mean(r, "evidence_gap", "C0-gapX", "macro_f1"),
 "A.evidence_gap_zero_filled.macro_f1": lambda r: mean(r, "evidence_gap", "C0-gap0", "macro_f1"),
 "A.weights.median": lambda r: float(r["wsens"][r["wsens"].weights == "dirichlet"].macro_f1.median()),
 "A.weights.q25": lambda r: float(r["wsens"][r["wsens"].weights == "dirichlet"].macro_f1.quantile(0.25)),
 "A.weights.q75": lambda r: float(r["wsens"][r["wsens"].weights == "dirichlet"].macro_f1.quantile(0.75)),
 "A.weights.min": lambda r: float(r["wsens"][r["wsens"].weights == "dirichlet"].macro_f1.min()),
 "A.theta0.50.recall": lambda r: float(r["tsens"].loc[0.5, "recall"]),
 "A.theta0.20.recall": lambda r: float(r["tsens"].loc[0.2, "recall"]),
 "A.context.recall_C0": lambda r: float(r["prf"][(r["prf"].tag == "main") & (r["prf"].variant == "C0") & (r["prf"].dim == "context")].R.iloc[0]),
 "A.noise0.03.C0": lambda r: mean(r, "sigma=0.03,amp=1.0", "C0", "macro_f1"),
 "A.noise0.05.C0": lambda r: mean(r, "sigma=0.05,amp=1.0", "C0", "macro_f1"),
 "A.noise0.05.half.C0": lambda r: mean(r, "sigma=0.05,amp=0.5", "C0", "macro_f1"),
 # ---------------- joint ablation (Table 9, Section 7.4)
 "J.dual.coverage": lambda r: dual(r, "dual (proposed)", "coverage"),
 "J.dual.recall_uniform": lambda r: dual(r, "dual (proposed)", "recall_uniform"),
 "J.dual.recall_coupled": lambda r: dual(r, "dual (proposed)", "recall_coupled"),
 "J.dual.rebuilds": lambda r: dual(r, "dual (proposed)", "rebuilds"),
 "J.full.rebuilds": lambda r: dual(r, "full regeneration", "rebuilds"),
 "J.rebuild_ratio": lambda r: dual(r, "full regeneration", "rebuilds") / dual(r, "dual (proposed)", "rebuilds"),
 "J.versioned_run.recall_uniform": lambda r: dual(r, "versioned/run", "recall_uniform"),
 "J.rel_only.coverage": lambda r: dual(r, "versioned/rel", "coverage"),
 "J.rel_only.recall_uniform": lambda r: dual(r, "versioned/rel", "recall_uniform"),
 "J.static.false_critical": lambda r: dual(r, "static/run", "false_critical"),
 "J.versioned.false_critical": lambda r: dual(r, "dual (proposed)", "false_critical"),
 "J.interaction.recall_uniform": lambda r: test_row(r["dtests"], "recall_uniform", "interaction", "diff"),
 "J.interaction.recall_uniform.ci_low": lambda r: test_row(r["dtests"], "recall_uniform", "interaction", "ci_low"),
 "J.interaction.recall_uniform.ci_high": lambda r: test_row(r["dtests"], "recall_uniform", "interaction", "ci_high"),
 "J.interaction.coverage": lambda r: test_row(r["dtests"], "coverage", "interaction", "diff"),
 "J.interaction.recall_coupled": lambda r: test_row(r["dtests"], "recall_coupled", "interaction", "diff"),
 "J.friedman_recall_uniform": lambda r: test_row(r["dtests"], "recall_uniform", "Friedman", "stat"),
 "J.mask_only.flagged": lambda r: int(r["shock"][r["shock"].variant == "dual, mask only"].flagged_in_window.sum()),
 "J.criticalcheck.flagged": lambda r: int(r["shock"][r["shock"].variant == "dual + CriticalCheck"].flagged_in_window.sum()),
 # ---------------- Study C (Section 7.3, Fig. 6)
 "C.snapshots": lambda r: int(len(r["snap"])),
 "C.transitions": lambda r: r["sec"]["transitions"],
 "C.increases": lambda r: r["sec"]["exposure_increases"],
 "C.decreases": lambda r: r["sec"]["exposure_decreases"],
 "C.other_transitions": lambda r: r["sec"]["transitions"] - r["sec"]["security_events"],
 "C.static_rate": lambda r: r["sec"]["alert_static_rate_elsewhere"],
 "C.ewma_rate": lambda r: r["sec"]["alert_ewma_rate_elsewhere"],
 "C.code_recall": lambda r: max(r["sec"]["alert_static_recall_on_security_events"], r["sec"]["alert_ewma_recall_on_security_events"]),
 "C.spearman_rho": lambda r: r["sec"]["spearman_idi_vs_dsec"][0],
 "C.spearman_p": lambda r: r["sec"]["spearman_idi_vs_dsec"][1],
 "C.increases_low_idi": lambda r: r["sec"]["exposure_increases_without_code_change"],
 "C.pinned_releases": lambda r: r["sec"]["pinned_releases"],
 "C.pinned_with_advisory": lambda r: r["sec"]["pinned_with_any_advisory"],
 "C.pinned_1y_exposed": lambda r: r["sec"]["pinned_365d"]["share_exposed"],
 "C.pinned_1y_ge07": lambda r: r["sec"]["pinned_365d"]["share_ge_0.7"],
 "C.pinned_2y_exposed": lambda r: r["sec"]["pinned_730d"]["share_exposed"],
 "C.pinned_2y_ge07": lambda r: r["sec"]["pinned_730d"]["share_ge_0.7"],
 "C.pinned_5y_exposed": lambda r: r["sec"]["pinned_1825d"]["share_exposed"],
 "C.pinned_5y_ge07": lambda r: r["sec"]["pinned_1825d"]["share_ge_0.7"],
 "C.urllib3_2y": lambda r: r["sec"]["pinned_by_repo_730d"]["urllib3"],
 "C.attrs_2y": lambda r: r["sec"]["pinned_by_repo_730d"]["attrs"],
 "C.advisories_on_release_track": lambda r: int(len(r["win"])),
 "C.zero_window": lambda r: int((r["win"].window_days == 0).sum()),
 "C.longest_window_days": lambda r: int(r["win"].window_days.max()),
 # ---------------- Study B (Tables 7, 8, 10; Section 7.2) from public aggregates
 "B.sim.S0.F1": lambda r: float(r["t7"].loc["S0", "F1"]),
 "B.sim.S1.F1": lambda r: float(r["t7"].loc["S1", "F1"]),
 "B.sim.S2.F1": lambda r: float(r["t7"].loc["S2", "F1"]),
 "B.sim.S3.F1": lambda r: float(r["t7"].loc["S3", "F1"]),
 "B.sim.S3-O.F1": lambda r: float(r["t7"].loc["S3-O", "F1"]),
 "B.sim.S3.PCRw": lambda r: float(r["t7"].loc["S3", "PCRw"]),
 "B.sim.S2.PCRw": lambda r: float(r["t7"].loc["S2", "PCRw"]),
 "B.sim.S1.MRSR": lambda r: float(r["t7"].loc["S1", "MRSR"]),
 "B.sim.friedman_chi2": lambda r: r["b"]["sim_friedman_chi2"],
 "B.sim.tost_p": lambda r: r["b"]["sim_tost_S3_S2_F1_margin_0.02_p"],
 "B.sim.S3.slots": lambda r: float(r["t7"].loc["S3", "slots_optimized"]),
 "B.sim.S2.slots": lambda r: float(r["t7"].loc["S2", "slots_optimized"]),
 "B.sim.S2_vs_S3.p_holm": lambda r: r["b"]["sim_wilcoxon_holm_S3_vs"]["S2"],
 "B.sim_ext.A-RX.F1": lambda r: r["b"]["sim_ext_F1"]["A-RX"],
 "B.sim_ext.A-RV.F1": lambda r: r["b"]["sim_ext_F1"]["A-RV"],
 "B.sim_ext.S3-9D.F1": lambda r: r["b"]["sim_ext_F1"]["S3-9D"],
 "B.sim_ext.S3.F1": lambda r: r["b"]["sim_ext_F1"]["S3"],
 "B.sim_ext.S3_minus_ARV": lambda r: r["b"]["sim_ext_S3_minus_ARV"][0],
 "B.testbed.S0.F1": lambda r: float(r["t8"].loc["S0", "F1"]),
 "B.testbed.S3.F1": lambda r: float(r["t8"].loc["S3", "F1"]),
 "B.testbed.S2.F1": lambda r: float(r["t8"].loc["S2", "F1"]),
 "B.testbed.A-RV.F1": lambda r: float(r["t8"].loc["A-RV", "F1"]),
 "B.testbed.S3_minus_S0": lambda r: r["b"]["testbed_S3_minus_S0"][0],
 "B.testbed.S3_minus_S0.ci_low": lambda r: r["b"]["testbed_S3_minus_S0"][1],
 "B.testbed.S3_minus_S0.ci_high": lambda r: r["b"]["testbed_S3_minus_S0"][2],
 "B.testbed.S3_minus_ARV": lambda r: r["b"]["testbed_S3_minus_ARV"][0],
 "B.testbed.S2_minus_S3": lambda r: r["b"]["testbed_S2_minus_S3"][0],
 "B.testbed.S2_vs_S3.p_holm": lambda r: r["b"]["testbed_wilcoxon_holm_S3_vs"]["S2"],
 "B.testbed.S3.overhead_ms": lambda r: float(r["t8"].loc["S3", "overhead_ms_step"]),
 "B.testbed.workload_ms": lambda r: float(r["t8"].loc["S3", "workload_ms_step"]),
 "B.sim_vs_testbed_spearman": lambda r: r["b"]["sim_vs_testbed_spearman"][0],
 "B.units": lambda r: r["bcounts"]["units_total"],
 "B.units_production": lambda r: r["bcounts"]["units_by_source"]["prod_db"],
 "B.units_deployed": lambda r: r["bcounts"]["units_deployed_without_error"],
 "B.routines_instrumented": lambda r: r["bcounts"]["routines_executed_with_instrumentation"],
 "B.objects_oracle": lambda r: r["bstruct"]["objects_ora"],
 "B.objects_pg": lambda r: r["bstruct"]["objects_pg"],
 "B.observation_slots": lambda r: r["bmodel"]["slots_gt"],
 "B.units_with_drift": lambda r: r["bmodel"]["localized_units"],
 "B.context_assumptions": lambda r: int(len(r["bctx"])),
 "B.rho_policy_security": lambda r: float(r["bcorr"].loc["d_policy", "d_security"]),
 "B.failure.units": lambda r: r["bbound"]["units"],
 "B.failure.failing": lambda r: r["bbound"]["failing"],
 "B.failure.rank": lambda r: r["bbound"]["weighted_rank"],
 "B.failure.chance_rank": lambda r: r["bbound"]["chance_rank"],
 "B.failure.top1": lambda r: r["bbound"]["top1"],
 "B.drift.context_share": lambda r: r["b"]["drift_share_nonzero"]["contextual"],
 "B.drift.role_share": lambda r: r["b"]["drift_share_nonzero"]["role"],
 "B.failure.EDI_auc": lambda r: r["b"]["failure_prediction_auc"]["edi_equal"][0] if "edi_equal" in r["b"]["failure_prediction_auc"] else
                       [v for k, v in r["b"]["failure_prediction_auc"].items() if "edi" in k.lower()][0][0],
 "B.failure.size_auc": lambda r: [v for k, v in r["b"]["failure_prediction_auc"].items() if "size" in k.lower() or "lines" in k.lower()][0][0],
}


def main():
    spec = json.loads(EXP.read_text())
    r = load()
    rows = []
    for e in spec["checks"]:
        try:
            if e["id"].startswith("dtest:"):          # dtest:<metric>|<comparison>|<field> from dual_profile_tests.csv
                mtr, comp, fld = e["id"][6:].split("|")
                got = test_row(r["dtests"], mtr, comp, fld)
            else:
                got = X[e["id"]](r)
            diff = abs(float(got) - float(e["paper_value"]))
            ok = diff <= e["tolerance"]
            rows.append(dict(id=e["id"], location=e["location"], expected=e["paper_value"], obtained=round(float(got), 6),
                             difference=round(diff, 6), tolerance=e["tolerance"], status="PASS" if ok else "FAIL",
                             source_file=e["source_file"]))
        except Exception as ex:          # missing output or extractor error is a failure, never a pass
            rows.append(dict(id=e["id"], location=e["location"], expected=e["paper_value"], obtained=None, difference=None,
                             tolerance=e["tolerance"], status=f"FAIL ({type(ex).__name__}: {ex})", source_file=e["source_file"]))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "reproduction_summary.json").write_text(json.dumps(rows, indent=1))
    n_fail = sum(not x["status"].startswith("PASS") for x in rows)
    md = ["# Reproduction summary", "", f"Checks: {len(rows)}; PASS: {len(rows) - n_fail}; FAIL: {n_fail}", "",
          "| id | manuscript location | expected | obtained | |diff| | tolerance | status | source |", "|---|---|---|---|---|---|---|---|"]
    for x in rows:
        md.append(f"| {x['id']} | {x['location']} | {x['expected']} | {x['obtained']} | {x['difference']} | {x['tolerance']} | {x['status']} | {x['source_file']} |")
    (RESULTS / "reproduction_summary.md").write_text("\n".join(md) + "\n")
    print(f"checks {len(rows)}  PASS {len(rows) - n_fail}  FAIL {n_fail}")
    for x in rows:
        if not x["status"].startswith("PASS"):
            print("  FAIL", x["id"], x["expected"], x["obtained"], x["status"])
    return n_fail


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
