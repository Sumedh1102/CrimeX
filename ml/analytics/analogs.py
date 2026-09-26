"""Historical pattern matching: past count sequences that resemble the current one.

For a zone and crime type, the current sequence is the counts of the last ``L`` windows
before the origin (``L`` = ``patterns.lookback_weeks`` in panel windows). Every earlier
sequence of the same zone and crime type whose following window ("outcome") ends before
the current sequence starts is a candidate. Distance is the RMSE between log(1 + count)
sequences, and ``similarity = exp(-RMSE)`` (1 = identical). The ``top_k`` most similar
candidates are chosen greedily so that no two overlap.

The outcome counts of these analogs describe what followed similar patterns in the past.
They are a descriptive comparison, not a forecast; the calibrated model probability stays
the only probability shown.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


def match_series(x: np.ndarray, lookback: int, top_k: int) -> tuple[np.ndarray, np.ndarray]:
    """Analog origins j (context x[j-L:j], outcome x[j]) and their similarities.

    ``x`` holds the observed windows before the origin (length k). Candidates need
    j <= k - L - 1 so the outcome window precedes the current context.
    """
    k = len(x)
    L = lookback
    last_j = k - L - 1
    if last_j < L:
        return np.array([], dtype=int), np.array([])
    lx = np.log1p(x.astype(float))
    cur = lx[k - L :]
    ctx = sliding_window_view(lx[:last_j], L)  # row r -> context of j = r + L
    rmse = np.sqrt(((ctx - cur) ** 2).mean(axis=1))
    order = np.argsort(rmse, kind="stable")
    chosen: list[int] = []
    for r in order:
        j = int(r) + L
        if all(abs(j - c) > L for c in chosen):
            chosen.append(j)
            if len(chosen) == top_k:
                break
    js = np.array(chosen, dtype=int)
    return js, np.exp(-rmse[js - L])


def pattern_matches(
    zc_counts: np.ndarray,
    origin_k: int,
    origins: pd.DatetimeIndex,
    zones: tuple[str, ...],
    crime_types: tuple[str, ...],
    lookback: int,
    top_k: int,
) -> pd.DataFrame:
    """One row per (zone, crime type) with the current sequence, analogs and a summary."""
    rows = []
    for zi, z in enumerate(zones):
        for ci, c in enumerate(crime_types):
            x = zc_counts[zi, ci, :origin_k]
            js, sim = match_series(x, lookback, top_k)
            analogs = [
                {
                    "context_start": origins[j - lookback].date().isoformat(),
                    "outcome_start": origins[j].date().isoformat(),
                    "context_counts": x[j - lookback : j].astype(int).tolist(),
                    "outcome_count": int(x[j]),
                    "similarity": round(float(s), 4),
                }
                for j, s in zip(js, sim, strict=True)
            ]
            outcomes = np.array([a["outcome_count"] for a in analogs], dtype=float)
            hist = x[lookback:] if len(x) > lookback else x
            rows.append(
                {
                    "zone_id": z,
                    "crime_type": c,
                    "current_start": origins[max(origin_k - lookback, 0)].date().isoformat(),
                    "current_counts": x[origin_k - lookback :].astype(int).tolist(),
                    "analogs": analogs,
                    "n_analogs": len(analogs),
                    "analog_mean_outcome": round(float(outcomes.mean()), 3)
                    if len(outcomes)
                    else None,
                    "analog_share_any": round(float((outcomes > 0).mean()), 3)
                    if len(outcomes)
                    else None,
                    "history_mean": round(float(hist.mean()), 3) if len(hist) else None,
                    "history_share_any": round(float((hist > 0).mean()), 3) if len(hist) else None,
                    "mean_similarity": round(float(sim.mean()), 4) if len(sim) else None,
                }
            )
    return pd.DataFrame(rows)
