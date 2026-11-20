# Study B — Oracle-to-PostgreSQL migration (RQ2)

Study B tests EAM after a large, approved evolution of an information system: 1,802 Oracle PL/SQL units migrated to
PostgreSQL 17. It measures the nine drift dimensions of every unit, selects the probes that must be updated (S3) and
compares this with static monitoring (S0), partial adaptation (S1), full regeneration (S2), an ablation without
ontology (S3−O), all nine dimensions (S3-9D) and four mechanisms from related work (A-RB, A-RX, A-AM, A-RV).

| Level | Script | Database | Reproduces | Verified |
|---|---|---|---|---|
| 1 | `run_study_b_offline.sh` (first steps) | no (recorded PG17 checks) | drift profile, Fig. 5, Table 7, comparison mechanisms, Table 10 | yes — identical to the original outputs |
| 2 | `run_study_b_offline.sh` (detectors) | no (recorded telemetry) | Table 8 | yes — identical |
| 3 | `run_study_b_testbed.sh` | PostgreSQL 17 (local or `docker-compose.yml`) | re-deployment, new telemetry, Table 8 again | re-run on 18 November 2026 (1 h 53 min, Apple M2, PostgreSQL 17.11); its measurements are the ones in `recorded/`; timing-dependent |

Order of the scripts, inputs and expected values: `../TUTORIAL.md`, section 4.
Folder layout follows the original project layout (`e2e/`, `ops/src/`) so that the scripts run unchanged; the only
edits are relative paths and the offline switch `EAM_PG_OFFLINE=1` in `e2e/o2p_ctx_goal.py` and `e2e/o2p_ctx_txn.py`.

* `run_records/level3_testbed_run_2026-11-18.txt` is the console log of the level-3 run whose measurements are in `data/study_b/recorded/` (Apple M2, 8 cores, 16 GB RAM, macOS 27.2.1, PostgreSQL 17.11, Python 3.14.0; 1 h 53 min).
* `run_records/level1-2_offline_run_clean_copy.txt` is the console log of the offline run (levels 1–2) that was verified against `data/study_b/reference/`. Both run records are the console logs of the runs; the only edit is that a few Ukrainian console messages were translated to English (numbers unchanged).
