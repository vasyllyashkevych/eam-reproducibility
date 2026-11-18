"""Generate EXPERIMENT_RESULTS.md: every experimental result of PAPER021433, read from the regenerated outputs.

    python3 results_report.py [OUT.md]
Run after run_all.sh (Studies A, C, ablation, Study B aggregates) and study_b/run_study_b_offline.sh.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from paths import DATA, PKG, RESULTS

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else PKG / "EXPERIMENT_RESULTS.md"
SB = PKG / "study_b"
L = []
def h(t): L.append(f"\n## {t}\n")
def p(t): L.append(t + "\n")
def table(df, fmt="{:.3f}"):
    cols = list(df.columns)
    L.append("| " + " | ".join([df.index.name or ""] + cols) + " |")
    L.append("|" + "---|" * (len(cols) + 1))
    for idx, row in df.iterrows():
        cells = [fmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in row]
        L.append("| " + " | ".join([str(idx)] + cells) + " |")
    L.append("")
def ms(x): return f"{x.mean():.3f} ± {x.std():.3f}"

L.append("# Experimental results — PAPER021433\n")
L.append("All values are read from the regenerated outputs of this repository (no hand-typed numbers). "
         "Means over runs; ± is the standard deviation across runs. Section numbers refer to the final manuscript.\n")

# ------------------------------------------------------------------ Study A
R = pd.read_csv(RESULTS / "controlled_runs.csv")
T = pd.read_csv(RESULTS / "controlled_tests.csv")
h("Study A — controlled drift injection (RQ1; Section 7.1, Table 5, Fig. 4)")
rows = [("main", "A", "A: window detector + PDI"), ("main", "B", "B: reference + maximum"), ("main", "C", "C: reference + PDI"),
        ("main", "C0", "C0: proposed"), ("coverage", "C0|context", "C0, telemetry only"),
        ("coverage", "C0|configuration,topology,architecture", "C0, configuration + structure"),
        ("coverage", "C0|context,configuration,topology,architecture", "C0, telemetry + configuration + structure"),
        ("sanctioned", "C0", "C0, planned release, static reference"), ("sanctioned", "C0-ref", "C0, planned release, versioned reference"),
        ("evidence_gap", "C0-gap0", "C0, missing evidence set to zero"), ("evidence_gap", "C0-gapX", "C0, observed-dimension rule (10)")]
tab = []
for tag, v, lab in rows:
    x = R[(R.tag == tag) & (R.variant == v)]
    tab.append(dict(variant=lab, accuracy=ms(x.accuracy), macro_F1=ms(x.macro_f1), false_critical_before_100=ms(x.false_critical), runs=len(x)))
table(pd.DataFrame(tab).set_index("variant"))
D = pd.read_csv(RESULTS / "controlled_detection_runs.csv") if (RESULTS / "controlled_detection_runs.csv").exists() else None
fr = T[(T.tag == "main") & (T.comparison == "Friedman") & (T.metric == "macro_f1")].iloc[0]
p(f"* Friedman (macro-F1, four variants, 40 runs): chi2 = {fr.stat:.1f}, p = {fr.p:.1e}.")
for comp in ("C0 - A", "C0 - B", "C0 - C"):
    q = T[(T.tag == "main") & (T.metric == "macro_f1") & (T.comparison == comp)].iloc[0]
    p(f"* {comp}: difference {q['diff']:.3f} [{q.ci_low:.3f}; {q.ci_high:.3f}], p_Holm = {q.p_holm:.1e}, A12 = {q.a12:.2f}.")
q = T[(T.tag == "sanctioned") & (T.metric == "macro_f1")].iloc[-1]
p(f"* Versioned vs static reference after the approved release: {q['diff']:.3f} [{q.ci_low:.3f}; {q.ci_high:.3f}], A12 = {q.a12:.2f}.")
F = pd.read_csv(RESULTS / "controlled_prf_by_dim.csv")
h("Study A — detection per dimension (Table 6, theta = 0.35)")
a = F[(F.tag == "main") & (F.variant == "A")].set_index("dim")[["P", "R", "F1"]].add_suffix(" (A)")
c = F[(F.tag == "main") & (F.variant == "C0")].set_index("dim")[["P", "R", "F1", "delay"]].add_suffix(" (C0)")
table(a.join(c), "{:.2f}")
Wt = pd.read_csv(RESULTS / "controlled_weight_sensitivity.csv"); d = Wt[Wt.weights == "dirichlet"].macro_f1
Th = pd.read_csv(RESULTS / "controlled_theta_sensitivity.csv").set_index("theta")
p(f"* 100 Dirichlet weight vectors: median macro-F1 {d.median():.3f} (IQR {d.quantile(.25):.3f}–{d.quantile(.75):.3f}; min {d.min():.3f}); profile weights {Wt[Wt.weights == 'profile'].macro_f1.iloc[0]:.3f}.")
p(f"* Detection threshold 0.50 → 0.20: recall {Th.loc[0.5, 'recall']:.2f} → {Th.loc[0.2, 'recall']:.2f}; precision {Th.loc[0.5, 'precision']:.2f} → {Th.loc[0.2, 'precision']:.2f}.")
for tag in ("sigma=0.03,amp=1.0", "sigma=0.05,amp=1.0", "sigma=0.05,amp=0.5"):
    vals = {v: R[(R.tag == tag) & (R.variant == v)].macro_f1.mean() for v in ("C0", "C", "B")}
    p(f"* Noise/amplitude {tag}: C0 {vals['C0']:.3f}, C {vals['C']:.3f}, B {vals['B']:.3f}.")

# ------------------------------------------------------------------ ablation
J = pd.read_csv(RESULTS / "dual_profile_runs.csv")
JT = pd.read_csv(RESULTS / "dual_profile_tests.csv")
h("Joint ablation of the two drift profiles (RQ1, RQ2; Section 7.4, Table 9)")
order = ["static/run", "static/rel", "static/both", "versioned/run", "versioned/rel", "dual (proposed)", "full regeneration", "dual, incomplete PHI"]
tab = [dict(variant=v, macro_F1=ms(J[J.variant == v].macro_f1), false_critical=ms(J[J.variant == v].false_critical),
            coverage=ms(J[J.variant == v].coverage), recall_uniform=ms(J[J.variant == v].recall_uniform),
            recall_change_coupled=ms(J[J.variant == v].recall_coupled), probe_rebuilds=ms(J[J.variant == v].rebuilds)) for v in order]
table(pd.DataFrame(tab).set_index("variant"))
for m in ("recall_uniform", "coverage", "recall_coupled"):
    q = JT[(JT.metric == m) & (JT.comparison == "interaction")].iloc[0]
    p(f"* Interaction contrast ({m}): {q['diff']:.3f} [{q.ci_low:.4f}; {q.ci_high:.4f}].")
for comp in ("dual (proposed) - static/both", "dual (proposed) - full regeneration", "dual (proposed) - dual, incomplete PHI"):
    for m in ("coverage", "recall_uniform"):
        q = JT[(JT.metric == m) & (JT.comparison == comp)].iloc[0]
        p(f"* {comp}, {m}: {q['diff']:.3f} [{q.ci_low:.3f}; {q.ci_high:.3f}], p_Holm = {q.p_holm:.1e}, A12 = {q.a12:.2f}.")
fr = JT[(JT.metric == "recall_uniform") & (JT.comparison == "Friedman")].iloc[0]
p(f"* Friedman (uniform-defect recall, 8 variants): chi2 = {fr.stat:.1f}, p = {fr.p:.1e}.")
p(f"* Probe rebuilds, full regeneration / dual profile: {J[J.variant == 'full regeneration'].rebuilds.mean() / J[J.variant == 'dual (proposed)'].rebuilds.mean():.1f}× (counts, not execution time).")
K = pd.read_csv(RESULTS / "dual_profile_shock_runs.csv")
for v in K.variant.unique():
    k = K[K.variant == v]
    p(f"* Masking scenario, {v}: shift flagged in {int(k.flagged_in_window.sum())}/{len(k)} runs; goal recall after window {k.goal_recall_after_window.mean():.2f}; mean delay {k.critical_delay.mean():.2f} steps.")

# ------------------------------------------------------------------ Study B
B = json.loads((RESULTS / "study_b_statistics.json").read_text())
T7 = pd.read_csv(RESULTS / "study_b_table7.csv").set_index("variant")
T8 = pd.read_csv(RESULTS / "study_b_table8.csv").set_index("variant")
CNT = json.loads((DATA / "study_b_public" / "study_b_counts.json").read_text())
ST = json.loads((DATA / "study_b_public" / "e2e_structure_stats.json").read_text())
MI = json.loads((DATA / "study_b_public" / "e2e_model_info.json").read_text())
h("Study B — corpus and drift profile (Section 6.2, 7.2, Fig. 5)")
p(f"* Units: {CNT['units_total']} (production database {CNT['units_by_source']['prod_db']}); Oracle objects {ST['objects_ora']}, PostgreSQL objects {ST['objects_pg']}.")
p(f"* Units deployed on the PostgreSQL 17.11 testbed without error: {CNT['units_deployed_without_error']}; routines run with instrumentation: {CNT['routines_executed_with_instrumentation']}.")
p(f"* Object-property observation slots: {MI['slots_gt']}; units with drift above the threshold in at least one dimension: {MI['localized_units']}.")
S9 = pd.read_csv(DATA / "study_b_public" / "e2e_drift9_summary.csv").set_index("dimension")[["share_pos", "mean", "share_sig"]]
table(S9)
C9 = pd.read_csv(DATA / "study_b_public" / "e2e_drift9_corr.csv", index_col=0)
p(f"* Spearman correlation policy–security drift: {C9.loc['d_policy', 'd_security']:.2f}.")
h("Study B — corpus experiment after migration (Table 7, deterministic re-run, 40 runs)")
t7 = T7.loc[["S0", "S1", "S2", "S3", "S3-O"], ["PCRw", "MRSR", "P", "R", "F1", "F1_sd", "MTTD", "LA", "FAR", "slots_optimized", "t_adapt_s"]]
table(t7)
p(f"* Friedman (F1, five variants): chi2 = {B['sim_friedman_chi2']:.1f}, p = {B['sim_friedman_p']:.1e}.")
p(f"* Wilcoxon, S3 vs other variants, Holm-adjusted p: " + ", ".join(f"{k} {v:.1e}" for k, v in B['sim_wilcoxon_holm_S3_vs'].items()) + ".")
p(f"* TOST S3 vs S2 (margin ±0.02 F1): p = {B['sim_tost_S3_S2_F1_margin_0.02_p']:.1e} (equivalent).")
p(f"* Ten-variant re-run, F1: " + ", ".join(f"{k} {v:.3f}" for k, v in sorted(B['sim_ext_F1'].items())) + ".")
d = B["sim_ext_S3_minus_ARV"]; p(f"* S3 − A-RV (corpus experiment): {d[0]:.3f} [{d[1]:.3f}; {d[2]:.3f}].")
p("* `t_adapt_s` is wall-clock time on the verification machine and changes between machines.")
h("Study B — PostgreSQL 17 testbed with measured telemetry (Table 8, 10 runs)")
table(T8[["object_probes", "P", "R", "F1", "F1_sd", "MTTD", "LA", "overhead_ms_step", "workload_ms_step"]])
for key, lab in (("testbed_S3_minus_S0", "S3 − S0"), ("testbed_S3_minus_ARV", "S3 − A-RV"), ("testbed_S2_minus_S3", "S2 − S3")):
    d = B[key]; p(f"* {lab}: {d[0]:.3f} [{d[1]:.3f}; {d[2]:.3f}] (paired t interval).")
p(f"* Holm-adjusted Wilcoxon p, S3 vs S2: {B['testbed_wilcoxon_holm_S3_vs']['S2']:.3f}.")
rho = B["sim_vs_testbed_spearman"]; p(f"* Rank agreement corpus experiment vs testbed (F1, {rho[2]} variants): Spearman rho = {rho[0]:.2f}, p = {rho[1]:.3f}.")
ev = SB / "ops" / "out" / "ops_events_det.csv"
if ev.exists():
    E = pd.read_csv(ev)
    s = E[(E.variant == "S3") & (E.detector == "rewma") & (E.detected)]
    cat = s.by_signal.isin(["pg_catalog_objects", "role_table_grants", "pgaudit"]).mean()
    p(f"* Share of S3 detections (robust EWMA detector) produced by catalogue, privilege and audit signals: {cat:.2f}.")
h("Study B — limits of unit-level failure prediction (Section 7.5, Table 10)")
FP = pd.read_csv(DATA / "study_b_public" / "boundary_failure_prediction.csv").set_index("indicator")
table(FP[["auc", "auc_lo", "auc_hi", "flagged", "f1"]])
BS = json.loads((DATA / "study_b_public" / "boundary_summary.json").read_text())
p(f"* Units with execution evidence: {int(BS['units'])}; failing because of migrated code: {int(BS['failing'])}.")
p(f"* Rank of the expected dimension per failure class: {BS['weighted_rank']:.2f} vs {BS['chance_rank']:.2f} by chance; first in {int(BS['top1'])} of {int(BS['classes'])} classes.")

# ------------------------------------------------------------------ Study C
C = json.loads((RESULTS / "security_drift_summary.json").read_text())
h("Study C — security drift of five libraries (RQ3; Section 7.3, Fig. 6)")
p(f"* Snapshots 250; consecutive transitions {C['transitions']}; advisory-based exposure changes {C['security_events']} ({C['exposure_increases']} increases, {C['exposure_decreases']} decreases).")
p(f"* Code-based detectors on these events: recall static {C['alert_static_recall_on_security_events']:.2f}, EWMA {C['alert_ewma_recall_on_security_events']:.2f}; alarm rate on the other {C['transitions'] - C['security_events']} transitions: static {C['alert_static_rate_elsewhere']:.3f}, EWMA {C['alert_ewma_rate_elsewhere']:.3f}.")
p(f"* Increases with IDI < 0.05: {C['exposure_increases_without_code_change']} of {C['exposure_increases']}; Spearman IDI vs exposure rho = {C['spearman_idi_vs_dsec'][0]:.3f}, p = {C['spearman_idi_vs_dsec'][1]:.3f}, n = {C['transitions']}.")
p(f"* Releases {C['pinned_releases']}; linked later to an advisory: {C['pinned_with_any_advisory']}.")
tab = [dict(horizon=f"{h_} days", evaluable=C[f'pinned_{h_}d']['evaluable'], share_exposed=C[f'pinned_{h_}d']['share_exposed'],
            share_ge_0_7=C[f'pinned_{h_}d']['share_ge_0.7'], mean_index=C[f'pinned_{h_}d']['mean']) for h_ in (365, 730, 1825)]
table(pd.DataFrame(tab).set_index("horizon"))
p("* Share exposed after two years by library: " + ", ".join(f"{k} {v:.3f}" for k, v in C["pinned_by_repo_730d"].items()) + ".")
Wn = pd.read_csv(RESULTS / "security_exposure_windows.csv")
top = Wn.sort_values("window_days").iloc[-1]
p(f"* Newest-release track: {int((Wn.window_days == 0).sum())} of {len(Wn)} advisories had no exposure window; longest {int(top.window_days)} days ({top.repo}, {top.advisory}).")

OUT.write_text("\n".join(L) + "\n")
print("written", OUT)
