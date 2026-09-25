"""Dense count panel: incidents per (zone, crime type, time band, window).

Windows are ``window_days`` long and anchored at the forecast origin (``as_of``):
``origins[k]`` is the start of window ``k`` and ``origins[-1] == as_of`` is the start
of the forecast window, whose counts are unknown. ``counts[..., k]`` holds window
``[origins[k], origins[k+1])`` for ``k < W``. A feature "at origin k" may only use
windows ``< k``; ``ml.features.rolling`` enforces that by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass
class CountPanel:
    zones: tuple[str, ...]
    crime_types: tuple[str, ...]
    bands: tuple[str, ...]
    origins: pd.DatetimeIndex  # length K = W + 1
    window_days: int
    counts: np.ndarray  # (Z, C, B, W) int32
    days_since_last: np.ndarray  # (Z, C, K) float32; inf when no earlier incident

    @property
    def W(self) -> int:
        return self.counts.shape[-1]

    @property
    def K(self) -> int:
        return len(self.origins)

    @property
    def zc_counts(self) -> np.ndarray:
        """(Z, C, W) counts summed over time bands."""
        return self.counts.sum(axis=2)


def build_panel(
    incidents: pd.DataFrame,
    zones: tuple[str, ...] | list[str],
    crime_types: tuple[str, ...] | list[str],
    bands: tuple[str, ...] | list[str],
    as_of: date,
    window_days: int,
    start: date | None = None,
) -> CountPanel:
    zones, crime_types, bands = tuple(zones), tuple(crime_types), tuple(bands)
    as_of_ts = pd.Timestamp(as_of)
    first = pd.Timestamp(start) if start else incidents["timestamp"].min().normalize()
    W = int((as_of_ts - first).days // window_days)
    if W < 1:
        raise ValueError("Not enough history for a single window")
    origins = pd.DatetimeIndex(
        [as_of_ts - pd.Timedelta(days=window_days * (W - k)) for k in range(W + 1)]
    )
    t0 = origins[0]

    inc = incidents[(incidents["timestamp"] >= t0) & (incidents["timestamp"] < as_of_ts)]
    zi = pd.Categorical(inc["zone_id"], categories=zones).codes.astype(np.int64)
    ci = pd.Categorical(inc["crime_type"], categories=crime_types).codes.astype(np.int64)
    bi = pd.Categorical(inc["band"], categories=bands).codes.astype(np.int64)
    if (zi < 0).any() or (ci < 0).any() or (bi < 0).any():
        raise ValueError("Incidents reference zones, crime types or bands outside the panel")
    elapsed = (inc["timestamp"] - t0).to_numpy().astype("timedelta64[s]").astype(np.int64)
    wi = elapsed // (window_days * 86_400)
    Z, C, B = len(zones), len(crime_types), len(bands)
    flat = ((zi * C + ci) * B + bi) * W + wi
    counts = np.bincount(flat, minlength=Z * C * B * W).reshape(Z, C, B, W).astype(np.int32)

    # days from the most recent incident (same zone and crime type, any band) to each origin
    days_since = np.full((Z, C, W + 1), np.inf, dtype=np.float32)
    ts_sec = inc["timestamp"].to_numpy().astype("datetime64[s]").astype(np.int64)
    origin_sec = origins.to_numpy().astype("datetime64[s]").astype(np.int64)
    group = zi.astype(np.int64) * C + ci
    order = np.lexsort((ts_sec, group))
    g_sorted, t_sorted = group[order], ts_sec[order]
    bounds = np.searchsorted(g_sorted, np.arange(Z * C + 1))
    for g in range(Z * C):
        a, b = bounds[g], bounds[g + 1]
        if a == b:
            continue
        tg = t_sorted[a:b]
        idx = np.searchsorted(tg, origin_sec, side="left") - 1
        ok = idx >= 0
        d = np.full(W + 1, np.inf)
        d[ok] = (origin_sec[ok] - tg[idx[ok]]) / 86_400.0
        days_since[g // C, g % C] = d
    return CountPanel(zones, crime_types, bands, origins, window_days, counts, days_since)
