#!/usr/bin/env bash
# Study B, level 3: rebuild the PostgreSQL 17 testbed and re-measure everything that the offline level reads
# from study_b/recorded/. Needs PostgreSQL 17 binaries (initdb, pg_ctl, psql) on PATH, or the Docker service in
# docker-compose.yml (then set PG_EXTERNAL=1 and OPS_PGLOG=$PWD/pg/cluster_log).
# Testbed telemetry depends on timing and the machine, so detection metrics are compared statistically with the
# recorded run (compare_with_reference.py prints the differences); exact equality is not expected.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONHASHSEED=0
mkdir -p e2e/out ops/out/telemetry logs
CL="$PWD/pg/cluster"
if [ "${PG_EXTERNAL:-0}" != "1" ]; then
  if [ ! -d "$CL" ]; then
    initdb -D "$CL" -U postgres --auth=trust --locale=en_US.UTF-8 >/dev/null
    cat pg/postgresql.testbed.conf >> "$CL/postgresql.conf"
  fi
  pg_ctl -D "$CL" -l logs/postgres_server.log -w start
  export OPS_PGLOG="$CL/log"
  trap 'pg_ctl -D "$CL" -m fast stop' EXIT
fi
psql -h localhost -p 55432 -U postgres -Xqc "CREATE DATABASE o2p" 2>/dev/null || true
step() { echo "== $1 ($(date -u +%H:%M:%S))"; shift; ( "$@" ); }
{
step "structure" bash -c "cd e2e && python3 o2p_structure.py"
step "context and goal dimensions (live PG17 checks)" bash -c "cd e2e && python3 o2p_ctx_goal.py"
step "deploy 1,802 units into template database o2p_tpl" bash -c "cd ops/src && python3 testbed_deploy.py"
step "infer stub tables from execution feedback" bash -c "cd ops/src && python3 infer_schema.py"
step "baseline executability" bash -c "cd ops/src && python3 baseline_probe.py"
step "instrumented COMMIT/ROLLBACK runs" bash -c "cd ops/src && python3 txn_validate.py"
step "transaction-control refinement (live probes)" bash -c "cd e2e && python3 o2p_ctx_txn.py"
step "execution errors for the failure classes" bash -c "cd ops/src && python3 exec_gold.py"
step "independent failure classes" bash -c "cd e2e && python3 ont_independent.py"
step "corpus experiment (Table 7)" bash -c "cd e2e && E2E_TAG= python3 e2e_adaptation.py"
step "corpus experiment, ten variants" bash -c "cd e2e && E2E_TAG=_ext E2E_VARIANTS=S0,S1,S2,S3,S3-O,A-RB,A-RX,A-AM,A-RV,S3-9D python3 e2e_adaptation.py"
step "testbed: 10 runs x 100 steps, 120 operations per step (about 1.5 h)" bash -c "cd ops/src && python3 testbed_run.py"
step "detectors on the new telemetry (Table 8)" bash -c "cd ops/src && python3 ops_detectors.py"
step "failure prediction (Table 10)" bash -c "cd ../code && EAM_STUDY_B_DIR=../study_b/e2e/out EAM_RESULTS_DIR=../study_b/out_check python3 boundary_real.py"
step "comparison with the recorded run" bash -c "python3 compare_with_reference.py || true"
} 2>&1 | tee logs/study_b_testbed_log.txt
