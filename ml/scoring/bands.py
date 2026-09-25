"""Display bands: configurable presentation values, not scientific thresholds.

Bands are defined by inclusive upper bounds, e.g. ``[(20, "LOW"), (40, "MODERATE"), ...]``
means 0-20 LOW, >20-40 MODERATE, ... Scores are rounded to one decimal before banding
so the displayed number and its band always agree.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def round_score(score) -> np.ndarray:
    return np.round(np.asarray(score, dtype=float), 1)


def assign_bands(score, bands: Sequence[tuple[float, str]]) -> np.ndarray:
    uppers = np.array([u for u, _ in bands], dtype=float)
    labels = np.array([lbl for _, lbl in bands], dtype=object)
    s = round_score(score)
    idx = np.searchsorted(uppers, s, side="left")
    return labels[np.clip(idx, 0, len(labels) - 1)]


def band_table(bands: Sequence[tuple[float, str]]) -> list[dict[str, float | str]]:
    """Bands as ``[{label, min, max}]`` for legends (min exclusive except the first)."""
    out = []
    lo = 0.0
    for upper, label in bands:
        out.append({"label": label, "min": lo, "max": float(upper)})
        lo = float(upper)
    return out
