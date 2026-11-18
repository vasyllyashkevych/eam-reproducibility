"""Algorithm 1 / Eq. (14): one-off release trigger, runtime hysteresis, W = 8 mask, parameters of Sec. 6.4."""
import numpy as np

import controlled_drift as cd
import dual_profile as dp


def test_parameters_match_the_paper():
    assert dp.THETA == 0.35 and dp.WIN == 8 and dp.T_REL == 25
    assert sorted(dp.REL_DIMS) == [2, 7]                     # role and goal
    assert dp.SHIFT / cd.md.DELTA_CRIT == 0.625              # Delta_rel for role/goal
    assert dp.NPROP == 36 and sum(len(s) == 2 for s in dp.PHI_TRUE) == 9
    assert list(cd.TRAIN) == list(range(101, 111)) and list(cd.TEST) == list(range(1, 41))


def test_runtime_trigger_fires_once_and_rearms_below_half_threshold():
    d = np.zeros((dp.N, dp.ND))
    series = [0.0, 0.40, 0.50, 0.60, 0.30, 0.20, 0.10, 0.36, 0.90]
    d[: len(series), 0] = series
    trig = dp.zone_triggers(d, use_run=True, use_rel=False)
    fired = [t for t in range(dp.N) if ("run", 0) in trig[t]]
    assert fired == [1, 7]          # first crossing; 0.30 and 0.20 do not re-arm (>= 0.175); 0.10 re-arms


def test_score_staying_above_threshold_does_not_rebuild_every_step():
    d = np.full((dp.N, dp.ND), 0.9)
    trig = dp.zone_triggers(d, use_run=True, use_rel=False)
    assert sum(len(x) for x in trig) == dp.ND                 # one event per dimension in 120 steps


def test_release_profile_fires_once_at_release_step():
    trig = dp.zone_triggers(np.zeros((dp.N, dp.ND)), use_run=False, use_rel=True)
    events = [(t, k) for t in range(dp.N) for k in trig[t]]
    assert events == [(dp.T_REL - 1, ("rel", 2)), (dp.T_REL - 1, ("rel", 7))] or \
           sorted(events) == sorted([(dp.T_REL - 1, ("rel", 2)), (dp.T_REL - 1, ("rel", 7))])


def test_full_regeneration_rebuilds_all_probes_per_trigger():
    trig = [set() for _ in range(dp.N)]
    trig[30].add(("run", 0))
    _, rb_sel = dp.probe_validity(trig, dp.PHI_TRUE)
    _, rb_full = dp.probe_validity(trig, dp.PHI_TRUE, full=True)
    assert rb_full == dp.NPROP and rb_sel < rb_full
