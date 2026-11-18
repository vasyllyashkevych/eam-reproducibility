# Experimental results — PAPER021433

All values are read from the regenerated outputs of this repository (no hand-typed numbers). Means over runs; ± is the standard deviation across runs. Section numbers refer to the final manuscript.


## Study A — controlled drift injection (RQ1; Section 7.1, Table 5, Fig. 4)

| variant | accuracy | macro_F1 | false_critical_before_100 | runs |
|---|---|---|---|---|
| A: window detector + PDI | 0.225 ± 0.025 | 0.167 ± 0.021 | 7.125 ± 1.814 | 40 |
| B: reference + maximum | 0.556 ± 0.089 | 0.530 ± 0.084 | 14.525 ± 15.860 | 40 |
| C: reference + PDI | 0.956 ± 0.026 | 0.958 ± 0.025 | 0.025 ± 0.158 | 40 |
| C0: proposed | 0.966 ± 0.024 | 0.968 ± 0.023 | 0.025 ± 0.158 | 40 |
| C0, telemetry only | 0.205 ± 0.046 | 0.121 ± 0.048 | 16.725 ± 7.107 | 40 |
| C0, configuration + structure | 0.745 ± 0.045 | 0.685 ± 0.051 | 21.700 ± 5.801 | 40 |
| C0, telemetry + configuration + structure | 0.738 ± 0.037 | 0.666 ± 0.030 | 23.850 ± 4.324 | 40 |
| C0, planned release, static reference | 0.878 ± 0.028 | 0.861 ± 0.027 | 9.575 ± 1.394 | 40 |
| C0, planned release, versioned reference | 0.968 ± 0.020 | 0.969 ± 0.019 | 0.025 ± 0.158 | 40 |
| C0, missing evidence set to zero | 0.927 ± 0.023 | 0.930 ± 0.022 | 0.050 ± 0.316 | 40 |
| C0, observed-dimension rule (10) | 0.919 ± 0.022 | 0.922 ± 0.021 | 0.050 ± 0.316 | 40 |

* Friedman (macro-F1, four variants, 40 runs): chi2 = 114.5, p = 1.2e-24.

* C0 - A: difference 0.802 [0.792; 0.811], p_Holm = 5.5e-12, A12 = 1.00.

* C0 - B: difference 0.438 [0.410; 0.466], p_Holm = 5.5e-12, A12 = 1.00.

* C0 - C: difference 0.010 [0.006; 0.014], p_Holm = 4.9e-05, A12 = 0.62.

* Versioned vs static reference after the approved release: 0.108 [0.100; 0.115], A12 = 1.00.


## Study A — detection per dimension (Table 6, theta = 0.35)

| dim | P (A) | R (A) | F1 (A) | P (C0) | R (C0) | F1 (C0) | delay (C0) |
|---|---|---|---|---|---|---|---|
| architecture | 0.52 | 0.63 | 0.57 | 1.00 | 0.89 | 0.94 | 6.08 |
| configuration | 0.87 | 0.53 | 0.66 | 1.00 | 1.00 | 1.00 | 0.00 |
| context | 0.30 | 0.54 | 0.38 | 1.00 | 0.09 | 0.16 | 0.00 |
| goal | 0.26 | 0.52 | 0.35 | 1.00 | 0.56 | 0.72 | 6.62 |
| policy | 0.64 | 0.60 | 0.62 | 1.00 | 0.79 | 0.88 | 12.12 |
| role | 0.61 | 0.55 | 0.58 | 1.00 | 0.47 | 0.64 | 10.70 |
| security | 0.18 | 0.53 | 0.27 | 1.00 | 1.00 | 1.00 | 0.00 |
| semantic | 0.33 | 0.70 | 0.45 | 1.00 | 0.58 | 0.74 | 10.80 |
| topology | 0.75 | 0.58 | 0.66 | 1.00 | 0.90 | 0.95 | 7.88 |

* 100 Dirichlet weight vectors: median macro-F1 0.905 (IQR 0.864–0.933; min 0.653); profile weights 0.968.

* Detection threshold 0.50 → 0.20: recall 0.55 → 0.88; precision 1.00 → 1.00.

* Noise/amplitude sigma=0.03,amp=1.0: C0 0.855, C 0.823, B 0.523.

* Noise/amplitude sigma=0.05,amp=1.0: C0 0.659, C 0.591, B 0.427.

* Noise/amplitude sigma=0.05,amp=0.5: C0 0.359, C 0.358, B 0.350.


## Joint ablation of the two drift profiles (RQ1, RQ2; Section 7.4, Table 9)

| variant | macro_F1 | false_critical | coverage | recall_uniform | recall_change_coupled | probe_rebuilds |
|---|---|---|---|---|---|---|
| static/run | 0.861 ± 0.027 | 9.575 ± 1.394 | 0.830 ± 0.017 | 0.855 ± 0.090 | 0.758 ± 0.088 | 44.425 ± 1.430 |
| static/rel | 0.861 ± 0.027 | 9.575 ± 1.394 | 0.407 ± 0.000 | 0.466 ± 0.118 | 0.336 ± 0.079 | 9.000 ± 0.000 |
| static/both | 0.861 ± 0.027 | 9.575 ± 1.394 | 0.833 ± 0.017 | 0.855 ± 0.090 | 0.759 ± 0.087 | 53.425 ± 1.430 |
| versioned/run | 0.969 ± 0.019 | 0.025 ± 0.158 | 0.809 ± 0.024 | 0.812 ± 0.102 | 0.723 ± 0.088 | 45.225 ± 2.675 |
| versioned/rel | 0.969 ± 0.019 | 0.025 ± 0.158 | 0.407 ± 0.000 | 0.466 ± 0.118 | 0.336 ± 0.079 | 9.000 ± 0.000 |
| dual (proposed) | 0.969 ± 0.019 | 0.025 ± 0.158 | 0.915 ± 0.024 | 0.925 ± 0.061 | 0.858 ± 0.064 | 54.225 ± 2.675 |
| full regeneration | 0.969 ± 0.019 | 0.025 ± 0.158 | 0.946 ± 0.017 | 0.955 ± 0.053 | 0.903 ± 0.054 | 355.500 ± 21.856 |
| dual, incomplete PHI | 0.969 ± 0.019 | 0.025 ± 0.158 | 0.832 ± 0.023 | 0.850 ± 0.071 | 0.754 ± 0.079 | 44.200 ± 2.210 |

* Interaction contrast (recall_uniform): 0.113 [0.0900; 0.1365].

* Interaction contrast (coverage): 0.103 [0.1028; 0.1034].

* Interaction contrast (recall_coupled): 0.133 [0.1136; 0.1529].

* dual (proposed) - static/both, coverage: 0.082 [0.073; 0.090], p_Holm = 2.1e-07, A12 = 0.99.

* dual (proposed) - static/both, recall_uniform: 0.070 [0.043; 0.097], p_Holm = 8.1e-06, A12 = 0.75.

* dual (proposed) - full regeneration, coverage: -0.031 [-0.036; -0.026], p_Holm = 2.1e-07, A12 = 0.11.

* dual (proposed) - full regeneration, recall_uniform: -0.030 [-0.040; -0.020], p_Holm = 3.1e-05, A12 = 0.35.

* dual (proposed) - dual, incomplete PHI, coverage: 0.083 [0.082; 0.084], p_Holm = 2.1e-07, A12 = 0.99.

* dual (proposed) - dual, incomplete PHI, recall_uniform: 0.075 [0.060; 0.091], p_Holm = 4.0e-07, A12 = 0.80.

* Friedman (uniform-defect recall, 8 variants): chi2 = 236.7, p = 1.9e-47.

* Probe rebuilds, full regeneration / dual profile: 6.6× (counts, not execution time).

* Masking scenario, dual, mask only: shift flagged in 0/40 runs; goal recall after window 0.00; mean delay 72.00 steps.

* Masking scenario, dual + CriticalCheck: shift flagged in 40/40 runs; goal recall after window 1.00; mean delay 0.03 steps.


## Study B — corpus and drift profile (Section 6.2, 7.2, Fig. 5)

* Units: 1802 (production database 1060); Oracle objects 2678, PostgreSQL objects 2910.

* Units deployed on the PostgreSQL 17.11 testbed without error: 795; routines run with instrumentation: 290.

* Object-property observation slots: 19595; units with drift above the threshold in at least one dimension: 1511.

| dimension | share_pos | mean | share_sig |
|---|---|---|---|
| configuration | 0.497 | 0.458 | 0.497 |
| topological | 0.351 | 0.177 | 0.333 |
| role | 0.024 | 0.022 | 0.024 |
| policy | 0.491 | 0.489 | 0.491 |
| architectural | 0.351 | 0.341 | 0.349 |
| semantic | 0.558 | 0.347 | 0.542 |
| security | 0.536 | 0.502 | 0.530 |
| contextual | 0.603 | 0.491 | 0.603 |
| goal | 0.534 | 0.141 | 0.362 |

* Spearman correlation policy–security drift: 0.94.


## Study B — corpus experiment after migration (Table 7, deterministic re-run, 40 runs)

| variant | PCRw | MRSR | P | R | F1 | F1_sd | MTTD | LA | FAR | slots_optimized | t_adapt_s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S0 | 0.317 | 0.000 | 0.866 | 0.235 | 0.369 | 0.022 | 14.623 | 0.000 | 0.134 | 0.000 | 0.000 |
| S1 | 0.389 | 0.269 | 0.661 | 0.377 | 0.479 | 0.022 | 4.363 | 0.239 | 0.339 | 0.000 | 0.002 |
| S2 | 0.681 | 0.711 | 0.802 | 0.741 | 0.770 | 0.022 | 6.770 | 0.639 | 0.198 | 17892.000 | 5.599 |
| S3 | 0.674 | 0.710 | 0.799 | 0.736 | 0.766 | 0.021 | 6.458 | 0.633 | 0.201 | 16449.400 | 5.185 |
| S3-O | 0.602 | 0.522 | 0.715 | 0.522 | 0.603 | 0.025 | 5.490 | 0.419 | 0.285 | 10730.400 | 3.386 |

* Friedman (F1, five variants): chi2 = 153.6, p = 3.4e-32.

* Wilcoxon, S3 vs other variants, Holm-adjusted p: S0 7.3e-12, S1 7.3e-12, S2 9.1e-03, S3-O 7.3e-12.

* TOST S3 vs S2 (margin ±0.02 F1): p = 1.8e-11 (equivalent).

* Ten-variant re-run, F1: A-AM 0.458, A-RB 0.480, A-RV 0.537, A-RX 0.428, S0 0.369, S1 0.479, S2 0.770, S3 0.766, S3-9D 0.765, S3-O 0.603.

* S3 − A-RV (corpus experiment): 0.229 [0.218; 0.240].

* `t_adapt_s` is wall-clock time on the verification machine and changes between machines.


## Study B — PostgreSQL 17 testbed with measured telemetry (Table 8, 10 runs)

| variant | object_probes | P | R | F1 | F1_sd | MTTD | LA | overhead_ms_step | workload_ms_step |
|---|---|---|---|---|---|---|---|---|---|
| A-AM | 2378.300 | 0.722 | 0.236 | 0.353 | 0.035 | 8.293 | 0.183 | 22.544 | 536.204 |
| A-RB | 3603.600 | 0.570 | 0.264 | 0.358 | 0.026 | 8.175 | 0.206 | 24.064 | 536.204 |
| A-RV | 6251.500 | 0.652 | 0.387 | 0.485 | 0.039 | 5.070 | 0.322 | 25.913 | 536.204 |
| A-RX | 3945.700 | 0.530 | 0.271 | 0.355 | 0.027 | 7.803 | 0.212 | 22.544 | 536.204 |
| S0 | 0.000 | 1.000 | 0.051 | 0.097 | 0.011 | 31.720 | 0.000 | 17.265 | 536.204 |
| S1 | 2378.300 | 0.611 | 0.245 | 0.347 | 0.027 | 8.562 | 0.193 | 22.544 | 536.204 |
| S2 | 8396.900 | 0.642 | 0.470 | 0.540 | 0.037 | 1.117 | 0.450 | 2061.373 | 536.204 |
| S3 | 8333.100 | 0.619 | 0.452 | 0.519 | 0.032 | 1.150 | 0.434 | 2055.832 | 536.204 |
| S3-9D | 8349.100 | 0.622 | 0.452 | 0.520 | 0.031 | 1.152 | 0.433 | 2058.508 | 536.204 |
| S3-O | 7876.900 | 0.467 | 0.269 | 0.340 | 0.038 | 3.330 | 0.259 | 25.913 | 536.204 |

* S3 − S0: 0.422 [0.396; 0.449] (paired t interval).

* S3 − A-RV: 0.035 [0.022; 0.047] (paired t interval).

* S2 − S3: 0.021 [0.012; 0.030] (paired t interval).

* Holm-adjusted Wilcoxon p, S3 vs S2: 0.018.

* Rank agreement corpus experiment vs testbed (F1, 10 variants): Spearman rho = 0.76, p = 0.011.

* Share of S3 detections (robust EWMA detector) produced by catalogue, privilege and audit signals: 0.73.


## Study B — limits of unit-level failure prediction (Section 7.5, Table 10)

| indicator | auc | auc_lo | auc_hi | flagged | f1 |
|---|---|---|---|---|---|
| d_configuration | 0.583 | 0.526 | 0.638 | 0.869 | 0.419 |
| d_topological | 0.540 | 0.483 | 0.599 | 0.552 | 0.375 |
| d_role | 0.500 | 0.500 | 0.500 | 0.000 | 0.000 |
| d_policy | 0.511 | 0.474 | 0.549 | 0.844 | 0.387 |
| d_architectural | 0.555 | 0.503 | 0.607 | 0.256 | 0.335 |
| d_contextual | 0.563 | 0.499 | 0.623 | 0.862 | 0.401 |
| d_semantic | 0.612 | 0.556 | 0.667 | 0.966 | 0.400 |
| d_goal | 0.580 | 0.515 | 0.644 | 0.762 | 0.404 |
| d_security | 0.516 | 0.480 | 0.554 | 0.928 | 0.394 |
| EDI | 0.639 | 0.578 | 0.702 | 1.000 | 0.393 |
| size_loc | 0.588 | 0.521 | 0.655 | 1.000 | 0.393 |

* Units with execution evidence: 442; failing because of migrated code: 108.

* Rank of the expected dimension per failure class: 3.36 vs 4.01 by chance; first in 3 of 9 classes.


## Study C — security drift of five libraries (RQ3; Section 7.3, Fig. 6)

* Snapshots 250; consecutive transitions 245; advisory-based exposure changes 5 (3 increases, 2 decreases).

* Code-based detectors on these events: recall static 0.00, EWMA 0.00; alarm rate on the other 240 transitions: static 0.113, EWMA 0.108.

* Increases with IDI < 0.05: 2 of 3; Spearman IDI vs exposure rho = -0.118, p = 0.065, n = 245.

* Releases 454; linked later to an advisory: 374.

| horizon | evaluable | share_exposed | share_ge_0_7 | mean_index |
|---|---|---|---|---|
| 365 days | 421.000 | 0.216 | 0.162 | 0.164 |
| 730 days | 411.000 | 0.311 | 0.214 | 0.241 |
| 1825 days | 351.000 | 0.564 | 0.328 | 0.400 |

* Share exposed after two years by library: attrs 0.000, gunicorn 0.043, pyyaml 0.370, tqdm 0.362, urllib3 0.573.

* Newest-release track: 28 of 31 advisories had no exposure window; longest 259 days (pyyaml, CVE-2017-18342).

