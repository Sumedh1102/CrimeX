"""Formula handbook checks, including the spec's worked examples."""

from __future__ import annotations

import numpy as np
import pytest

from ml.config import ScoringConfig
from ml.scoring.bands import assign_bands, band_table
from ml.scoring.formulas import (
    anomaly_component,
    blended_risk,
    cai_score,
    consistency,
    crs_contributions,
    crs_score,
    location_quotient,
    recency_component,
    spatial_affinity,
    trend_component,
)

CFG = ScoringConfig()


def test_cai_worked_example_is_87():
    assert cai_score(0.92, 0.83, 0.88, 0.76, CFG.cai_weights) == pytest.approx(87.0)


def test_crs_worked_example_is_79_35():
    comps = dict(zip("FRTASPX", (0.80, 0.90, 0.75, 0.87, 0.65, 0.92, 0.55), strict=True))
    assert crs_score(comps, CFG.crs_weights) == pytest.approx(79.35)
    contrib = crs_contributions(comps, CFG.crs_weights)
    assert sum(float(v) for v in contrib.values()) == pytest.approx(79.35)


def test_components_must_be_normalised():
    with pytest.raises(ValueError):
        cai_score(1.2, 0.5, 0.5, 0.5, CFG.cai_weights)
    with pytest.raises(ValueError):
        blended_risk(1.5, 0.2, 0.6)


def test_location_quotient_and_spatial_affinity():
    # zone share 50% vs city share 10% -> LQ 5
    assert location_quotient(5, 10, 100, 1000) == pytest.approx(5.0)
    assert location_quotient(0, 0, 100, 1000) == 0.0
    assert spatial_affinity(1e6, 10) == pytest.approx(1.0)  # capped
    assert spatial_affinity(0, 10) == 0.0
    assert spatial_affinity(1, 10) == pytest.approx(np.log(2) / np.log(11))


def test_consistency_is_zero_without_incidents():
    assert consistency(np.zeros(13), 1e-6) == 0.0
    assert consistency(np.full(13, 2.0), 1e-6) == pytest.approx(1.0)
    one = np.zeros(13)
    one[0] = 1
    assert consistency(one, 1e-6) == 0.0


def test_recency_trend_anomaly():
    assert recency_component(14, 14) == pytest.approx(0.5)
    assert recency_component(np.inf, 14) == 0.0
    assert trend_component(0.5, 3.0, 0.5) == pytest.approx(0.5)
    assert trend_component(2.0, 3.0, 0.5) > 0.95
    assert anomaly_component(-2, 3) == 0.0
    assert anomaly_component(1.5, 3) == pytest.approx(0.5)
    assert anomaly_component(9, 3) == 1.0


def test_blended_risk():
    assert blended_risk(0.5, 0.5, 0.6) == pytest.approx(50.0)
    assert blended_risk(1.0, 0.0, 0.6) == pytest.approx(60.0)


def test_default_bands_inclusive_upper_bounds():
    labels = assign_bands([0, 20, 20.04, 20.06, 40, 60.5, 80, 99.9, 100], CFG.risk_bands)
    assert labels.tolist() == [
        "LOW",
        "LOW",
        "LOW",  # 20.04 displays as 20.0
        "MODERATE",  # 20.06 displays as 20.1
        "MODERATE",
        "HIGH",
        "HIGH",
        "VERY HIGH",
        "VERY HIGH",
    ]
    assert assign_bands([87.0], CFG.affinity_bands).tolist() == ["Very High"]
    assert band_table(CFG.risk_bands)[0] == {"label": "LOW", "min": 0.0, "max": 20.0}
