# PAPER021433 — Supplementary Study A LOFO protocol

## Purpose

Estimate how much the nine drift indicators contribute to **five-class evolution-state classification** under the existing synthetic Study A benchmark. This is an additional analysis; it does not overwrite or revise the submitted manuscript's numerical results.

## Code and inputs

`code/study_a_lofo.py` imports the existing `controlled_drift.py` and `multidrift_eval.py`. The same injection plan, model weights, temporal `risk()` processing, critical override and labels are reused. The evaluator uses the ten Study A training seeds 101–110 and 40 evaluation seeds 1–40.

## One-dimension-out comparison

1. Generate the nine reference-indicator time series for each training and test seed.
2. Calculate the **all-nine-dimensions** C0 baseline, including EDI, `risk()` and the critical override.
3. For each dimension, replace only that dimension's reference-indicator series with `NaN` (not zero). This removes it from the weighted EDI and makes the original `CriticalCheck` exclude it.
4. Recalibrate the four ordered state thresholds on training seeds only, with all other parameters unchanged.
5. Compute per-seed five-state macro-F1 on the same 40 test runs, then report the paired mean loss:

   `LOFO_drop(d) = mean_seed[F1(all) - F1(without d)]`

6. Draw 15,000 paired bootstrap resamples of the 40 per-seed differences (fixed RNG seed `31000 + dimension index`) for the percentile 95% interval.
7. As a robustness diagnostic, also report the F1 without each dimension **using the original full-model thresholds**, clearly distinguished from the recalibrated primary comparison.

## Expected primary result

The original C0 control reaches macro-F1 approximately **0.9683**. The three largest primary declines are configuration (~0.1150), security (~0.0705), and architecture (~0.0583). The topology and semantic intervals include zero; the results therefore do **not** establish that those dimensions are unimportant in other settings.

## Files

- `results/study_a_lofo/StudyA_leave_one_dimension_out.csv`: one row per dimension; all primary and fixed-threshold diagnostics.
- `results/study_a_lofo/StudyA_LOFO_paired_runs.csv`: 9 × 40 rows of paired observations, with baseline, ablated macro-F1 and paired difference.
- `figures/study_a_lofo/Fig_LOFO_Radar_StudyA.png|svg`: radar diagram of the macro-F1 drop, in percentage points.
- `figures/study_a_lofo/Fig_LOFO_Bars_StudyA.png|svg`: horizontal bar chart with 95% paired bootstrap CIs.

## Running

```bash
python code/study_a_lofo.py --code-dir code --output-dir results/study_a_lofo
```

Python with NumPy, pandas, SciPy and Matplotlib is required. The program reads no private migration corpus or testbed records.

## Scope / limitations

The difference reflects both removal from EDI and removal from the critical override, where applicable. The primary estimates **recalibrate thresholds**, so they measure predictive contribution after adaptation of the remaining model. The fixed-threshold columns reveal an alternative operational effect. Do not interpret this sensitivity experiment as identifying causes, or as measuring PCRw, MRSR, probe rebuild count, or Study B fault-detection F1. These results should be labeled **supplementary Study A ablation** until separately integrated into the manuscript.
