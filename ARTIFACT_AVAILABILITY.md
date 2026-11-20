# Artifact availability

All artifacts needed to reproduce the paper are included. Nothing is withheld.

| Artifact | Location | Status |
|---|---|---|
| Study A generator, variants, statistics; plan and seeds | `code/multidrift_eval.py`, `code/controlled_drift.py`, `data/study_a/` | Public |
| Joint ablation | `code/dual_profile.py` | Public |
| Supplementary leave-one-dimension-out analysis of Study A | `code/study_a_lofo.py`, `docs/STUDY_A_LOFO.md`, `docs/results/study_a_lofo/`, `docs/figures/fig5a_*`, `docs/figures/fig5b_*` | Public |
| Study C script (offline) and inputs, OSV cache (5 Nov 2026) | `code/security_cvss.py`, `data/study_c/` | Public (OSV data CC-BY 4.0) |
| Study B migration corpus, 1,802 Oracle → PostgreSQL units (+ metadata) | `data/study_b/ds/` | Public, released by the author with the data owner's agreement |
| Study B analysis code (structure, nine drift dimensions, corpus experiment S0–S3, comparison mechanisms) | `docs/study_b/e2e/` | Public |
| Study B testbed code (deployment, stub inference, instrumented runs, telemetry collection, detectors) | `docs/study_b/ops/src/`, `docs/study_b/pg/`, `docs/study_b/docker-compose.yml` | Public |
| Measurements recorded on the PostgreSQL 17.11 testbed (incl. telemetry of 10 runs, 123 MB) | `data/study_b/recorded/` | Public |
| Author's original Study B outputs (for comparison) | `data/study_b/reference/` | Public |
| Object-profile classifier from the project *oracle-spec-project* | `docs/study_b/third_party/` | Redistributed with the original author's permission |
| Per-run Study B metrics and aggregates (quick path) | `data/study_b_public/` | Public |
| Figures 1–6 (Figs. 1–3 are the conceptual diagrams as printed in the manuscript; the others are drawn by the scripts) | `docs/figures/`, `code/figures.py`, `code/study_a_lofo.py` | Public |
| Tests, expected values, traceability | `tests/`, `docs/expected/`, `docs/RESULTS_TRACEABILITY.csv` | Public |

Re-running the testbed (Study B level 3) requires PostgreSQL 17; its telemetry depends on timing and hardware and is
therefore not expected to repeat digit for digit. No synthetic data replace primary data.
