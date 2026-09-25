"""Crime Pattern Fingerprint (CPF): a learned, multi-dimensional profile per crime type.

Every dimension is computed from the incidents of the trailing window (default 52 weeks)
before the origin and scaled to [0, 1]. Qualitative labels (LOW / MEDIUM / HIGH) are
presentation cut points at 1/3 and 2/3.

spatial_concentration   Gini coefficient of incidents across zones
time_concentration      1 - normalised entropy of the hour-of-day distribution
weekend_concentration   weekend share relative to the 2/7 expected by chance, /2 (0.5 =
                        proportional, 1.0 = at least double)
repeat_location         share of 4-week periods in which a zone with the crime recorded it
                        again (incident-weighted mean of the CAI recurrence component)
neighbor_spillover      global Moran's I of zone counts (queen contiguity), clipped to [0, 1]
recent_trend            trend component T of the city-wide last 4 weeks vs 52-week rate
hotspot_persistence     share of hot zone-periods (Gi*) that belong to PERSISTENT zones
temporal_similarity     cosine similarity of the last 8 weeks' hour profile to the 52-week one
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.config import ScoringConfig
from ml.preprocessing.grid import Grid
from ml.scoring.formulas import trend_component

DIMENSIONS = (
    "spatial_concentration",
    "time_concentration",
    "weekend_concentration",
    "repeat_location",
    "neighbor_spillover",
    "recent_trend",
    "hotspot_persistence",
    "temporal_similarity",
)


def gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    if x.sum() == 0:
        return 0.0
    n = len(x)
    cum = np.cumsum(x)
    return float((n + 1 - 2 * (cum / cum[-1]).sum()) / n)


def morans_i(x: np.ndarray, w: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    z = x - x.mean()
    denom = (z**2).sum()
    if denom == 0 or w.sum() == 0:
        return 0.0
    return float(len(x) / w.sum() * (z @ w @ z) / denom)


def label(v: float) -> str:
    return "LOW" if v < 1 / 3 else "MEDIUM" if v < 2 / 3 else "HIGH"


def fingerprint(
    incidents: pd.DataFrame,
    crime_type: str,
    as_of: pd.Timestamp,
    grid: Grid,
    zone_crime: pd.DataFrame,
    s: ScoringConfig,
    window_weeks: int = 52,
) -> dict:
    as_of = pd.Timestamp(as_of)
    start = as_of - pd.Timedelta(weeks=window_weeks)
    inc = incidents[
        (incidents["crime_type"] == crime_type)
        & (incidents["timestamp"] >= start)
        & (incidents["timestamp"] < as_of)
    ]
    n = len(inc)
    counts = np.bincount(inc["zone_idx"].to_numpy(), minlength=grid.n_zones)
    hours = np.bincount(inc["hour"].to_numpy(), minlength=24).astype(float)
    p_h = hours / hours.sum() if hours.sum() else np.full(24, 1 / 24)
    nz = p_h[p_h > 0]
    time_conc = 1.0 - float(-(nz * np.log(nz)).sum() / np.log(24))
    weekend_share = float(inc["is_weekend"].mean()) if n else 0.0
    weekend_lift = weekend_share / (2 / 7) if n else 0.0

    zc = zone_crime[zone_crime["crime_type"] == crime_type]
    w_inc = zc["incidents_52w"].to_numpy(dtype=float)
    repeat = float((zc["a_recurrence"] * w_inc).sum() / w_inc.sum()) if w_inc.sum() else 0.0
    moran = morans_i(counts, grid.binary_weights(1, include_self=False))

    recent_start = as_of - pd.Timedelta(weeks=4)
    recent = int((inc["timestamp"] >= recent_start).sum())
    base_rate = (n - recent) / max(window_weeks - 4, 1) * 4
    ratio = (recent - base_rate) / (base_rate + s.count_epsilon)
    trend = float(trend_component(ratio, s.trend_k, s.trend_b))
    direction = "RISING" if ratio > 0.1 else "FALLING" if ratio < -0.1 else "STABLE"

    hot_total = zc["hot_periods"].sum()
    persistent_hot = zc.loc[zc["state"] == "PERSISTENT", "hot_periods"].sum()
    persistence = float(persistent_hot / hot_total) if hot_total else 0.0

    recent_inc = inc[inc["timestamp"] >= as_of - pd.Timedelta(weeks=8)]
    h_recent = np.bincount(recent_inc["hour"].to_numpy(), minlength=24).astype(float)
    denom = np.linalg.norm(h_recent) * np.linalg.norm(hours)
    similarity = float(h_recent @ hours / denom) if denom else 0.0

    values = {
        "spatial_concentration": gini(counts),
        "time_concentration": time_conc,
        "weekend_concentration": min(1.0, weekend_lift / 2),
        "repeat_location": repeat,
        "neighbor_spillover": float(np.clip(moran, 0, 1)),
        "recent_trend": trend,
        "hotspot_persistence": persistence,
        "temporal_similarity": similarity,
    }
    top_hours = np.argsort(-hours)[:3].tolist() if n else []
    return {
        "crime_type": crime_type,
        "window": {"start": start.date().isoformat(), "end": as_of.date().isoformat()},
        "incidents": n,
        "dimensions": [
            {"name": k, "value": round(v, 4), "label": label(v)} for k, v in values.items()
        ],
        "details": {
            "weekend_share": round(weekend_share, 4),
            "weekend_lift": round(weekend_lift, 3),
            "morans_i": round(moran, 4),
            "recent_4w": recent,
            "baseline_4w": round(base_rate, 2),
            "trend_direction": direction,
            "peak_hours": top_hours,
        },
    }
