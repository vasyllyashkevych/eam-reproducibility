# Reproduction summary

Checks: 145; PASS: 145; FAIL: 0

| id | manuscript location | expected | obtained | |diff| | tolerance | status | source |
|---|---|---|---|---|---|---|---|
| A.C0.macro_f1 | Abstract; Table 5; Sec. 7.1 | 0.968 | 0.968309 | 0.000309 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.LOFO.C0_macro_f1 | Sec. 7.1 (LOFO ablation) | 0.9683 | 0.968309 | 9e-06 | 5.0001000000000005e-05 | PASS | docs/results/study_a_lofo/StudyA_leave_one_dimension_out.csv |
| A.LOFO.configuration_drop | Sec. 7.1 (LOFO ablation), percentage points | 11.5 | 11.502995 | 0.002995 | 0.0050000010000000004 | PASS | docs/results/study_a_lofo/StudyA_leave_one_dimension_out.csv |
| A.LOFO.configuration_ci_low | Sec. 7.1 (LOFO ablation), 95% CI, percentage points | 10.09 | 10.087809 | 0.002191 | 0.0050000010000000004 | PASS | docs/results/study_a_lofo/StudyA_leave_one_dimension_out.csv |
| A.LOFO.configuration_ci_high | Sec. 7.1 (LOFO ablation), 95% CI, percentage points | 12.88 | 12.879183 | 0.000817 | 0.0050000010000000004 | PASS | docs/results/study_a_lofo/StudyA_leave_one_dimension_out.csv |
| A.LOFO.security_drop | Sec. 7.1 (LOFO ablation), percentage points | 7.05 | 7.054752 | 0.004752 | 0.0050000010000000004 | PASS | docs/results/study_a_lofo/StudyA_leave_one_dimension_out.csv |
| A.LOFO.architecture_drop | Sec. 7.1 (LOFO ablation), percentage points | 5.83 | 5.831926 | 0.001926 | 0.0050000010000000004 | PASS | docs/results/study_a_lofo/StudyA_leave_one_dimension_out.csv |
| A.LOFO.context_drop | Sec. 7.1 (LOFO ablation), percentage points | 4.16 | 4.164669 | 0.004669 | 0.0050000010000000004 | PASS | docs/results/study_a_lofo/StudyA_leave_one_dimension_out.csv |
| A.LOFO.semantic_drop | Sec. 7.1 (LOFO ablation), percentage points | 0.04 | 0.035937 | 0.004063 | 0.0050000010000000004 | PASS | docs/results/study_a_lofo/StudyA_leave_one_dimension_out.csv |
| A.LOFO.topology_drop | Sec. 7.1 (LOFO ablation), percentage points | 0.65 | 0.652802 | 0.002802 | 0.0050000010000000004 | PASS | docs/results/study_a_lofo/StudyA_leave_one_dimension_out.csv |
| A.C0.accuracy | Table 5 | 0.966 | 0.966458 | 0.000458 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.C.macro_f1 | Table 5 | 0.958 | 0.95815 | 0.00015 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.B.macro_f1 | Abstract; Table 5 | 0.53 | 0.53003 | 3e-05 | 0.005000001 | PASS | docs/results/controlled_runs.csv |
| A.A.macro_f1 | Table 5; Sec. 7.1 | 0.167 | 0.166759 | 0.000241 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.B.false_critical | Table 5; Sec. 7.1 | 14.5 | 14.525 | 0.025 | 0.050000001 | PASS | docs/results/controlled_runs.csv |
| A.C0.false_critical | Table 5 | 0.03 | 0.025 | 0.005 | 0.005000001 | PASS | docs/results/controlled_runs.csv |
| A.telemetry_only.macro_f1 | Table 5; Sec. 7.1 | 0.121 | 0.120677 | 0.000323 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.config_structure.macro_f1 | Table 5 | 0.685 | 0.685348 | 0.000348 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.tel_config_structure.macro_f1 | Table 5 | 0.666 | 0.666088 | 8.8e-05 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.release_static.macro_f1 | Table 5; Table 9 | 0.861 | 0.861062 | 6.2e-05 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.release_versioned.macro_f1 | Table 5; Table 9 | 0.969 | 0.96906 | 6e-05 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.release_static.false_critical | Table 5; Sec. 7.1 | 9.6 | 9.575 | 0.025 | 0.050000001 | PASS | docs/results/controlled_runs.csv |
| A.evidence_gap_renormalised.macro_f1 | Sec. 7.1 | 0.922 | 0.922177 | 0.000177 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.evidence_gap_zero_filled.macro_f1 | Sec. 7.1 | 0.93 | 0.929771 | 0.000229 | 0.005000001 | PASS | docs/results/controlled_runs.csv |
| A.noise0.03.C0 | Sec. 7.1 | 0.855 | 0.854731 | 0.000269 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.noise0.05.C0 | Sec. 7.1 | 0.659 | 0.659148 | 0.000148 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.noise0.05.half.C0 | Sec. 7.1 | 0.359 | 0.358712 | 0.000288 | 0.000500001 | PASS | docs/results/controlled_runs.csv |
| A.friedman_chi2 | Sec. 7.1 | 114.5 | 114.544757 | 0.044757 | 0.050000001 | PASS | docs/results/controlled_tests.csv |
| A.C0_minus_C.diff | Sec. 7.1 | 0.01 | 0.010159 | 0.000159 | 0.005000001 | PASS | docs/results/controlled_tests.csv |
| A.C0_minus_C.ci_low | Sec. 7.1 | 0.006 | 0.006169 | 0.000169 | 0.000500001 | PASS | docs/results/controlled_tests.csv |
| A.C0_minus_C.ci_high | Sec. 7.1 | 0.014 | 0.014143 | 0.000143 | 0.000500001 | PASS | docs/results/controlled_tests.csv |
| A.release_diff | Sec. 7.1 | 0.108 | 0.107998 | 2e-06 | 0.000500001 | PASS | docs/results/controlled_tests.csv |
| A.weights.median | Sec. 7.1 | 0.905 | 0.9049 | 0.0001 | 0.000500001 | PASS | docs/results/controlled_weight_sensitivity.csv |
| A.weights.q25 | Sec. 7.1 | 0.864 | 0.863797 | 0.000203 | 0.000500001 | PASS | docs/results/controlled_weight_sensitivity.csv |
| A.weights.q75 | Sec. 7.1 | 0.933 | 0.932673 | 0.000327 | 0.000500001 | PASS | docs/results/controlled_weight_sensitivity.csv |
| A.weights.min | Sec. 7.1 | 0.653 | 0.653225 | 0.000225 | 0.000500001 | PASS | docs/results/controlled_weight_sensitivity.csv |
| A.theta0.50.recall | Sec. 7.1 | 0.55 | 0.548207 | 0.001793 | 0.005000001 | PASS | docs/results/controlled_theta_sensitivity.csv |
| A.theta0.20.recall | Sec. 7.1 | 0.88 | 0.88257 | 0.00257 | 0.005000001 | PASS | docs/results/controlled_theta_sensitivity.csv |
| A.context.recall_C0 | Table 6; Sec. 7.1 | 0.09 | 0.088235 | 0.001765 | 0.005000001 | PASS | docs/results/controlled_prf_by_dim.csv |
| J.dual.coverage | Table 9 | 0.915 | 0.914769 | 0.000231 | 0.000500001 | PASS | docs/results/dual_profile_runs.csv |
| J.dual.recall_uniform | Table 9; Sec. 9 | 0.925 | 0.92517 | 0.00017 | 0.000500001 | PASS | docs/results/dual_profile_runs.csv |
| J.dual.recall_coupled | Table 9 | 0.858 | 0.857534 | 0.000466 | 0.000500001 | PASS | docs/results/dual_profile_runs.csv |
| J.dual.rebuilds | Table 9; Sec. 7.4 | 54.2 | 54.225 | 0.025 | 0.050000001 | PASS | docs/results/dual_profile_runs.csv |
| J.full.rebuilds | Table 9; Sec. 7.4 | 355.5 | 355.5 | 0.0 | 0.050000001 | PASS | docs/results/dual_profile_runs.csv |
| J.rebuild_ratio | Sec. 7.4 | 6.6 | 6.556017 | 0.043983 | 0.050000001 | PASS | docs/results/dual_profile_runs.csv |
| J.versioned_run.recall_uniform | Table 9; Sec. 7.4 | 0.812 | 0.812352 | 0.000352 | 0.000500001 | PASS | docs/results/dual_profile_runs.csv |
| J.rel_only.coverage | Table 9; Sec. 7.4 | 0.407 | 0.407041 | 4.1e-05 | 0.000500001 | PASS | docs/results/dual_profile_runs.csv |
| J.rel_only.recall_uniform | Table 9; Sec. 7.4 | 0.466 | 0.466241 | 0.000241 | 0.000500001 | PASS | docs/results/dual_profile_runs.csv |
| J.static.false_critical | Table 9 | 9.6 | 9.575 | 0.025 | 0.050000001 | PASS | docs/results/dual_profile_runs.csv |
| J.versioned.false_critical | Table 9 | 0.03 | 0.025 | 0.005 | 0.005000001 | PASS | docs/results/dual_profile_runs.csv |
| J.interaction.recall_uniform | Sec. 7.4 | 0.113 | 0.112818 | 0.000182 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| J.interaction.recall_uniform.ci_low | Sec. 7.4 | 0.09 | 0.090003 | 3e-06 | 0.005000001 | PASS | docs/results/dual_profile_tests.csv |
| J.interaction.recall_uniform.ci_high | Sec. 7.4 (corrected from 0.137 in the previous draft) | 0.136 | 0.136464 | 0.000464 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| J.interaction.coverage | Sec. 7.4 | 0.103 | 0.103128 | 0.000128 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| J.interaction.recall_coupled | Sec. 7.4 | 0.133 | 0.13332 | 0.00032 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| J.friedman_recall_uniform | Sec. 7.4 | 236.7 | 236.714922 | 0.014922 | 0.050000001 | PASS | docs/results/dual_profile_tests.csv |
| J.mask_only.flagged | Sec. 7.4 | 0 | 0.0 | 0.0 | 0 | PASS | docs/results/dual_profile_shock_runs.csv |
| J.criticalcheck.flagged | Sec. 7.4 | 40 | 40.0 | 0.0 | 0 | PASS | docs/results/dual_profile_shock_runs.csv |
| C.snapshots | Sec. 6.3 | 250 | 250.0 | 0.0 | 0 | PASS | docs/results/security_drift_snapshots.csv |
| C.transitions | Sec. 6.3; 7.3 | 245 | 245.0 | 0.0 | 0 | PASS | docs/results/security_drift_summary.json |
| C.increases | Sec. 7.3 | 3 | 3.0 | 0.0 | 0 | PASS | docs/results/security_drift_summary.json |
| C.decreases | Sec. 7.3 | 2 | 2.0 | 0.0 | 0 | PASS | docs/results/security_drift_summary.json |
| C.other_transitions | Sec. 7.3 | 240 | 240.0 | 0.0 | 0 | PASS | docs/results/security_drift_summary.json |
| C.code_recall | Sec. 7.3 | 0.0 | 0.0 | 0.0 | 0 | PASS | docs/results/security_drift_summary.json |
| C.increases_low_idi | Sec. 7.3 | 2 | 2.0 | 0.0 | 0 | PASS | docs/results/security_drift_summary.json |
| C.pinned_releases | Sec. 6.3; 7.3 | 454 | 454.0 | 0.0 | 0 | PASS | docs/results/security_drift_summary.json |
| C.pinned_with_advisory | Sec. 7.3 | 374 | 374.0 | 0.0 | 0 | PASS | docs/results/security_drift_summary.json |
| C.static_rate | Sec. 7.3 | 0.113 | 0.113 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.ewma_rate | Sec. 7.3 | 0.108 | 0.108 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.spearman_rho | Sec. 7.3 | -0.118 | -0.118 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.spearman_p | Sec. 7.3 | 0.065 | 0.064612 | 0.000388 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.pinned_1y_exposed | Sec. 7.3 | 0.216 | 0.216 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.pinned_1y_ge07 | Sec. 7.3 | 0.162 | 0.162 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.pinned_2y_exposed | Abstract-level; Sec. 7.3; Sec. 9 | 0.311 | 0.311 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.pinned_2y_ge07 | Sec. 7.3 | 0.214 | 0.214 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.pinned_5y_exposed | Sec. 7.3 | 0.564 | 0.564 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.pinned_5y_ge07 | Sec. 7.3 | 0.328 | 0.328 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.urllib3_2y | Sec. 7.3 | 0.573 | 0.573 | 0.0 | 0.000500001 | PASS | docs/results/security_drift_summary.json |
| C.attrs_2y | Sec. 7.3 | 0.0 | 0.0 | 0.0 | 0.050000001 | PASS | docs/results/security_drift_summary.json |
| C.advisories_on_release_track | Sec. 7.3 | 31 | 31.0 | 0.0 | 0 | PASS | docs/results/security_exposure_windows.csv |
| C.zero_window | Sec. 7.3 | 28 | 28.0 | 0.0 | 0 | PASS | docs/results/security_exposure_windows.csv |
| C.longest_window_days | Sec. 7.3 | 259 | 259.0 | 0.0 | 0 | PASS | docs/results/security_exposure_windows.csv |
| B.sim.S0.F1 | Abstract; Table 7 | 0.369 | 0.369084 | 8.4e-05 | 0.000500001 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.S1.F1 | Table 7 | 0.479 | 0.479427 | 0.000427 | 0.000500001 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.S2.F1 | Abstract; Table 7 | 0.77 | 0.770398 | 0.000398 | 0.005000001 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.S3.F1 | Abstract; Table 7 | 0.766 | 0.765878 | 0.000122 | 0.000500001 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.S3-O.F1 | Table 7 | 0.603 | 0.603308 | 0.000308 | 0.000500001 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.S3.PCRw | Table 7 | 0.674 | 0.673886 | 0.000114 | 0.000500001 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.S2.PCRw | Table 7 | 0.681 | 0.681452 | 0.000452 | 0.000500001 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.S1.MRSR | Table 7 | 0.269 | 0.269101 | 0.000101 | 0.000500001 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.S3.slots | Sec. 7.2 | 16449 | 16449.4 | 0.4 | 0.5 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.S2.slots | Sec. 7.2 | 17892 | 17892.0 | 0.0 | 0.5 | PASS | docs/results/study_b_table7.csv (from data/study_b_public/e2e_runs.csv) |
| B.sim.friedman_chi2 | Sec. 7.2 | 153.6 | 153.637046 | 0.037046 | 0.050000001 | PASS | docs/results/study_b_statistics.json |
| B.sim.tost_p | Sec. 7.2 (p < 0.001) | 0.001 | 0.0 | 0.001 | 0.001 | PASS | docs/results/study_b_statistics.json |
| B.sim_ext.A-RX.F1 | Sec. 7.2 | 0.428 | 0.428408 | 0.000408 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.sim_ext.A-RV.F1 | Sec. 7.2 | 0.537 | 0.536917 | 8.3e-05 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.sim_ext.S3-9D.F1 | Sec. 7.2 | 0.765 | 0.764614 | 0.000386 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.sim_ext.S3.F1 | Sec. 7.2 | 0.766 | 0.765878 | 0.000122 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.sim_ext.S3_minus_ARV | Sec. 7.2 | 0.229 | 0.228961 | 3.9e-05 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.testbed.S0.F1 | Abstract; Table 8 | 0.097 | 0.096738 | 0.000262 | 0.000500001 | PASS | docs/results/study_b_table8.csv (from data/study_b_public/ops_runs_method.csv) |
| B.testbed.S3.F1 | Abstract; Table 8 | 0.519 | 0.519089 | 8.9e-05 | 0.000500001 | PASS | docs/results/study_b_table8.csv (from data/study_b_public/ops_runs_method.csv) |
| B.testbed.S2.F1 | Abstract; Table 8 | 0.54 | 0.540194 | 0.000194 | 0.000500001 | PASS | docs/results/study_b_table8.csv (from data/study_b_public/ops_runs_method.csv) |
| B.testbed.A-RV.F1 | Table 8 | 0.485 | 0.484563 | 0.000437 | 0.000500001 | PASS | docs/results/study_b_table8.csv (from data/study_b_public/ops_runs_method.csv) |
| B.testbed.S3.overhead_ms | Sec. 7.2 | 2056 | 2055.83235 | 0.16765 | 0.5 | PASS | docs/results/study_b_table8.csv (from data/study_b_public/ops_runs_method.csv) |
| B.testbed.workload_ms | Sec. 7.2 | 536 | 536.203847 | 0.203847 | 0.5 | PASS | docs/results/study_b_table8.csv (from data/study_b_public/ops_runs_method.csv) |
| B.testbed.S3_minus_S0 | Sec. 7.2 | 0.422 | 0.42235 | 0.00035 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.testbed.S3_minus_S0.ci_low | Sec. 7.2 | 0.396 | 0.396092 | 9.2e-05 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.testbed.S3_minus_S0.ci_high | Sec. 7.2 | 0.449 | 0.448608 | 0.000392 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.testbed.S3_minus_ARV | Sec. 7.2 | 0.035 | 0.034526 | 0.000474 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.testbed.S2_minus_S3 | Sec. 7.2 | 0.021 | 0.021106 | 0.000106 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.testbed.S2_vs_S3.p_holm | Sec. 7.2 | 0.018 | 0.017578 | 0.000422 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
| B.sim_vs_testbed_spearman | Sec. 7.2 | 0.76 | 0.757576 | 0.002424 | 0.005000001 | PASS | docs/results/study_b_statistics.json |
| B.drift.context_share | Sec. 7.2 (60.3%) | 0.603 | 0.603219 | 0.000219 | 0.0005 | PASS | data/study_b_public/e2e_drift9_summary.csv |
| B.drift.role_share | Sec. 7.2 (2.4%) | 0.024 | 0.024417 | 0.000417 | 0.0005 | PASS | data/study_b_public/e2e_drift9_summary.csv |
| B.failure.EDI_auc | Abstract; Table 10 | 0.639 | 0.639041 | 4.1e-05 | 0.000500001 | PASS | data/study_b_public/boundary_failure_prediction.csv (precomputed from the Study B unit table) |
| B.failure.size_auc | Table 10 | 0.588 | 0.588199 | 0.000199 | 0.000500001 | PASS | data/study_b_public/boundary_failure_prediction.csv (precomputed from the Study B unit table) |
| dtest:coverage|dual (proposed) - static/both|diff | Sec. 7.4 | 0.082 | 0.081889 | 0.000111 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:coverage|dual (proposed) - static/both|ci_low | Sec. 7.4 | 0.073 | 0.072537 | 0.000463 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:coverage|dual (proposed) - static/both|ci_high | Sec. 7.4 | 0.09 | 0.089879 | 0.000121 | 0.005000001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - static/both|diff | Sec. 7.4 | 0.07 | 0.069935 | 6.5e-05 | 0.005000001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - static/both|ci_low | Sec. 7.4 | 0.043 | 0.043149 | 0.000149 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - static/both|ci_high | Sec. 7.4 | 0.097 | 0.096607 | 0.000393 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - static/both|a12 | Sec. 7.4 | 0.75 | 0.7475 | 0.0025 | 0.005000001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - full regeneration|diff | Sec. 7.4 | -0.03 | -0.029705 | 0.000295 | 0.005000001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - full regeneration|ci_low | Sec. 7.4 | -0.04 | -0.039984 | 1.6e-05 | 0.005000001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - full regeneration|ci_high | Sec. 7.4 | -0.02 | -0.019853 | 0.000147 | 0.005000001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - dual, incomplete PHI|diff | Sec. 7.4 | 0.075 | 0.074838 | 0.000162 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - dual, incomplete PHI|ci_low | Sec. 7.4 | 0.06 | 0.059726 | 0.000274 | 0.005000001 | PASS | docs/results/dual_profile_tests.csv |
| dtest:recall_uniform|dual (proposed) - dual, incomplete PHI|ci_high | Sec. 7.4 | 0.091 | 0.090507 | 0.000493 | 0.000500001 | PASS | docs/results/dual_profile_tests.csv |
| B.units | Abstract; Sec. 6.2 | 1802 | 1802.0 | 0.0 | 0 | PASS | data/study_b_public/study_b_counts.json |
| B.units_production | Sec. 6.2 | 1060 | 1060.0 | 0.0 | 0 | PASS | data/study_b_public/study_b_counts.json |
| B.units_deployed | Sec. 6.2 | 795 | 795.0 | 0.0 | 0 | PASS | data/study_b_public/study_b_counts.json |
| B.routines_instrumented | Sec. 6.2 | 290 | 290.0 | 0.0 | 0 | PASS | data/study_b_public/study_b_counts.json |
| B.objects_oracle | Sec. 6.2 | 2678 | 2678.0 | 0.0 | 0 | PASS | data/study_b_public/e2e_structure_stats.json |
| B.objects_pg | Sec. 6.2 | 2910 | 2910.0 | 0.0 | 0 | PASS | data/study_b_public/e2e_structure_stats.json |
| B.observation_slots | Sec. 6.2 | 19595 | 19595.0 | 0.0 | 0 | PASS | data/study_b_public/e2e_model_info.json |
| B.units_with_drift | Sec. 7.2 | 1511 | 1511.0 | 0.0 | 0 | PASS | data/study_b_public/e2e_model_info.json |
| B.context_assumptions | Sec. 6.2; Table 2 | 15 | 15.0 | 0.0 | 0 | PASS | data/study_b_public/e2e_ctx_checks.csv |
| B.failure.units | Sec. 7.5; Table 10 | 442 | 442.0 | 0.0 | 0 | PASS | data/study_b_public/boundary_summary.json |
| B.failure.failing | Sec. 7.5; Table 10 | 108 | 108.0 | 0.0 | 0 | PASS | data/study_b_public/boundary_summary.json |
| B.failure.top1 | Sec. 7.5 | 3 | 3.0 | 0.0 | 0 | PASS | data/study_b_public/boundary_summary.json |
| B.rho_policy_security | Sec. 4.4 | 0.94 | 0.940057 | 5.7e-05 | 0.0050000010000000004 | PASS | data/study_b_public/e2e_drift9_corr.csv |
| B.failure.rank | Sec. 7.5 | 3.36 | 3.358696 | 0.001304 | 0.0050000010000000004 | PASS | data/study_b_public/boundary_summary.json |
| B.failure.chance_rank | Sec. 7.5 | 4.01 | 4.006157 | 0.003843 | 0.0050000010000000004 | PASS | data/study_b_public/boundary_summary.json |
| B.sim.S2_vs_S3.p_holm | Sec. 7.2 | 0.009 | 0.009065 | 6.5e-05 | 0.000500001 | PASS | docs/results/study_b_statistics.json |
