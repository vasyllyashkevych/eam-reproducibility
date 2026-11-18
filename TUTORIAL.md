# Step-by-step tutorial: reproducing the experiments by hand

This tutorial runs every experiment of PAPER021433 one command at a time, so that each intermediate file can be
inspected. The one-command alternatives are `run_all.sh` and `study_b/run_study_b_offline.sh`.
Times were measured on an Apple M2 laptop (8 cores, 16 GB RAM, no GPU).

**Conventions.** Commands are run from the repository root unless a `cd` is shown. “Check” lines give the value
printed in the paper; your output must match it to the printed number of digits (wall-clock times excepted).

---

## 0. Environment (5 min)

```bash
git clone <repository> eam-reproducibility && cd eam-reproducibility   # or unzip the archive
shasum -a 256 -c MANIFEST.sha256 --quiet && echo "inputs intact"     # Linux: sha256sum -c MANIFEST.sha256
python3 --version                                                     # 3.14 used by the author; 3.12+ should work
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt                                       # numpy, pandas, scipy, matplotlib, pillow, pytest
```

Every script writes into `results/` (Studies A, C, ablation) or `study_b/e2e/out`, `study_b/ops/out` (Study B).
Delete those folders to start from scratch.

---

## 1. Study A — controlled drift injection (RQ1; Section 7.1, Tables 5–6, Fig. 4) — about 10 s

```bash
cd code
python3 controlled_drift.py
```

What happens: nine AR(1) series (120 steps) receive the injection plan in `data/study_a/injection_plan_and_seeds.json`;
state thresholds are learned on seeds 101–110 (Eq. (13)) and four variants are evaluated on seeds 1–40.

Inspect:

```bash
python3 -c "import pandas as pd; R=pd.read_csv('../results/controlled_runs.csv'); \
print(R[R.tag=='main'].groupby('variant')[['accuracy','macro_f1','false_critical']].mean().round(3))"
```

Check: macro-F1 C0 = **0.968**, C = 0.958, B = **0.530**, A = 0.167; false critical states B = 14.5 per run.
Further outputs: `controlled_tests.csv` (Friedman χ² = 114.5; C0 − C = 0.010 [0.006; 0.014]),
`controlled_prf_by_dim.csv` (Table 6), `controlled_weight_sensitivity.csv` (median 0.905 over 100 weight draws),
`controlled_theta_sensitivity.csv` (recall 0.55 → 0.88 when θ goes from 0.50 to 0.20).
Rows with `tag == "sanctioned"` are the approved-release experiment (static 0.861 vs versioned 0.969).

## 2. Joint ablation of the two drift profiles (Section 7.4, Table 9) — about 3 s

```bash
python3 dual_profile.py          # still in code/
python3 -c "import pandas as pd; J=pd.read_csv('../results/dual_profile_runs.csv'); \
print(J.groupby('variant')[['macro_f1','coverage','recall_uniform','recall_coupled','rebuilds']].mean().round(3))"
```

Check: dual profile coverage **0.915**, uniform-defect recall **0.925**, rebuilds **54.2**; full regeneration 355.5
rebuilds; versioned reference with the runtime profile only: recall 0.812.
`dual_profile_tests.csv`, row `interaction`: recall contrast 0.113 [0.090; 0.136].
`dual_profile_shock_runs.csv`: the mask alone misses the goal shift in 40/40 runs; with CriticalCheck it is flagged in 40/40.

To see the trigger rule of Eq. (14) in isolation:

```bash
python3 -m pytest -q ../tests/test_algorithm_triggers.py
```

## 3. Study C — security drift of five libraries (RQ3; Section 7.3, Fig. 6) — about 2 s

```bash
python3 security_cvss.py         # offline: frozen OSV cache, evaluation instant 2026-11-05 23:40
```

Inputs: `data/study_c/snapshots_manifest.csv` (250 snapshots and the release reachable from each commit),
`release_tags.csv`, `code_drift_snapshots.csv`, `monitoring_alerts.csv`, `osv_cache.json`.
Check in `results/security_drift_summary.json`: `transitions` 245, `exposure_increases` 3,
`exposure_decreases` 2, `alert_static_rate_elsewhere` 0.113, `alert_ewma_rate_elsewhere` 0.108,
`spearman_idi_vs_dsec` [−0.118, 0.065], `pinned_730d.share_exposed` 0.311.
(`EAM_ONLINE=1 python3 security_cvss.py` queries the live OSV API instead; results then follow today's advisories.)

## 4. Study B — Oracle → PostgreSQL migration (RQ2; Sections 6.2, 7.2, 7.5)

Study B has three levels. Levels 1 and 2 need no database; they read the measurements that were recorded on the
PostgreSQL 17.11 testbed from `study_b/recorded/`. Level 3 re-creates the testbed.

```bash
cd ../study_b
export EAM_PG_OFFLINE=1 PYTHONHASHSEED=0
mkdir -p e2e/out ops/out/telemetry
cp recorded/e2e_ctx_checks.csv recorded/e2e_ctx_txn_probes.csv e2e/out/
cp recorded/ops_*.csv recorded/ops_meta.json ops/out/
cp recorded/telemetry/H_seed*.pkl ops/out/telemetry/
```

### Level 1 — from the migration corpus to Tables 7 and 10 (about 25 min)

| Step | Command (in `study_b/`) | Output | Check |
|---|---|---|---|
| 1. Structural models, seven code-level drift operators (Table 2) | `cd e2e && python3 o2p_structure.py` | `e2e_units.csv`, `e2e_objects.csv`, `e2e_structure_stats.json` | 1,802 units; 2,678 Oracle and 2,910 PostgreSQL objects |
| 2. Context (15 assumptions, Eq. (6)) and goal drift | `python3 o2p_ctx_goal.py` | `e2e_units_9d.csv`, `e2e_drift9_summary.csv` | context drift in 60.3% of units; role 2.4% |
| 3. Transaction-control refinement | `python3 o2p_ctx_txn.py` | `e2e_ctx_txn_*.csv` (updates the nine-dimension table) | Spearman policy–security 0.94 (`e2e_drift9_corr.csv`) |
| 4. Independent failure classes | `python3 ont_independent.py` | `ont_indep_gold.csv` | — |
| 5. Corpus experiment, S0–S3 and S3−O, 40 seeds | `E2E_TAG= python3 e2e_adaptation.py` | `e2e_runs.csv` | F1: S0 **0.369**, S1 0.479, S2 **0.770**, S3 **0.766**, S3−O 0.603 |
| 6. Corpus experiment, ten variants | `E2E_TAG=_ext E2E_VARIANTS=S0,S1,S2,S3,S3-O,A-RB,A-RX,A-AM,A-RV,S3-9D python3 e2e_adaptation.py` | `e2e_runs_ext.csv` | A-RX 0.428, A-RV 0.537, S3-9D 0.765 |
| 7. Failure prediction (Table 10) | `cd ../../code && EAM_STUDY_B_DIR=../study_b/e2e/out EAM_RESULTS_DIR=../study_b/out_check python3 boundary_real.py` | `study_b/out_check/boundary_failure_prediction.csv` | EDI AUC **0.639** [0.578; 0.702]; 442 units, 108 failures |

### Level 2 — testbed detectors on the recorded telemetry (Table 8, about 1 min)

```bash
cd ../study_b/ops/src && python3 ops_detectors.py      # reads ../out/telemetry/H_seed1..10.pkl
```

Output `ops/out/ops_runs_method.csv`. Check: F1 S0 **0.097**, S3 **0.519**, S2 **0.540**, A-RV 0.485.

### Compare levels 1–2 with the author's original outputs

```bash
cd ../.. && python3 compare_with_reference.py
```

Every file must print `SAME` (wall-clock columns are excluded). The script also prints, for information, the first non-deterministic
corpus-experiment run that produced an earlier version of Table 7; the published Table 7 is the deterministic re-run.

### Level 3 — rebuild the PostgreSQL 17 testbed (optional, about 2 h)

Requirements: PostgreSQL 17 (`initdb`, `pg_ctl`, `psql` on PATH) **or** Docker, and `pip install -r requirements-testbed.txt`.

```bash
bash run_study_b_testbed.sh                 # local PostgreSQL 17: creates pg/cluster on port 55432
# or, with Docker:
docker compose up -d && PG_EXTERNAL=1 OPS_PGLOG=$PWD/pg/cluster_log bash run_study_b_testbed.sh
```

The script deploys all 1,802 units into a template database (795 deploy without error), infers stub tables,
runs the instrumented COMMIT/ROLLBACK checks and the execution-error collection, and then runs the testbed:
10 runs × 100 steps × 120 operations per step, with defects injected as DDL mutations. Telemetry, statement
statistics and server errors are timing-dependent, so Table 8 will not repeat digit for digit; the comparison script
prints the differences to the recorded run. The recorded run in `study_b/recorded/` is the level-3 run of
18 November 2026 (Apple M2, 8 cores, 16 GB RAM, macOS 27.2.1, PostgreSQL 17.11, Python 3.14.0; 1 h 53 min).
In that run Table 7 and the drift tables were identical to level 1; Table 8 and Table 10 are the values printed in the paper.

## 5. Statistics, figures and the full number check

```bash
cd ../code                       # from study_b/
python3 metrics_statistics.py    # Table 7/8 statistics from the per-run files (Friedman, Holm, TOST, intervals)
python3 figures.py               # Fig. 4–6 (600 dpi)
python3 diagrams.py              # Fig. 1–3 (SVG; PNG if rsvg-convert is installed)
python3 check_expected.py        # 136 numbers of the paper vs regenerated outputs -> results/reproduction_summary.md
python3 results_report.py        # all results in one file -> EXPERIMENT_RESULTS.md
cd .. && python3 -m pytest -q tests
```

`RESULTS_TRACEABILITY.csv` maps every number of the paper to the file and command that produce it.

## 6. Troubleshooting

* `KeyError … missing from the frozen OSV cache` — `data/study_c/osv_cache.json` was changed; restore it.
* `FileNotFoundError: …/recorded/e2e_ctx_checks.csv` — run Study B from inside `study_b/` with `EAM_PG_OFFLINE=1`.
* `psycopg.OperationalError` in level 3 — the cluster is not running on localhost:55432.
* A value differs in the third decimal — check that `PYTHONHASHSEED=0` is set for Study B and that inputs pass the SHA-256 check.
