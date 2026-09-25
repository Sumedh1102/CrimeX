"""TreeSHAP explanations of the XGBoost classifier.

Contributions are in log-odds of the *uncalibrated* model; they sum (with the bias) to
the raw model margin. Isotonic calibration is monotone, so the direction of every
contribution also holds for the calibrated probability.
"""

from __future__ import annotations

import numpy as np

from ml.features.registry import feature_group, feature_label


def top_contributions(
    contrib: np.ndarray,
    X: np.ndarray,
    names: list[str],
    k: int,
    crime_labels: dict[str, str],
) -> list[list[dict]]:
    """Top-k features by |SHAP| for each row. ``contrib`` excludes the bias column."""
    # one-hot indicators that are 0 describe the *other* categories; skip them
    skip = np.array([n.startswith(("crime_", "band_")) for n in names])
    mag = np.abs(contrib)
    mag[:, skip] = np.where(X[:, skip] > 0, mag[:, skip], -1)
    order = np.argsort(-mag, axis=1)[:, :k]
    out = []
    for i in range(contrib.shape[0]):
        row = []
        for j in order[i]:
            if mag[i, j] <= 0:
                continue
            row.append(
                {
                    "feature": names[j],
                    "label": feature_label(names[j], crime_labels),
                    "group": feature_group(names[j]),
                    "value": round(float(X[i, j]), 4),
                    "shap_log_odds": round(float(contrib[i, j]), 4),
                    "direction": "raises" if contrib[i, j] > 0 else "lowers",
                }
            )
        out.append(row)
    return out
