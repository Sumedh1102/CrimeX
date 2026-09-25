"""Formula handbook implementations. All inputs are numpy-broadcastable.

Three numbers are kept distinct everywhere:

* CAI (0-100): historical association of a zone with a crime type (statistical, not causal).
* CRS (0-100): normalised composite risk indicator. **Not a probability.**
* Calibrated probability: only from the calibrated classifier, for a defined event.

The blended score combines the calibrated probability with the explainable score; it is
also a score, not a probability.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

CAI_COMPONENTS = ("spatial", "recency", "recurrence", "consistency")
CRS_COMPONENTS = ("F", "R", "T", "A", "S", "P", "X")


def _check_unit(name: str, x: np.ndarray) -> None:
    if np.any((x < -1e-9) | (x > 1 + 1e-9)):
        raise ValueError(f"Component {name} must be normalised to [0, 1]")


def location_quotient(N_zc, N_z, N_c, N) -> np.ndarray:
    """LQ = (N_zc / N_z) / (N_c / N); 0 where a denominator is 0."""
    N_zc, N_z, N_c, N = (np.asarray(a, dtype=float) for a in (N_zc, N_z, N_c, N))
    with np.errstate(divide="ignore", invalid="ignore"):
        share_zone = np.where(N_z > 0, N_zc / N_z, 0.0)
        share_city = np.where(N > 0, N_c / N, 0.0)
        lq = np.where(share_city > 0, share_zone / share_city, 0.0)
    return lq


def spatial_affinity(lq, lq_cap: float) -> np.ndarray:
    """A_spatial = log(1 + min(LQ, cap)) / log(1 + cap)."""
    return np.log1p(np.minimum(np.asarray(lq, dtype=float), lq_cap)) / np.log1p(lq_cap)


def consistency(period_counts: np.ndarray, eps: float, axis: int = 0) -> np.ndarray:
    """A_consistency = clip(1 - sigma / (mu + eps), 0, 1); 0 when there are no incidents."""
    mu = period_counts.mean(axis=axis)
    sigma = period_counts.std(axis=axis)
    out = np.clip(1.0 - sigma / (mu + eps), 0.0, 1.0)
    return np.where(period_counts.sum(axis=axis) > 0, out, 0.0)


def cai_score(
    a_spatial, a_recency, a_recurrence, a_consistency, weights: Mapping[str, float]
) -> np.ndarray:
    parts = {
        "spatial": np.asarray(a_spatial, dtype=float),
        "recency": np.asarray(a_recency, dtype=float),
        "recurrence": np.asarray(a_recurrence, dtype=float),
        "consistency": np.asarray(a_consistency, dtype=float),
    }
    total = 0.0
    for name in CAI_COMPONENTS:
        _check_unit(name, parts[name])
        total = total + weights[name] * parts[name]
    return 100.0 * total


def recency_component(days_since, half_life_days) -> np.ndarray:
    """R = exp(-lambda * d), lambda = ln 2 / half-life; 0 when there was no prior incident."""
    d = np.asarray(days_since, dtype=float)
    lam = np.log(2.0) / np.asarray(half_life_days, dtype=float)
    with np.errstate(over="ignore", invalid="ignore"):
        r = np.exp(-lam * d)
    return np.where(np.isfinite(d), r, 0.0)


def trend_component(ratio, k: float, b: float) -> np.ndarray:
    """T = sigmoid(k * (ratio - b)) with ratio = (C_recent - C_baseline) / (C_baseline + eps)."""
    return 1.0 / (1.0 + np.exp(-k * (np.asarray(ratio, dtype=float) - b)))


def anomaly_component(z, z_cap: float) -> np.ndarray:
    """X = min(1, max(0, z) / z_cap)."""
    return np.minimum(1.0, np.maximum(0.0, np.asarray(z, dtype=float)) / z_cap)


def crs_score(components: Mapping[str, np.ndarray], weights: Mapping[str, float]) -> np.ndarray:
    """CRS = 100 * sum_k w_k * component_k over F, R, T, A, S, P, X (each in [0, 1])."""
    total = 0.0
    for name in CRS_COMPONENTS:
        x = np.asarray(components[name], dtype=float)
        _check_unit(name, x)
        total = total + weights[name] * x
    return 100.0 * total


def crs_contributions(
    components: Mapping[str, np.ndarray], weights: Mapping[str, float]
) -> dict[str, np.ndarray]:
    """Points each component adds to the CRS (they sum exactly to the CRS)."""
    return {k: 100.0 * weights[k] * np.asarray(components[k], dtype=float) for k in CRS_COMPONENTS}


def blended_risk(p_ml, r_explainable, ml_weight: float) -> np.ndarray:
    """FinalRisk = 100 * (w * P_ML + (1 - w) * R_explainable). A score, not a probability."""
    p = np.asarray(p_ml, dtype=float)
    r = np.asarray(r_explainable, dtype=float)
    _check_unit("P_ML", p)
    _check_unit("R_explainable", r)
    return 100.0 * (ml_weight * p + (1.0 - ml_weight) * r)
