"""Mann-Kendall monotonic trend test, vectorised over many series."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm


def mann_kendall(series: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (tau, z, two-sided p) for each row of ``series`` (N, T).

    Uses the tie-corrected variance and the continuity-corrected z statistic.
    """
    x = np.asarray(series, dtype=float)
    if x.ndim == 1:
        x = x[None, :]
    n = x.shape[1]
    i, j = np.triu_indices(n, k=1)
    s = np.sign(x[:, j] - x[:, i]).sum(axis=1)
    var = np.full(x.shape[0], n * (n - 1) * (2 * n + 5), dtype=float)
    rounded = np.round(x, 6)
    for r in range(x.shape[0]):
        _, t = np.unique(rounded[r], return_counts=True)
        t = t[t > 1]
        if t.size:
            var[r] -= (t * (t - 1) * (2 * t + 5)).sum()
    var /= 18.0
    z = np.zeros_like(s, dtype=float)
    pos, neg = (s > 0) & (var > 0), (s < 0) & (var > 0)
    z[pos] = (s[pos] - 1) / np.sqrt(var[pos])
    z[neg] = (s[neg] + 1) / np.sqrt(var[neg])
    p = 2.0 * norm.sf(np.abs(z))
    tau = s / (n * (n - 1) / 2)
    return tau, z, p
