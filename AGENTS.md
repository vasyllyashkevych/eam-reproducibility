# Instructions for AI coding assistants (Claude Code, Cursor, others)

This file tells an assistant how to help a reviewer **validate the results of this reproducibility package**
(IJITCS manuscript PAPER021433). Claude Code reads it through `CLAUDE.md`; Cursor and other tools read `AGENTS.md` directly.

## Ground rules

1. **Report only what the files and commands show.** Never estimate, round up, infer or "fill in" a number. Every number you give
   must come from a command you ran or a file in this repository, and you must name that file or command.
2. **Do not edit the expected values or the shipped outputs to make a check pass.** `docs/expected/expected_results.json`,
   `docs/RESULTS_TRACEABILITY.csv`, `MANIFEST.sha256`, `docs/results/` and `docs/figures/` are the author's reference. Write your own outputs
   to a separate folder (for example `EAM_RESULTS_DIR=/tmp/eam_check`, or a fresh clone).
3. **Do not change the experiment code, seeds or inputs** unless the reviewer explicitly asks for a modified experiment.
   If you do, say clearly that the result is no longer a reproduction.
4. **A FAIL is a finding, not a bug to hide.** Report the check id, expected value, obtained value, tolerance and source file.
5. **Say what you did not verify.** The manuscript text is not in this repository (table, figure and equation numbers in the docs refer
   to the manuscript). You can compare the code and the stored expected values; compare with the manuscript only if the
   reviewer gives it to you, and name the version you used.
6. Do not commit, push or delete files unless asked. Do not send repository content to external services.

## What the package contains

| Path | Role |
|---|---|
| `code/` | Study A (`controlled_drift.py`, `multidrift_eval.py`), supplementary LOFO (`study_a_lofo.py`), joint ablation (`dual_profile.py`), Study C (`security_cvss.py`), Study B statistics (`metrics_statistics.py`, `boundary_real.py`), `figures.py`, `check_expected.py`, `results_report.py` |
| `data/` | Study A plan and seeds; Study C snapshots and the frozen OSV cache; per-run Study B metrics (`data/study_b_public/`) |
| `docs/study_b/` | Study B corpus (`ds/`), analysis code (`e2e/`), testbed code (`ops/src/`), recorded PostgreSQL measurements (`recorded/`), author's outputs for comparison (`reference/`) |
| `docs/expected/expected_results.json` | the values printed in the paper, with tolerances and the source of each |
| `docs/RESULTS_TRACEABILITY.csv` | 150 claims → manuscript location, output file, script, command (145 are checked by `check_expected.py`, 5 are visual) |
| `tests/` | unit tests |
| `README.md`, `README_REPRODUCE.md`, `TUTORIAL.md`, `DATA_DICTIONARY.md` | human documentation; read these before answering questions about methods or files |

## Standard validation procedure

Run from the repository root. Use a virtual environment (Python 3.14 was used; 3.12+ should work).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
shasum -a 256 -c MANIFEST.sha256 --quiet && echo "inputs intact"     # Linux: sha256sum -c MANIFEST.sha256
bash run_all.sh                       # Studies A, C, ablation, LOFO, Study B aggregates, figures, number check, tests
bash docs/study_b/run_study_b_offline.sh   # Study B levels 1-2 (about 30 min, no database); ends with a comparison to data/study_b/reference/
```

Interpret the results as follows.

* `run_all.sh` must end with `checks 145  PASS 145  FAIL 0` and a passing `pytest` summary. The table behind it is
  `docs/results/reproduction_summary.md` (expected, obtained, difference, tolerance, PASS/FAIL, source).
* Tolerance is half a unit of the last printed digit; counts must match exactly.
* Study A, the ablation, Study C and the LOFO analysis are deterministic. The Study B offline levels are deterministic with
  `PYTHONHASHSEED=0` (the script sets it); `docs/study_b/compare_with_reference.py` must print `SAME` for every file.
* Wall-clock columns (`t_adapt`, `overhead_ms_step`, `workload_ms_step`) depend on the machine and are not compared.
* Study B level 3 (`docs/study_b/run_study_b_testbed.sh`, PostgreSQL 17, about 2 hours) re-measures timing-dependent telemetry; it is
  **not** expected to repeat digit for digit. Judge it by the statistical comparison the script prints, not by equality.
* The 5 visual claims (figures) cannot be checked by a script; open the files in `docs/figures/` and compare them with the manuscript.

## Typical validation tasks

* *"Does Table N reproduce?"* — look the table up in `docs/RESULTS_TRACEABILITY.csv` (column `manuscript_location`), run the command in
  its `command` column, then read the matching rows of `docs/results/reproduction_summary.md` from your own run.
* *"Why does check X fail?"* — find X in `docs/expected/expected_results.json` (`source_file`, tolerance), open the output file that
  `check_expected.py` read, and compare the raw value. Check the environment first (package versions in `requirements.txt`,
  `PYTHONHASHSEED=0` for Study B, unmodified `data/study_c/osv_cache.json`).
* *"Is a number in the text consistent with the data?"* — recompute it from the CSV/JSON named in `DATA_DICTIONARY.md`
  with a short script; show the script and its output.
* *"What does file/column Y mean?"* — answer from `DATA_DICTIONARY.md` and the docstring at the top of the producing script;
  if neither says, say that the documentation does not cover it.
* *"Is the leave-one-dimension-out result reliable?"* — it is a supplementary analysis (`docs/STUDY_A_LOFO.md`); the all-dimensions
  control must equal the Study A C0 macro-F1 (`Original C0 macro-F1 = 0.968309` in its output). Do not present it as a causal
  ranking, and do not mix it with Study B metrics (PCRw, MRSR, defect recall).

## Known limits to mention in a validation report

* Study B level 3 was run once by the author (18 November 2026); its timing-dependent values are the ones in `data/study_b/recorded/`.
* `run_all.ps1` (Windows) was not executed by the author; `run_all.sh` was verified on macOS (arm64).
* `docs/study_b/third_party/` contains a third-party classifier file redistributed unchanged with its author's permission
  (see `LICENSE_AND_DATA_RIGHTS.md`).
* The insufficient-evidence state of Equation (11) is part of the operational rule and is **not** evaluated as a Study A outcome.

## Report format

Give the reviewer: (1) commands run and the environment (OS, Python and package versions), (2) the number of checks that
passed/failed, (3) every FAIL or difference with expected and obtained values and file names, (4) what was not run or not
verified, and (5) no conclusions beyond the evidence.
