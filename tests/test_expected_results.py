"""Every number in expected/expected_results.json must be reproduced from the regenerated outputs."""
import json
from pathlib import Path

import check_expected

R = Path(__file__).resolve().parents[1] / "results"


def test_all_reported_numbers_reproduce():
    n_fail = check_expected.main()
    rows = json.loads((R / "reproduction_summary.json").read_text())
    failed = [r for r in rows if not r["status"].startswith("PASS")]
    assert n_fail == 0, failed
    assert len(rows) >= 100
