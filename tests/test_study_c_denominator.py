"""Study C denominators: 5 x 50 snapshots, 5 x 49 transitions, 3 increases, 2 decreases, 240 others."""
import json
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[1] / "results"


def test_snapshot_and_transition_counts():
    S = pd.read_csv(R / "security_drift_snapshots.csv")
    assert len(S) == 250 and S.groupby("repo").size().eq(50).all()
    T = S[S.seq > 0]
    assert len(T) == 245 == 5 * 49
    assert (T.dd_sec > 0).sum() == 3 and (T.dd_sec < 0).sum() == 2 and (T.dd_sec == 0).sum() == 240


def test_summary_matches_snapshot_table():
    s = json.loads((R / "security_drift_summary.json").read_text())
    assert s["transitions"] == 245 and s["security_events"] == 5
    assert round(s["spearman_idi_vs_dsec"][0], 3) == -0.118 and round(s["spearman_idi_vs_dsec"][1], 3) == 0.065
    assert s["alert_static_rate_elsewhere"] == 0.113 and s["alert_ewma_rate_elsewhere"] == 0.108
    assert s["exposure_increases_without_code_change"] == 2
