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

<!-- STUDY_A_LOFO_START -->
### Supplementary analysis: Study A — leave-one-drift-dimension-out (LOFO)

The supplementary ablation in `code/study_a_lofo.py` tests the contribution of each of the nine drift dimensions to **evolution-state classification macro-F1** under the controlled Study A scenario. It does **not** re-estimate Study B monitoring coverage (PCRw), MRSR, or runtime defect recall, and does not change any previously reported result.

Install the project's Python dependencies (`numpy`, `pandas`, `scipy`, `matplotlib`) and run from the repository root:

```bash
python code/study_a_lofo.py --code-dir code --output-dir results/study_a_lofo
```

Each dimension is masked in turn, the EDI weights are renormalized over the remaining dimensions, that dimension is excluded from `CriticalCheck`, and the five-state classifier thresholds are recalibrated using training seeds **101–110**. The method is evaluated using **40 paired seeds (1–40)**. The output includes mean macro-F1 differences and 95% paired bootstrap intervals (15,000 resamples, deterministic seeds), two figures, and per-run results. The all-dimensions control should reproduce Study A C0 macro-F1 close to **0.9683**.

- `results/study_a_lofo/StudyA_leave_one_dimension_out.csv` — summary by dimension.
- `results/study_a_lofo/StudyA_LOFO_paired_runs.csv` — paired 40-seed results.
- `figures/study_a_lofo/Fig_LOFO_Radar_StudyA.{png,svg}` — nine-axis radar profile.
- `figures/study_a_lofo/Fig_LOFO_Bars_StudyA.{png,svg}` — paired effect and confidence interval comparison.
- `docs/STUDY_A_LOFO.md` — protocol, interpretation, and limitations.

This is a **supplementary sensitivity/ablation analysis**. The measured loss after exclusion depends on the Study A scenario, dimensions, threshold recalibration, and critical-override rule; it is not a causal attribution and is not a general ranking across domains.
<!-- STUDY_A_LOFO_END -->
