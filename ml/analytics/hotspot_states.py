"""Emerging Hotspot Detection: classify each (zone, crime type) into a hotspot state.

For the last ``n_periods`` periods of ``period_weeks`` windows before the origin, a Gi*
z-score is computed per zone and period; a zone is "hot" in a period when z >= hot_z.
A Mann-Kendall test on the zone's Gi* series gives the trend. Rules, applied in order:

PERSISTENT  hot in >= persistent_min_fraction of periods, no significant downward trend
DECLINING   hot in >= declining_min_early_fraction of the first half, and now either
            significantly trending down or not hot in any recent period
EMERGING    hot in >= emerging_min_recent_hot of the recent periods, hot in at most
            emerging_max_prior_fraction of the periods before them, and the recent
            incident rate exceeds emerging_min_rate_ratio x the earlier rate
ACTIVE      hot in the final period (and none of the above)
SPORADIC    hot in >= sporadic_min_hot_periods periods, not in the final one
STABLE      otherwise: no hotspot pattern in the analysis window

The thresholds are configurable presentation choices (HotspotConfig).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.analytics.gistar import gi_star
from ml.analytics.trend import mann_kendall
from ml.config import HotspotConfig
from ml.preprocessing.grid import Grid

STATES = ("EMERGING", "ACTIVE", "PERSISTENT", "DECLINING", "SPORADIC", "STABLE")
STATE_DESCRIPTIONS = {
    "EMERGING": "Recently became a statistically significant hotspot after little or no "
    "earlier hotspot activity.",
    "ACTIVE": "A statistically significant hotspot in the most recent period.",
    "PERSISTENT": "A statistically significant hotspot in most periods of the analysis window.",
    "DECLINING": "Was a frequent hotspot earlier in the window; hotspot intensity is now "
    "decreasing or absent.",
    "SPORADIC": "An on-and-off hotspot: significant in some periods but not the most recent.",
    "STABLE": "No hotspot pattern in the analysis window.",
}


def period_counts(zc_counts: np.ndarray, origin_k: int, period: int, n_periods: int) -> np.ndarray:
    """(Z, C, n_periods) counts for consecutive periods ending at window ``origin_k``."""
    start = origin_k - period * n_periods
    if start < 0:
        raise ValueError("Not enough history for the hotspot-state analysis window")
    block = zc_counts[..., start:origin_k]
    Z, C, _ = block.shape
    return block.reshape(Z, C, n_periods, period).sum(axis=-1)


def classify_states(
    zc_counts: np.ndarray,
    origin_k: int,
    grid: Grid,
    crime_types: tuple[str, ...],
    cfg: HotspotConfig,
    period_windows: int | None = None,
) -> pd.DataFrame:
    period = period_windows or cfg.period_weeks
    n = cfg.n_periods
    pc = period_counts(zc_counts, origin_k, period, n)  # (Z, C, n)
    w = grid.binary_weights(cfg.gi_neighbor_radius_cells, include_self=True)
    rows = []
    recent_n = cfg.recent_periods
    half = n // 2
    for ci, code in enumerate(crime_types):
        z = gi_star(pc[:, ci, :], w)  # (Z, n)
        hot = z >= cfg.hot_z
        tau, _, p = mann_kendall(z)
        frac = hot.mean(axis=1)
        early_frac = hot[:, :half].mean(axis=1)
        prior_frac = hot[:, : n - recent_n].mean(axis=1)
        recent_hot = hot[:, n - recent_n :].sum(axis=1)
        final_hot = hot[:, -1]
        n_hot = hot.sum(axis=1)
        sig_down = (p < cfg.trend_alpha) & (tau < 0)
        sig_up = (p < cfg.trend_alpha) & (tau > 0)

        state = np.full(grid.n_zones, "STABLE", dtype=object)
        undecided = np.ones(grid.n_zones, dtype=bool)

        def assign(mask, label, undecided=undecided, state=state):
            m = mask & undecided
            state[m] = label
            undecided[m] = False

        assign((frac >= cfg.persistent_min_fraction) & ~sig_down, "PERSISTENT")
        assign(
            (early_frac >= cfg.declining_min_early_fraction) & (sig_down | (recent_hot == 0)),
            "DECLINING",
        )
        counts_c = pc[:, ci, :]
        recent_rate = counts_c[:, n - recent_n :].mean(axis=1)
        prior_rate = counts_c[:, : n - recent_n].mean(axis=1)
        rising = recent_rate > cfg.emerging_min_rate_ratio * prior_rate
        assign(
            (recent_hot >= cfg.emerging_min_recent_hot)
            & (prior_frac <= cfg.emerging_max_prior_fraction)
            & rising,
            "EMERGING",
        )
        assign(final_hot, "ACTIVE")
        assign(n_hot >= cfg.sporadic_min_hot_periods, "SPORADIC")

        # current run of consecutive hot periods ending at the final period
        run = np.zeros(grid.n_zones, dtype=int)
        for t in range(n - 1, -1, -1):
            still = hot[:, t] & (run == (n - 1 - t))
            run[still] += 1
        for zi, zid in enumerate(grid.zone_ids):
            rows.append(
                {
                    "zone_id": zid,
                    "crime_type": code,
                    "state": state[zi],
                    "hot_periods": int(n_hot[zi]),
                    "n_periods": n,
                    "hot_fraction": round(float(frac[zi]), 3),
                    "recent_hot_periods": int(recent_hot[zi]),
                    "final_period_hot": bool(final_hot[zi]),
                    "current_hot_run_periods": int(run[zi]),
                    "trend_tau": round(float(tau[zi]), 3),
                    "trend_p": round(float(p[zi]), 4),
                    "recent_rate": round(float(recent_rate[zi]), 3),
                    "prior_rate": round(float(prior_rate[zi]), 3),
                    "trend": "INCREASING"
                    if sig_up[zi]
                    else "DECREASING"
                    if sig_down[zi]
                    else "NO SIGNIFICANT TREND",
                    "gi_z_last": round(float(z[zi, -1]), 3),
                    "gi_z_series": np.round(z[zi], 2).tolist(),
                    "count_series": pc[zi, ci].astype(int).tolist(),
                }
            )
    return pd.DataFrame(rows)
