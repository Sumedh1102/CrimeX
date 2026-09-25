"""Getis-Ord Gi* local hotspot statistic on the zone grid.

G*_i = (sum_j w_ij x_j - Xbar * sum_j w_ij)
       / (S * sqrt((n * sum_j w_ij^2 - (sum_j w_ij)^2) / (n - 1)))

with binary weights that include the zone itself (w_ii = 1). The statistic is a
z-score; significance is two-sided under the normal approximation.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

HOTSPOT_CLASSES = (
    ("HOT_99", 2.576),
    ("HOT_95", 1.960),
    ("HOT_90", 1.645),
)
CLASS_LABELS = {
    "HOT_99": "Hot spot (99% confidence)",
    "HOT_95": "Hot spot (95% confidence)",
    "HOT_90": "Hot spot (90% confidence)",
    "NOT_SIGNIFICANT": "Not significant",
    "COLD_90": "Cold spot (90% confidence)",
    "COLD_95": "Cold spot (95% confidence)",
    "COLD_99": "Cold spot (99% confidence)",
}


def gi_star(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Gi* z-scores. ``x`` is (Z,) or (Z, T) (one column per period); ``w`` is (Z, Z)."""
    x = np.asarray(x, dtype=float)
    squeeze = x.ndim == 1
    if squeeze:
        x = x[:, None]
    n = x.shape[0]
    xbar = x.mean(axis=0)
    s = np.sqrt(np.maximum((x**2).mean(axis=0) - xbar**2, 0.0))
    wsum = w.sum(axis=1)[:, None]
    w2sum = (w**2).sum(axis=1)[:, None]
    num = w @ x - xbar * wsum
    den_core = np.sqrt(np.maximum((n * w2sum - wsum**2) / (n - 1), 0.0))
    den = s * den_core
    z = np.divide(num, den, out=np.zeros_like(num), where=den > 0)
    return z[:, 0] if squeeze else z


def p_values(z: np.ndarray) -> np.ndarray:
    return 2.0 * norm.sf(np.abs(z))


def benjamini_hochberg(p: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """Boolean mask of discoveries under the Benjamini-Hochberg FDR procedure."""
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    thresh = alpha * (np.arange(1, len(p) + 1) / len(p))
    below = ranked <= thresh
    keep = np.zeros(len(p), dtype=bool)
    if below.any():
        cutoff = np.nonzero(below)[0].max()
        keep[order[: cutoff + 1]] = True
    return keep


def classify(z: np.ndarray, significant: np.ndarray | None = None) -> np.ndarray:
    out = np.full(z.shape, "NOT_SIGNIFICANT", dtype=object)
    for label, cut in reversed(HOTSPOT_CLASSES):
        out[z >= cut] = label
        out[z <= -cut] = label.replace("HOT", "COLD")
    if significant is not None:
        out[~significant] = "NOT_SIGNIFICANT"
    return out
