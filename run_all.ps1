# Windows PowerShell equivalent of run_all.sh (same steps; requires Python 3 on PATH).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force logs, results, figures | Out-Null
$log = "logs/verification_log_windows.txt"
& {
  python --version
  Get-Content MANIFEST.sha256 | ForEach-Object {
    $h, $f = $_ -split "  ", 2
    if ((Get-FileHash $f -Algorithm SHA256).Hash.ToLower() -ne $h) { throw "checksum mismatch: $f" }
  }
  "MANIFEST OK"
  Push-Location code
  python controlled_drift.py   > ../logs/study_a_stdout.txt
  python dual_profile.py       > ../logs/ablation_stdout.txt
  python security_cvss.py      > ../logs/study_c_stdout.txt
  python metrics_statistics.py > ../logs/study_b_stdout.txt
  python figures.py
  python diagrams.py
  python check_expected.py
  Pop-Location
  python -m pytest -q tests
} *>&1 | Tee-Object -FilePath $log
# Note: run_all.ps1 has not been executed on Windows by the author; run_all.sh was verified on macOS.
