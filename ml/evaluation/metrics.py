"""Evaluation metrics. Accuracy alone is never reported.

* Probabilities: PR-AUC, ROC-AUC, Brier score, log loss, expected calibration error,
  reliability table, and precision / recall / F1 at a threshold chosen on validation.
* Scores that are not probabilities (CRS, blended): ranking metrics only.
* Counts: MAE, RMSE, Poisson deviance.
* Hotspot capture: share of incidents falling in the top-K ranked zones of each
  (window, crime type, band), plus the predictive accuracy index (PAI).
"""

from __future__ import annotations

import math

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)


def _r(x: float, n: int = 5) -> float:
    return float(round(float(x), n))


def reliability_table(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> list[dict]:
    """Quantile-binned reliability: mean predicted vs observed frequency per bin."""
    order = np.argsort(p, kind="stable")
    bins = np.array_split(order, n_bins)
    out = []
    for b in bins:
        if len(b) == 0:
            continue
        out.append(
            {
                "mean_predicted": _r(p[b].mean()),
                "observed_rate": _r(y[b].mean()),
                "n": int(len(b)),
                "p_min": _r(p[b].min()),
                "p_max": _r(p[b].max()),
            }
        )
    return out


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> float:
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    ece = 0.0
    for i in range(n_bins):
        m = idx == i
        if m.any():
            ece += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(ece)


def best_f1_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """Threshold maximising F1 (chosen on validation, then applied unchanged to test)."""
    qs = np.unique(np.quantile(p, np.linspace(0.5, 0.999, 120)))
    best_t, best_f = 0.5, -1.0
    for t in qs:
        _, _, f, _ = precision_recall_fscore_support(y, p >= t, average="binary", zero_division=0)
        if f > best_f:
            best_t, best_f = float(t), float(f)
    return best_t


def probability_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    y = y.astype(int)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y, p >= threshold, average="binary", zero_division=0
    )
    return {
        "pr_auc": _r(average_precision_score(y, p)),
        "roc_auc": _r(roc_auc_score(y, p)),
        "brier": _r(brier_score_loss(y, p), 6),
        "log_loss": _r(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1])),
        "ece": _r(expected_calibration_error(y, p), 6),
        "threshold": _r(threshold, 6),
        "precision": _r(prec),
        "recall": _r(rec),
        "f1": _r(f1),
        "base_rate": _r(y.mean(), 6),
        "mean_predicted": _r(p.mean(), 6),
    }


def ranking_metrics(y: np.ndarray, score: np.ndarray) -> dict:
    y = y.astype(int)
    return {
        "pr_auc": _r(average_precision_score(y, score)),
        "roc_auc": _r(roc_auc_score(y, score)),
    }


def count_metrics(y_count: np.ndarray, mu: np.ndarray) -> dict:
    y = y_count.astype(float)
    mu = np.clip(mu.astype(float), 1e-9, None)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(y > 0, y * np.log(y / mu), 0.0)
    return {
        "mae": _r(np.abs(y - mu).mean(), 6),
        "rmse": _r(math.sqrt(((y - mu) ** 2).mean()), 6),
        "poisson_deviance": _r(2 * (term - (y - mu)).mean(), 6),
    }


def top_k_capture(
    score: np.ndarray, y_count: np.ndarray, shape: tuple[int, int, int, int], k_frac: float
) -> dict:
    """Share of incidents in the top-K zones by score, per (window, crime type, band).

    ``score`` and ``y_count`` are in row order of an array shaped (n_origins, Z, C, B).
    """
    nk, Z, C, B = shape
    s = score.reshape(nk, Z, C, B)
    y = y_count.reshape(nk, Z, C, B).astype(float)
    k = max(1, math.ceil(k_frac * Z))
    top = np.argpartition(-s, k - 1, axis=1)[:, :k]
    captured = np.take_along_axis(y, top, axis=1).sum()
    oracle_top = np.argpartition(-y, k - 1, axis=1)[:, :k]
    oracle = np.take_along_axis(y, oracle_top, axis=1).sum()
    total = y.sum()
    capture = captured / total if total else 0.0
    per_type = {}
    for c in range(C):
        tot_c = y[:, :, c].sum()
        cap_c = np.take_along_axis(y[:, :, c], top[:, :, c], axis=1).sum()
        per_type[c] = _r(cap_c / tot_c if tot_c else 0.0)
    return {
        "k_zones": int(k),
        "k_fraction": _r(k / Z),
        "capture_rate": _r(capture),
        "oracle_capture_rate": _r(oracle / total if total else 0.0),
        "pai": _r(capture / (k / Z)),
        "per_crime_type": per_type,
    }
