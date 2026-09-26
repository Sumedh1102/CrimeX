"""Hotspot lifecycle, hotspot movement and historical pattern matching."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.analytics.analogs import match_series, pattern_matches
from ml.analytics.hotspot_states import period_windows
from ml.analytics.lifecycle import (
    bearing,
    compass,
    hot_clusters,
    hotspot_lifecycle,
    hotspot_movement,
    lifecycle_origins,
    lifecycle_summary,
    stage_of,
)
from ml.config import HotspotConfig


def test_period_windows_follow_window_length():
    cfg = HotspotConfig(period_weeks=4)
    assert period_windows(cfg, 7) == 4
    assert period_windows(cfg, 1) == 28


def test_stage_mapping():
    assert stage_of("EMERGING", None) == "EMERGING"
    assert stage_of("STABLE", None) == "NORMAL"
    assert stage_of("SPORADIC", "ACTIVE") == "RESOLVED"
    assert stage_of("STABLE", "RESOLVED") == "NORMAL"
    assert stage_of("PERSISTENT", "NORMAL") == "PERSISTENT"


def test_lifecycle_origins_skip_missing_history():
    assert lifecycle_origins(100, 4, 10, 3) == [92, 96, 100]
    # only origins with period * n_periods windows of history are kept
    assert lifecycle_origins(45, 4, 10, 3) == [41, 45]


def test_compass():
    assert compass(bearing(19.0, 72.8, 19.1, 72.8)) == "N"
    assert compass(bearing(19.0, 72.8, 19.0, 72.9)) == "E"
    assert compass(bearing(19.1, 72.9, 19.0, 72.8)) == "SW"


def _moving_block(grid, n_windows, period, shift_at):
    """Counts with one hot zone that jumps to a zone two cells east at ``shift_at``."""
    lk = grid.lookup
    r, c = next(
        (r, c)
        for r in range(2, grid.n_rows - 2)
        for c in range(2, grid.n_cols - 4)
        if (lk[r - 1 : r + 2, c - 1 : c + 4] >= 0).all()
    )
    a, b = lk[r, c], lk[r, c + 2]
    counts = np.ones((grid.n_zones, 1, n_windows))
    counts[a, 0, :shift_at] = 30
    counts[b, 0, shift_at:] = 30
    return counts, a, b


def test_lifecycle_and_movement_track_a_shifting_hotspot(small_grid):
    cfg = HotspotConfig(n_periods=6, period_weeks=4, recent_periods=2, lifecycle_steps=4)
    period = 4
    n = 6 * period + 4 * period
    counts, a, b = _moving_block(small_grid, n, period, shift_at=n - period)
    origins = pd.date_range("2025-01-01", periods=n + 1, freq="7D")
    lc = hotspot_lifecycle(counts, n, origins, small_grid, ("THEFT",), cfg, period)
    assert sorted(lc["step"].unique()) == [0, 1, 2, 3]
    za, zb = small_grid.zone_ids[a], small_grid.zone_ids[b]
    last = lc[lc["step"] == 3].set_index("zone_id")["stage"]
    assert last[zb] in {"EMERGING", "ACTIVE"}
    first = lc[lc["step"] == 0].set_index("zone_id")["stage"]
    assert first[za] in {"ACTIVE", "PERSISTENT"}
    summary = lifecycle_summary(lc).set_index("zone_id")
    assert summary.loc[zb, "stage_changed"]

    mv = hotspot_movement(lc, small_grid, cfg)
    step3 = mv[mv["step"] == 3]
    moved = step3[step3["zones"].map(lambda z: zb in z)]
    assert len(moved) == 1
    row = moved.iloc[0]
    # the cluster moved east by about two cells (Gi* smooths the centroid)
    assert row["kind"] in {"SHIFTED", "CONTINUED"}
    if row["kind"] == "SHIFTED":
        assert row["direction"] in {"E", "NE", "SE"}
        # linked by shared zones, so the distance cap does not apply; about two cells
        assert 0.5 * small_grid.cell_km <= row["distance_km"] <= 2.5 * small_grid.cell_km


def test_hot_clusters_group_contiguous_zones(small_grid):
    z = np.zeros(small_grid.n_zones)
    assert hot_clusters(z, small_grid, 1.96) == []
    lk = small_grid.lookup
    r, c = next(
        (r, c)
        for r in range(small_grid.n_rows)
        for c in range(small_grid.n_cols - 1)
        if lk[r, c] >= 0 and lk[r, c + 1] >= 0
    )
    z[[lk[r, c], lk[r, c + 1]]] = [3.0, 2.5]
    cl = hot_clusters(z, small_grid, 1.96)
    assert len(cl) == 1 and len(cl[0]["members"]) == 2
    lo, hi = sorted(small_grid.centroid_lon[[lk[r, c], lk[r, c + 1]]])
    assert lo < cl[0]["lon"] < hi


def test_match_series_finds_the_repeat_and_never_overlaps_the_present():
    rng = np.random.default_rng(0)
    x = rng.poisson(1.0, 120).astype(float)
    motif = np.array([0, 5, 9, 2, 0, 7, 1, 3.0])
    x[30:38] = motif
    x[38] = 11  # what followed the motif
    x[-8:] = motif
    js, sim = match_series(x, lookback=8, top_k=3)
    assert js[0] == 38 and sim[0] == pytest.approx(1.0)
    assert np.all(js <= len(x) - 8 - 1)  # outcome precedes the current sequence
    assert np.all(np.diff(np.sort(js)) > 8)  # non-overlapping
    assert np.all((sim > 0) & (sim <= 1))


def test_match_series_short_history():
    js, sim = match_series(np.ones(10), lookback=8, top_k=5)
    assert js.size == 0 and sim.size == 0


def test_pattern_matches_table(small_panel):
    k = small_panel.W
    df = pattern_matches(
        small_panel.zc_counts,
        k,
        small_panel.origins,
        small_panel.zones,
        small_panel.crime_types,
        8,
        5,
    )
    assert len(df) == len(small_panel.zones) * len(small_panel.crime_types)
    row = df.iloc[0]
    assert len(row["current_counts"]) == 8
    assert row["n_analogs"] == 5
    for a in row["analogs"]:
        assert a["outcome_start"] < row["current_start"]
