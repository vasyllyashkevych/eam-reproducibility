#!/usr/bin/env bash
# Study B, levels 1-2: from the migration corpus to Tables 7, 8 and 10 without a database.
# Live PostgreSQL measurements (15 platform checks, COMMIT probes, instrumented routine runs,
# execution errors, testbed telemetry and probe counts) are read from data/study_b/recorded/.
# Level 3 (re-running the testbed itself) is run_study_b_testbed.sh.
set -euo pipefail
cd "$(dirname "$0")"
export EAM_PG_OFFLINE=1 PYTHONHASHSEED=0
mkdir -p e2e/out ops/out/telemetry logs
REC=../../data/study_b/recorded
cp $REC/e2e_ctx_checks.csv $REC/e2e_ctx_txn_probes.csv e2e/out/
cp $REC/ops_*.csv $REC/ops_meta.json ops/out/
cp $REC/telemetry/H_seed*.pkl ops/out/telemetry/
rm -f e2e/out/e2e_units_9d_initial.csv e2e/out/e2e_drift9_summary_initial.csv e2e/out/e2e_drift9_corr_initial.csv
step() { echo "== $1 ($(date -u +%H:%M:%S))"; shift; ( "$@" ) ; }
{
step "structure and seven code-level drift dimensions" bash -c "cd e2e && python3 o2p_structure.py"
step "context and goal dimensions (recorded PG17 checks)" bash -c "cd e2e && python3 o2p_ctx_goal.py"
step "transaction-control refinement (recorded probes)" bash -c "cd e2e && python3 o2p_ctx_txn.py"
step "independent failure classes" bash -c "cd e2e && python3 ont_independent.py"
step "corpus experiment: S0-S3, S3-O x 40 seeds (Table 7)" bash -c "cd e2e && E2E_TAG= python3 e2e_adaptation.py"
step "corpus experiment: ten variants x 40 seeds (comparison mechanisms, S3-9D)" bash -c "cd e2e && E2E_TAG=_ext E2E_VARIANTS=S0,S1,S2,S3,S3-O,A-RB,A-RX,A-AM,A-RV,S3-9D python3 e2e_adaptation.py"
step "testbed detectors on recorded telemetry (Table 8)" bash -c "cd ops/src && python3 ops_detectors.py"
step "failure prediction (Table 10)" bash -c "cd ../../code && EAM_STUDY_B_DIR=../docs/study_b/e2e/out EAM_RESULTS_DIR=../docs/study_b/out_check python3 boundary_real.py"
step "comparison with the author's original outputs" python3 compare_with_reference.py
} 2>&1 | tee logs/study_b_offline_log.txt
