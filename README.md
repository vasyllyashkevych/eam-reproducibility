# eam-reproducibility

Code, data and expected outputs for the IJITCS manuscript **PAPER021433**
*“Evolution-Aware Monitoring for Evolving Information Systems: Multidimensional Drift Assessment with a Version-Dependent Reference Model”* (V. Lyashkevych).

Repository: https://github.com/vasyllyashkevych/eam-reproducibility

| Study | What it checks | How to reproduce | Database needed |
|---|---|---|---|
| A — controlled drift injection (RQ1) | evolution-state classification, Tables 5–6, Fig. 4 | `bash run_all.sh` | no |
| Joint ablation (RQ1, RQ2) | release-change vs runtime profile, Table 9 | `bash run_all.sh` | no |
| C — security drift of five libraries (RQ3) | advisory-based exposure, Fig. 6 | `bash run_all.sh` (frozen OSV cache) | no |
| B — Oracle → PostgreSQL migration (RQ2) | probe selection after evolution, Tables 7, 8, 10, Fig. 5 | `bash study_b/run_study_b_offline.sh` (levels 1–2) | no |
| B — testbed re-measurement | re-deploys 1,802 units and re-collects telemetry | `bash study_b/run_study_b_testbed.sh` (level 3) | PostgreSQL 17 |

Quick start (macOS/Linux, Python 3.14):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash run_all.sh                         # Studies A, C, ablation, figures, 136 number checks, tests
bash study_b/run_study_b_offline.sh     # Study B from the migration corpus
```

Details: `README_REPRODUCE.md` (Studies A, C, ablation, number checks) and `study_b/README_STUDY_B.md` (Study B).
Every number printed in the paper is listed in `RESULTS_TRACEABILITY.csv`; `code/check_expected.py` recomputes them from the regenerated outputs.
