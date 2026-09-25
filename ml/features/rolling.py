"""Leak-safe trailing-window operations on the window axis (last axis).

All functions return one value per *origin* ``k = 0..W`` computed only from windows
``< k`` (optionally skipping the most recent ``lag`` windows). Windows before the start
of the panel are treated as absent; ``effective_length`` reports how many windows were
actually available so partial histories can be excluded from training.
"""

from __future__ import annotations

import numpy as np


def cumsum0(x: np.ndarray) -> np.ndarray:
    """Cumulative sum along the last axis with a leading zero: out[..., k] = sum(x[..., :k])."""
    pad = np.zeros(x.shape[:-1] + (1,), dtype=np.float64)
    return np.concatenate([pad, np.cumsum(x, axis=-1, dtype=np.float64)], axis=-1)


def _bounds(K: int, length: int, lag: int) -> tuple[np.ndarray, np.ndarray]:
    k = np.arange(K)
    hi = np.clip(k - lag, 0, None)
    lo = np.clip(k - lag - length, 0, None)
    return lo, hi


def trailing_sum(cs: np.ndarray, length: int, lag: int = 0) -> np.ndarray:
    """Sum of windows [k - lag - length, k - lag) for every origin k (``cs`` from cumsum0)."""
    lo, hi = _bounds(cs.shape[-1], length, lag)
    return cs[..., hi] - cs[..., lo]


def effective_length(K: int, length: int, lag: int = 0) -> np.ndarray:
    lo, hi = _bounds(K, length, lag)
    return hi - lo


def trailing_mean_std(
    cs1: np.ndarray, cs2: np.ndarray, length: int, lag: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """Mean and population std over windows [k - lag - length, k - lag)."""
    n = effective_length(cs1.shape[-1], length, lag).astype(np.float64)
    n_safe = np.where(n > 0, n, 1.0)
    s1 = trailing_sum(cs1, length, lag)
    s2 = trailing_sum(cs2, length, lag)
    mean = s1 / n_safe
    var = np.maximum(s2 / n_safe - mean**2, 0.0)
    return mean, np.sqrt(var)


def trailing_exp_weighted(x: np.ndarray, length: int, decay_per_window: float) -> np.ndarray:
    """sum_{L=1..length} x[k - L] * decay^(L - 0.5) for every origin k.

    Uses the recursion D[k] = decay * (x[k-1] + D[k-1]) and truncates at ``length``.
    """
    K = x.shape[-1] + 1
    D = np.zeros(x.shape[:-1] + (K,), dtype=np.float64)
    for k in range(1, K):
        D[..., k] = decay_per_window * (x[..., k - 1] + D[..., k - 1])
    out = D.copy()
    tail = decay_per_window**length
    out[..., length:] -= tail * D[..., : K - length]
    return out / np.sqrt(decay_per_window)
