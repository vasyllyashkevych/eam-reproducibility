# Data dictionary

## Study A (generated; written to `results/`)
* `controlled_runs.csv` — one row per (tag, variant, seed). `tag`: main | coverage | sanctioned | evidence_gap | sigma=…,amp=…; `accuracy`, `macro_f1` (five evolution states), `critical_delay` (steps after step 100), `false_critical` (critical labels before step 100).
* `controlled_detection_runs.csv` — per-dimension detection per run; `controlled_prf_by_dim.csv` — TP, FP, FN, P, R, F1, mean delay (steps) per tag/variant/dimension (θ = 0.35).
* `controlled_tests.csv` — Friedman statistic, paired differences with 95% bootstrap intervals (seed 0), Wilcoxon p, Holm-adjusted p, Vargha–Delaney Â12.
* `controlled_weight_sensitivity.csv` — 100 Dirichlet weight draws plus the profile weights; `controlled_theta_sensitivity.csv` — θ from 0.20 to 0.50.
* Time index: step 1–120; phases normal 1–19, degraded 20–49, vulnerable 50–79, anomalous 80–99, critical 100–120.

## Joint ablation (`results/dual_profile_*`)
* `dual_profile_runs.csv` — variant, seed, macro_f1, false_critical, `coverage` (share of property-steps from step 20 with a valid probe), `recall_uniform`, `recall_coupled`, `delay`, `rebuilds` (probe rebuild count; not execution time), defect counts.
* `dual_profile_tests.csv` — paired comparisons and the 2×2 interaction contrast (versioned/both − versioned/run − static/both + static/run).
* `dual_profile_shock_runs.csv` — goal shift +0.45 at step 28 inside the transition window; `flagged_in_window`, `critical_delay`, `goal_recall_after_window`.

## Study C (`data/study_c/`, `results/security_*`)
* `snapshots_manifest.csv` — repo, seq (0–49), commit_hash, ts (Unix time), tag, `version_at_snapshot` (latest release reachable from the commit).
* `release_tags.csv` — repo, tag, creatordate_unix (pre-releases are filtered by the script).
* `code_drift_snapshots.csv` — six code-derived drift components, `idi` (integrated code drift index), `has_release`.
* `monitoring_alerts.csv` — alerts of the static and adaptive EWMA strategies per snapshot.
* `security_drift_snapshots.csv` — per snapshot: `d_sec_known` (Eq. (8) over advisories published by the snapshot date), `dd_sec` (change from the previous snapshot), joined code drift and alerts. Transitions are rows with seq > 0 (245).
* `security_pinned_deployments.csv` — per release (454): advisories, `d_sec_365d/730d/1825d` (empty when the horizon is after the evaluation instant).
* `security_exposure_windows.csv` — per advisory on the newest-release track: `window_days` from disclosure to the first unaffected release.

## Study B public aggregates (`data/study_b_public/`)
* `e2e_runs.csv` — corpus experiment, one row per seed (1–40) and variant (S0, S1, S2, S3, S3-O): PCR, PCRw, MRSR, P, R, F1, MTTD (steps), LA, FAR, `slots_optimized`, `t_adapt` (seconds), `required` slots.
* `e2e_runs_ext.csv` — deterministic re-run with ten variants (adds A-RB, A-RX, A-AM, A-RV, S3-9D).
* `ops_runs_method.csv` — PostgreSQL 17 testbed, one row per run (seeds 1–10) and variant: events, TP, FP, P, R, F1, MTTD (steps), LA, FAR, probes, `probes_obj`, `overhead_ms_step`, `workload_ms_step`.
* `e2e_drift9_summary.csv` — per dimension: share of units with drift > 0, mean drift, 90th percentile, share above θ (Fig. 5).
* `e2e_drift9_corr.csv` — Spearman correlation matrix of the nine unit-level drift measures.
* `e2e_structure_stats.json`, `e2e_model_info.json`, `study_b_counts.json` — corpus counts, observation slots, deployment and instrumentation counts.
* `e2e_ctx_checks.csv` — the 15 contextual assumptions checked on PostgreSQL 17 (generic platform behaviour).
* `e2e_tests.csv` — statistical tests written by `e2e_adaptation.py` (for comparison with `metrics_statistics.py`).
* `first_run/` — statistical outputs of the author's first testbed run, kept only for comparison; the paper uses the 18 November 2026 run.
* `boundary_*.csv/json` — failure-prediction outputs of Table 10 (442 units with execution evidence, 108 failing; failures caused by missing testbed stubs excluded).

## Study B full materials (`study_b/`)
* `ds/O2P_GOLDEN_TESTSET_v03_full.csv` — one row per migration unit (1,802): `input_db_query` (Oracle PL/SQL), `output_db_query` (PostgreSQL), `source` (prod_db, prev_test_set, parsed_live_sql, prev_team_view, prev_team_triggers); `…_metadata.json` gives keyword statistics per unit.
* `recorded/e2e_ctx_checks.csv` — the 15 contextual assumptions: Oracle value, value measured on PostgreSQL 17.11, violated flag.
* `recorded/e2e_ctx_txn_probes.csv` — COMMIT probes in functions, procedures and DO blocks on PostgreSQL 17.11.
* `recorded/ops_txn_validation.csv` — instrumented calls of routines with transaction control (290 routines).
* `recorded/ops_exec_errors.csv` — execution errors per unit, used for the independent failure classes (Table 10).
* `recorded/ops_deploy.csv`, `ops_objects.csv`, `ops_definer_txn_conflict.csv` — deployment of every unit into the template database and the matched catalogue objects (795 units without error).
* `recorded/ops_runs.csv`, `ops_defects.csv`, `ops_meta.json` — per run and variant: probe counts, measured overhead (ms/step), injected defects, run metadata.
* `recorded/telemetry/H_seed1..10.pkl` — telemetry of the ten testbed runs (pg_stat_user_functions, pg_stat_statements, pg_stat_user_tables, catalogue state, csvlog errors, probe results per step).
* `reference/` — the author's original outputs of the same scripts, used by `compare_with_reference.py`.
* Outputs regenerated in `e2e/out/` and `ops/out/` have the same names as in `reference/`; `e2e_runs.csv` columns are listed in the Study B public-aggregate section above.
* `study_b/run_records/level3_testbed_run_2026-11-18.txt` — console log of the level-3 testbed run that produced `study_b/recorded/`.
