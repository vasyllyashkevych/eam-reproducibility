# Artifact availability

All artifacts needed to reproduce the paper are included. Nothing is withheld.

| Artifact | Location | Status |
|---|---|---|
| Study A generator, variants, statistics; plan and seeds | `code/multidrift_eval.py`, `code/controlled_drift.py`, `data/study_a/` | Public |
| Joint ablation | `code/dual_profile.py` | Public |
| Study C script (offline) and inputs, OSV cache (5 Nov 2026) | `code/security_cvss.py`, `data/study_c/` | Public (OSV data CC-BY 4.0) |
| Study B migration corpus, 1,802 Oracle → PostgreSQL units (+ metadata) | `study_b/ds/` | Public, released by the author with the data owner's agreement |
| Study B analysis code (structure, nine drift dimensions, corpus experiment S0–S3, comparison mechanisms) | `study_b/e2e/` | Public |
| Study B testbed code (deployment, stub inference, instrumented runs, telemetry collection, detectors) | `study_b/ops/src/`, `study_b/pg/`, `study_b/docker-compose.yml` | Public |
| Measurements recorded on the PostgreSQL 17.11 testbed (incl. telemetry of 10 runs, 123 MB) | `study_b/recorded/` | Public |
| Author's original Study B outputs (for comparison) | `study_b/reference/` | Public |
| Object-profile classifier from the laboratory project *oracle-spec-project* | `study_b/third_party/` | Redistributed with the author's (D. Tukalo) permission |
| Per-run Study B metrics and aggregates (quick path) | `data/study_b_public/` | Public |
| Figures 1–5 | `figures/`, `code/figures.py`, `code/diagrams.py` | Public |
| Tests, expected values, traceability | `tests/`, `expected/`, `RESULTS_TRACEABILITY.csv` | Public |

Re-running the testbed (Study B level 3) requires PostgreSQL 17; its telemetry depends on timing and hardware and is
therefore not expected to repeat digit for digit. No synthetic data replace primary data.
