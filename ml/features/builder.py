"""Flatten the component panel into a model matrix for selected origins.

Rows are ordered (origin, zone, crime type, band), i.e. ``np.ravel`` of an array shaped
(len(ks), Z, C, B). ``row_keys`` returns the matching index arrays.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ml.config import ScoringConfig
from ml.features.engine import ComponentPanel, FittedScoringState, finalise_components
from ml.features.registry import feature_names
from ml.preprocessing.grid import Grid
from ml.preprocessing.panel import CountPanel


@dataclass
class FeatureMatrix:
    X: np.ndarray  # (N, F) float32
    names: list[str]
    ks: np.ndarray  # origins included
    shape: tuple[int, int, int, int]  # (len(ks), Z, C, B)
    components: dict[str, np.ndarray]  # CRS components (Z, C, B, len(ks)) incl. "CRS"

    @property
    def n_rows(self) -> int:
        return self.X.shape[0]

    def row_keys(self) -> dict[str, np.ndarray]:
        nk, Z, C, B = self.shape
        kk, zz, cc, bb = np.meshgrid(
            self.ks, np.arange(Z), np.arange(C), np.arange(B), indexing="ij"
        )
        return {"k": kk.ravel(), "z": zz.ravel(), "c": cc.ravel(), "b": bb.ravel()}

    def flatten(self, arr_zcbk: np.ndarray) -> np.ndarray:
        """(Z, C, B, len(ks)) -> row order."""
        return np.ascontiguousarray(np.moveaxis(arr_zcbk, -1, 0)).ravel()


def targets(panel: CountPanel, ks: np.ndarray) -> np.ndarray:
    """Incident counts in each row's forecast window (row order); ks must be < W."""
    if np.any(ks >= panel.W):
        raise ValueError("The forecast window of the last origin has no observed counts")
    return np.ascontiguousarray(np.moveaxis(panel.counts[..., ks], -1, 0)).ravel()


def build_matrix(
    panel: CountPanel,
    cp: ComponentPanel,
    state: FittedScoringState,
    grid: Grid,
    s: ScoringConfig,
    ks: np.ndarray,
) -> FeatureMatrix:
    ks = np.asarray(ks, dtype=int)
    Z, C, B = len(panel.zones), len(panel.crime_types), len(panel.bands)
    nk = len(ks)
    comps = finalise_components(cp, panel, state, s, ks)
    names = feature_names(panel.crime_types, panel.bands)
    X = np.empty((nk * Z * C * B, len(names)), dtype=np.float32)
    shape4 = (Z, C, B, nk)

    def band(a):
        return a[..., ks]

    def zc(a):
        return a[:, :, None, ks]

    origins = panel.origins[ks]
    woy = origins.isocalendar().week.to_numpy().astype(float)
    city_r52_per4 = cp.city_c_r52[:, ks] * 4 / 52
    eps = s.count_epsilon
    cols = {
        "b_lag1": cp.b_lags[0][..., ks],
        "b_lag2": cp.b_lags[1][..., ks],
        "b_lag3": cp.b_lags[2][..., ks],
        "b_lag4": cp.b_lags[3][..., ks],
        "b_r8": band(cp.b_r8),
        "b_r13": band(cp.b_r13),
        "b_r26": band(cp.b_r26),
        "b_r52": band(cp.b_r52),
        "b_lag52": band(cp.b_lag52),
        "zc_lag1": zc(cp.zc_lag1),
        "zc_r4": zc(cp.zc_r4),
        "zc_r13": zc(cp.zc_r13),
        "zc_r52": zc(cp.zc_r52),
        "days_since_last": zc(np.minimum(cp.days_since, 365.0)),
        "z_r4": cp.z_r4[:, None, None, ks],
        "z_r52": cp.z_r52[:, None, None, ks],
        "nbr_b_r8": band(cp.nbr_current_b),
        "nbr_zc_r4": zc(cp.nbr_zc_r4),
        "city_c_r4": cp.city_c_r4[None, :, None, ks],
        "city_c_r52": cp.city_c_r52[None, :, None, ks],
        "city_c_trend": ((cp.city_c_r4[:, ks] - city_r52_per4) / (city_r52_per4 + eps))[
            None, :, None, :
        ],
        "F": comps["F"],
        "S": comps["S"],
        "T": comps["T"],
        "T_ratio": zc(cp.T_ratio),
        "P": comps["P"],
        "X": comps["X"],
        "anomaly_z": zc(cp.anomaly_z),
        "A": comps["A"],
        "a_spatial": zc(cp.a_spatial),
        "a_recency": zc(cp.a_recency),
        "a_recurrence": zc(cp.a_recurrence),
        "a_consistency": zc(cp.a_consistency),
        "lq": zc(np.minimum(cp.lq, s.lq_cap)),
        "woy_sin": np.sin(2 * np.pi * woy / 52.18)[None, None, None, :],
        "woy_cos": np.cos(2 * np.pi * woy / 52.18)[None, None, None, :],
        "month": origins.month.to_numpy()[None, None, None, :],
        "zone_row": (grid.rows / max(grid.n_rows - 1, 1))[:, None, None, None],
        "zone_col": (grid.cols / max(grid.n_cols - 1, 1))[:, None, None, None],
    }
    eye_c = np.eye(C, dtype=np.float32)
    eye_b = np.eye(B, dtype=np.float32)
    for i, c in enumerate(panel.crime_types):
        cols[f"crime_{c}"] = eye_c[i][None, :, None, None]
    for i, b in enumerate(panel.bands):
        cols[f"band_{b}"] = eye_b[i][None, None, :, None]

    for j, name in enumerate(names):
        full = np.broadcast_to(np.asarray(cols[name], dtype=np.float32), shape4)
        X[:, j] = np.moveaxis(full, -1, 0).ravel()
    return FeatureMatrix(X=X, names=names, ks=ks, shape=(nk, Z, C, B), components=comps)
