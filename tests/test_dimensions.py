"""Unit tests of the drift operators used in the paper (Eqs. (5), (8), (10))."""
import numpy as np
import pytest

import controlled_drift as cd
import security_cvss as sc


def test_cvss_base_score_matches_first_specification():
    assert sc.cvss3("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == 9.8   # FIRST v3.1 reference vector
    assert sc.cvss3("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N") == 6.1
    assert sc.cvss3("CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:N") == 0.0


def test_exposure_index_eq8():
    assert sc.exposure([]) == 0.0
    assert sc.exposure([5.0, 5.0]) == pytest.approx(0.75)          # 1 - (1-0.5)(1-0.5)
    assert sc.exposure([5.5, 5.5, 5.5]) > 0.7                      # several moderate advisories cross 0.7
    assert sc.exposure([9.8]) == pytest.approx(0.98)


def test_edi_is_weighted_mean_over_observed_dimensions_eq10():
    d = np.array([[0.2, 0.4, np.nan, 0.0, 1.0, 0.5, np.nan, 0.1, 0.3]])
    obs = ~np.isnan(d[0])
    expected = (d[0][obs] * cd.W[obs]).sum() / cd.W[obs].sum()
    assert cd.edi(d)[0] == pytest.approx(expected)
    assert cd.W.sum() == pytest.approx(1.0)


def test_reference_operator_eq5_is_bounded():
    obs = cd.generate(1)
    d = cd.ref_indicators(obs)
    assert np.nanmin(d) >= 0.0 and np.nanmax(d) <= 1.0


def test_versioned_reference_masks_only_released_dimensions_during_window():
    obs = cd.generate(1, release=True)
    d = cd.ref_indicators(obs, reference_update=True, release=True)
    a, b = cd.RELEASE_T - 1, cd.RELEASE_T - 1 + cd.TRANSITION
    assert np.isnan(d[a:b, cd.RELEASE_DIMS]).all()
    others = [i for i in range(cd.ND) if i not in cd.RELEASE_DIMS]
    assert not np.isnan(d[:, others]).any()
