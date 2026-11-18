#!/usr/bin/env bash
# Reproduce Study A, Study C, the joint ablation, Study B aggregates and Fig. 1-5 from a clean copy.
# Usage: bash run_all.sh            (no path editing needed; all paths are relative to this folder)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs results figures
LOG=logs/verification_log.txt
{
  echo "== run_all.sh started $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python3 --version
  python3 -c "import numpy, pandas, scipy, matplotlib; print('numpy', numpy.__version__, 'pandas', pandas.__version__, 'scipy', scipy.__version__, 'matplotlib', matplotlib.__version__)"
  echo "== SHA-256 check of shipped inputs"
  shasum -a 256 -c MANIFEST.sha256 --quiet && echo "MANIFEST OK"
  cd code
  echo "== Study A";            time python3 controlled_drift.py   > ../logs/study_a_stdout.txt
  echo "== joint ablation";     time python3 dual_profile.py       > ../logs/ablation_stdout.txt
  echo "== Study C (offline)";  time python3 security_cvss.py      > ../logs/study_c_stdout.txt
  echo "== Study B aggregates"; time python3 metrics_statistics.py > ../logs/study_b_stdout.txt
  echo "== failure prediction, Table 10 (needs study_b/e2e/out from study_b/run_study_b_offline.sh)"
  python3 boundary_real.py > ../logs/boundary_stdout.txt 2>&1 || echo "SKIPPED: run bash study_b/run_study_b_offline.sh first; Table 10 is then also checked there"
  echo "== figures";            python3 figures.py; python3 diagrams.py || echo "diagrams: SVG written; PNG needs rsvg-convert"
  echo "== compare with the manuscript"; python3 check_expected.py
  cd ..
  echo "== tests"; python3 -m pytest -q tests
  echo "== run_all.sh finished $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$LOG"
