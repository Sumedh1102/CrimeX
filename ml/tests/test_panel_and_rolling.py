from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from ml.features.rolling import (
    cumsum0,
    effective_length,
    trailing_exp_weighted,
    trailing_mean_std,
    trailing_sum,
)
from ml.preprocessing.panel import build_panel


def _incidents(rows):
    return pd.DataFrame(rows, columns=["timestamp", "zone_id", "crime_type", "band"]).assign(
        timestamp=lambda d: pd.to_datetime(d["timestamp"])
    )


def test_panel_windows_are_anchored_at_as_of():
    inc = _incidents(
        [
            ("2026-01-01 10:00", "Z1", "THEFT", "MORNING"),  # before first full window
            ("2026-01-02 10:00", "Z1", "THEFT", "MORNING"),  # window 0
            ("2026-01-08 23:59", "Z1", "THEFT", "EVENING"),  # window 0 (ends 01-09)
            ("2026-01-09 00:00", "Z2", "HURT", "NIGHT"),  # window 1
            ("2026-01-15 12:00", "Z2", "HURT", "AFTERNOON"),  # window 1
        ]
    )
    p = build_panel(
        inc,
        ["Z1", "Z2"],
        ["THEFT", "HURT"],
        ["NIGHT", "MORNING", "AFTERNOON", "EVENING"],
        as_of=date(2026, 1, 16),
        window_days=7,
    )
    assert list(p.origins.strftime("%m-%d")) == ["01-02", "01-09", "01-16"]
    assert p.counts.shape == (2, 2, 4, 2)
    assert p.counts[0, 0, :, 0].tolist() == [0, 1, 0, 1]
    assert p.counts[1, 1, :, 1].tolist() == [1, 0, 1, 0]
    assert p.counts.sum() == 4
    # days since last incident at each origin (Z1/THEFT: last seen 01-08 23:59)
    assert np.isinf(p.days_since_last[0, 0, 0])  # 01-01 is before the panel start
    assert np.isclose(p.days_since_last[0, 0, 1], 1 / 1440)
    assert np.isclose(p.days_since_last[1, 1, 2], 0.5)


def test_trailing_sum_uses_only_past_windows():
    x = np.array([1.0, 2.0, 3.0, 4.0])  # windows 0..3; origins 0..4
    cs = cumsum0(x)
    assert trailing_sum(cs, 2).tolist() == [0, 1, 3, 5, 7]
    assert trailing_sum(cs, 1, lag=1).tolist() == [0, 0, 1, 2, 3]
    assert effective_length(5, 2).tolist() == [0, 1, 2, 2, 2]


def test_changing_the_target_window_never_changes_its_features():
    rng = np.random.default_rng(0)
    x = rng.poisson(1.0, size=(3, 40)).astype(float)
    k = 30
    y = x.copy()
    y[:, k:] += 100  # alter the target window and everything after it
    for fn in (
        lambda a: trailing_sum(cumsum0(a), 8),
        lambda a: trailing_mean_std(cumsum0(a), cumsum0(a**2), 12, lag=1)[1],
        lambda a: trailing_exp_weighted(a, 10, 0.9),
    ):
        assert np.allclose(fn(x)[:, : k + 1], fn(y)[:, : k + 1])


def test_trailing_exp_weighted_matches_direct_sum():
    rng = np.random.default_rng(1)
    x = rng.poisson(2.0, size=25).astype(float)
    decay, length = 0.8, 6
    got = trailing_exp_weighted(x, length, decay)
    for k in range(len(x) + 1):
        direct = sum(x[k - L] * decay ** (L - 0.5) for L in range(1, length + 1) if k - L >= 0)
        assert np.isclose(got[k], direct)


def test_trailing_mean_std():
    x = np.array([1.0, 3.0, 5.0, 7.0])
    m, s = trailing_mean_std(cumsum0(x), cumsum0(x**2), 2)
    assert np.allclose(m, [0, 1, 2, 4, 6])
    assert np.allclose(s, [0, 0, 1, 1, 1])
