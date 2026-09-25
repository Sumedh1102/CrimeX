from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from ml.analytics.anomaly import surge_table
from ml.analytics.gistar import benjamini_hochberg, classify, gi_star
from ml.analytics.hotspot_states import classify_states
from ml.analytics.hotspots import hotspot_map
from ml.analytics.trend import mann_kendall
from ml.config import HotspotConfig
from ml.features.engine import compute_components


def test_gi_star_spike_and_uniform(small_grid):
    w = small_grid.binary_weights(1, include_self=True)
    x = np.zeros(small_grid.n_zones)
    centre = int(np.argmax(w.sum(axis=1)))  # a zone with a full neighbourhood
    x[centre] = 20
    z = gi_star(x, w)
    # Gi* scores the neighbourhood: the spike's own window and its neighbours' windows
    # are positive, everything outside is below the mean
    assert z[centre] > 1.96
    assert np.all(z[w[centre] == 0] < 0)
    assert np.allclose(gi_star(np.full(small_grid.n_zones, 3.0), w), 0)


def test_classify_and_fdr():
    z = np.array([3.0, 2.0, 1.7, 0.0, -2.0])
    assert classify(z).tolist() == ["HOT_99", "HOT_95", "HOT_90", "NOT_SIGNIFICANT", "COLD_95"]
    keep = benjamini_hochberg(np.array([0.001, 0.02, 0.04, 0.5]), alpha=0.05)
    assert keep.tolist() == [True, True, False, False]


def test_mann_kendall():
    tau, z, p = mann_kendall(np.array([[1, 2, 3, 4, 5, 6, 7, 8.0], [5.0] * 8]))
    assert tau[0] == pytest.approx(1.0) and p[0] < 0.01
    assert tau[1] == 0 and p[1] == pytest.approx(1.0)


def test_hotspot_map_columns(small_grid):
    counts = np.zeros(small_grid.n_zones, dtype=int)
    counts[5] = 30
    df = hotspot_map(counts, small_grid, HotspotConfig())
    assert set(df.columns) >= {"zone_id", "count", "gi_z", "gi_p", "hotspot_class"}
    assert df.loc[5, "hotspot_class"].startswith("HOT")


def _isolated_zones(grid, n):
    """n zones whose 5x5 neighbourhoods do not overlap."""
    chosen = []
    for i in range(grid.n_zones):
        if all(
            max(abs(grid.rows[i] - grid.rows[j]), abs(grid.cols[i] - grid.cols[j])) > 4
            for j in chosen
        ):
            chosen.append(i)
        if len(chosen) == n:
            return chosen
    raise AssertionError("grid too small")


def test_state_rules_on_constructed_patterns(small_grid):
    cfg = HotspotConfig()
    n, period = cfg.n_periods, cfg.period_weeks
    W = n * period
    rng = np.random.default_rng(0)
    counts = rng.poisson(0.05, size=(small_grid.n_zones, 1, W)).astype(float)
    persistent, emerging, declining, sporadic = _isolated_zones(small_grid, 4)
    w = small_grid.binary_weights(1, include_self=False)

    def plant(zone, windows, rate):
        # hotspots are clusters: the zone plus a spill-over into its neighbours
        counts[zone, 0, windows] += rate
        counts[w[zone] > 0, 0, windows] += rate / 2

    plant(persistent, slice(None), 6)
    plant(emerging, slice(W - 3 * period, W), 8)
    plant(declining, slice(0, (n // 2) * period), 8)
    for t in (2, 9, 17):
        plant(sporadic, slice(t * period, (t + 1) * period), 8)
    st = classify_states(counts, W, small_grid, ("THEFT",), cfg).set_index("zone_id")
    zid = small_grid.zone_ids
    assert st.loc[zid[persistent], "state"] == "PERSISTENT"
    assert st.loc[zid[emerging], "state"] == "EMERGING"
    assert st.loc[zid[declining], "state"] == "DECLINING"
    assert st.loc[zid[sporadic], "state"] == "SPORADIC"
    assert set(st["state"]) <= {
        "EMERGING",
        "ACTIVE",
        "PERSISTENT",
        "DECLINING",
        "SPORADIC",
        "STABLE",
    }


def test_component_ranges(small_components, small_panel):
    cp = small_components
    k = cp.windows.required_history
    for name in ("T", "X", "P", "a_spatial", "a_recency", "a_recurrence", "a_consistency"):
        arr = getattr(cp, name)[..., k:]
        assert np.all((arr >= 0) & (arr <= 1 + 1e-6)), name
    assert np.all((cp.cai >= 0) & (cp.cai <= 100 + 1e-4))
    assert np.allclose(np.linalg.norm(cp.band_share, axis=2) > 0, True)


def test_components_never_use_the_target_window(
    small_panel, small_grid, small_cfg, small_components
):
    k = small_panel.W - 10
    altered = dataclasses.replace(small_panel, counts=small_panel.counts.copy())
    altered.counts[..., k:] += 3
    cp2 = compute_components(altered, small_grid, small_cfg.scoring)
    for f in dataclasses.fields(small_components):
        a = getattr(small_components, f.name)
        if isinstance(a, np.ndarray) and a.ndim >= 2:
            b = getattr(cp2, f.name)
            assert np.allclose(a[..., : k + 1], b[..., : k + 1], equal_nan=True), f.name


def test_surge_table_flags_recent_planted_surges(
    small_components, small_panel, small_cfg, generated
):
    sg = surge_table(
        small_components,
        small_panel.W,
        small_panel.zones,
        small_panel.crime_types,
        small_cfg.scoring,
    )
    recent = generated["ground_truth"]["anomalies"][: small_cfg.synthetic.n_recent_anomalies]
    flagged = set(
        zip(sg.loc[sg.is_alert, "zone_id"], sg.loc[sg.is_alert, "crime_type"], strict=True)
    )
    hits = sum((a["zone"], a["crime_type"]) in flagged for a in recent)
    assert hits >= len(recent) - 1  # allow one miss to Poisson noise


def test_cai_is_higher_at_persistent_hotspots(small_components, small_panel, generated):
    k = small_panel.W
    cai = small_components.cai[..., k]
    zidx = {z: i for i, z in enumerate(small_panel.zones)}
    cidx = {c: i for i, c in enumerate(small_panel.crime_types)}
    wins = []
    for h in generated["ground_truth"]["hotspots"]:
        if h["kind"] != "persistent":
            continue
        c = cidx[h["crime_type"]]
        wins.append(cai[zidx[h["center_zone"]], c] > np.median(cai[:, c]))
    assert np.mean(wins) >= 0.8
