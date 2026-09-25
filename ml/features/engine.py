"""Compute every explainable component and count feature for every origin at once.

Shapes: Z zones, C crime types, B time bands, K = W + 1 origins. Band-level arrays are
(Z, C, B, K); zone-crime arrays are (Z, C, K) and apply to every band of that zone and
crime type. Everything at origin k is computed from windows < k only.

Components that need fitted state (percentile references for F and S, tuned recency
half-lives for R) are finalised by :func:`finalise_components`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ml.config import ScoringConfig
from ml.features.percentile import PercentileReference
from ml.features.rolling import (
    cumsum0,
    trailing_exp_weighted,
    trailing_mean_std,
    trailing_sum,
)
from ml.preprocessing.grid import Grid
from ml.preprocessing.panel import CountPanel
from ml.scoring.formulas import (
    anomaly_component,
    consistency,
    crs_score,
    location_quotient,
    recency_component,
    spatial_affinity,
    trend_component,
)


@dataclass
class Windows:
    """Scoring windows converted from weeks to panel windows."""

    frequency: int
    trend_recent: int
    baseline: int
    anomaly_history: int
    affinity: int
    affinity_period: int
    seasonal_lag: int

    @classmethod
    def from_config(cls, s: ScoringConfig, window_days: int) -> Windows:
        def w(weeks: int) -> int:
            return max(1, round(weeks * 7 / window_days))

        return cls(
            frequency=w(s.frequency_window_weeks),
            trend_recent=w(s.trend_recent_weeks),
            baseline=w(s.baseline_weeks),
            anomaly_history=w(s.anomaly_history_weeks),
            affinity=w(s.affinity_window_weeks),
            affinity_period=w(s.affinity_period_weeks),
            seasonal_lag=w(52),
        )

    @property
    def required_history(self) -> int:
        return max(
            self.baseline + self.trend_recent,
            self.anomaly_history + 1,
            self.affinity,
            self.frequency,
            self.seasonal_lag,
        )


@dataclass
class ComponentPanel:
    windows: Windows
    # band level (Z, C, B, K)
    b_lags: np.ndarray  # (4, Z, C, B, K) counts in windows k-1 .. k-4
    b_r8: np.ndarray
    b_r13: np.ndarray
    b_r26: np.ndarray
    b_r52: np.ndarray
    b_lag52: np.ndarray
    current_b: np.ndarray  # frequency-window count (F numerator)
    city_mean_current_b: np.ndarray  # (1, C, B, K) cross-sectional mean of current_b
    F_raw: np.ndarray
    nbr_current_b: np.ndarray  # inverse-distance weighted neighbour mean of current_b
    S_raw: np.ndarray
    P: np.ndarray
    band_share: np.ndarray  # smoothed share of the zone-crime's incidents in each band
    # zone-crime level (Z, C, K)
    zc_lag1: np.ndarray
    zc_r4: np.ndarray
    zc_r13: np.ndarray
    zc_r52: np.ndarray
    trend_recent: np.ndarray
    trend_baseline: np.ndarray
    T_ratio: np.ndarray
    T: np.ndarray
    anomaly_current: np.ndarray
    anomaly_mean: np.ndarray
    anomaly_std: np.ndarray
    anomaly_z: np.ndarray
    X: np.ndarray
    days_since: np.ndarray
    nbr_zc_r4: np.ndarray
    lq: np.ndarray
    a_spatial: np.ndarray
    a_recency: np.ndarray
    a_recurrence: np.ndarray
    a_consistency: np.ndarray
    cai: np.ndarray
    # zone level (Z, K) and city level (C, K)
    z_r4: np.ndarray
    z_r52: np.ndarray
    city_c_r4: np.ndarray
    city_c_r52: np.ndarray


def _f32(x: np.ndarray) -> np.ndarray:
    return x.astype(np.float32, copy=False)


def compute_components(panel: CountPanel, grid: Grid, s: ScoringConfig) -> ComponentPanel:
    if tuple(grid.zone_ids) != panel.zones:
        raise ValueError("Panel zones must follow the grid's zone order")
    win = Windows.from_config(s, panel.window_days)
    eps = s.count_epsilon
    counts_b = panel.counts.astype(np.float64)  # (Z, C, B, W)
    counts_zc = counts_b.sum(axis=2)  # (Z, C, W)
    cs_b = cumsum0(counts_b)
    cs_zc = cumsum0(counts_zc)
    cs_zc2 = cumsum0(counts_zc**2)
    Z, C, B = counts_b.shape[:3]

    # ---- count features
    b_lags = np.stack([trailing_sum(cs_b, 1, lag=i) for i in range(4)])
    b_r8 = trailing_sum(cs_b, 8)
    b_r13 = trailing_sum(cs_b, 13)
    b_r26 = trailing_sum(cs_b, 26)
    b_r52 = trailing_sum(cs_b, 52)
    b_lag52 = trailing_sum(cs_b, 1, lag=win.seasonal_lag - 1)
    zc_lag1 = trailing_sum(cs_zc, 1)
    zc_r4 = trailing_sum(cs_zc, 4)
    zc_r13 = trailing_sum(cs_zc, 13)
    zc_r52 = trailing_sum(cs_zc, 52)
    z_r4 = zc_r4.sum(axis=1)
    z_r52 = zc_r52.sum(axis=1)
    city_c_r4 = zc_r4.sum(axis=0) / Z
    city_c_r52 = zc_r52.sum(axis=0) / Z

    # ---- F: frequency vs the average zone (percentile-normalised later)
    current_b = trailing_sum(cs_b, win.frequency)
    city_mean = current_b.mean(axis=0, keepdims=True)
    F_raw = current_b / (city_mean + eps)

    # ---- S: inverse-distance weighted neighbour pressure (percentile-normalised later)
    w = grid.inverse_distance_weights(s.neighbor_radius_cells, s.neighbor_distance_epsilon_km)
    row = w.sum(axis=1, keepdims=True)
    wn = np.divide(w, row, out=np.zeros_like(w), where=row > 0)
    nbr_current_b = np.einsum("zj,jcbk->zcbk", wn, current_b)
    S_raw = nbr_current_b / (city_mean + eps)
    nbr_zc_r4 = np.einsum("zj,jck->zck", wn, zc_r4)

    # ---- T: recent windows vs the zone's own baseline (zone-crime level)
    recent = trailing_sum(cs_zc, win.trend_recent)
    base_total = trailing_sum(cs_zc, win.baseline, lag=win.trend_recent)
    baseline = base_total * win.trend_recent / win.baseline
    T_ratio = (recent - baseline) / (baseline + eps)
    T = trend_component(T_ratio, s.trend_k, s.trend_b)

    # ---- X: last window vs its own history (CSD surge z-score)
    current = trailing_sum(cs_zc, 1)
    mean, std = trailing_mean_std(cs_zc, cs_zc2, win.anomaly_history, lag=1)
    anomaly_z = (current - mean) / (std + s.anomaly_epsilon)
    X = anomaly_component(anomaly_z, s.anomaly_z_cap)

    # ---- P: cosine similarity between the zone-crime band profile and the window's band
    n_zcb = trailing_sum(cs_b, win.affinity)  # (Z, C, B, K)
    n_zc = n_zcb.sum(axis=2, keepdims=True)
    city_cb = n_zcb.sum(axis=0, keepdims=True)
    city_c = city_cb.sum(axis=2, keepdims=True)
    city_share = np.where(city_c > 0, city_cb / np.where(city_c > 0, city_c, 1), 1.0 / B)
    alpha = s.temporal_profile_prior
    band_share = (n_zcb + alpha * city_share) / (n_zc + alpha)
    P = band_share / np.linalg.norm(band_share, axis=2, keepdims=True)

    # ---- CAI (zone-crime level, trailing affinity window)
    N_zc = trailing_sum(cs_zc, win.affinity)
    N_z = N_zc.sum(axis=1, keepdims=True)
    N_c = N_zc.sum(axis=0, keepdims=True)
    N = N_zc.sum(axis=(0, 1), keepdims=True)
    lq = location_quotient(N_zc, N_z, N_c, N)
    a_spatial = spatial_affinity(lq, s.lq_cap)
    lam = np.log(2.0) / s.affinity_recency_half_life_days
    decay = float(np.exp(-lam * panel.window_days))
    weighted = trailing_exp_weighted(counts_zc, win.affinity, decay)
    a_recency = np.divide(weighted, N_zc, out=np.zeros_like(weighted), where=N_zc > 0)
    n_periods = max(1, win.affinity // win.affinity_period)
    periods = np.stack(
        [
            trailing_sum(cs_zc, win.affinity_period, lag=j * win.affinity_period)
            for j in range(n_periods)
        ]
    )
    a_recurrence = (periods > 0).mean(axis=0)
    a_consistency = consistency(periods, s.consistency_epsilon, axis=0)
    wts = s.cai_weights
    cai = 100.0 * (
        wts["spatial"] * a_spatial
        + wts["recency"] * a_recency
        + wts["recurrence"] * a_recurrence
        + wts["consistency"] * a_consistency
    )

    return ComponentPanel(
        windows=win,
        b_lags=_f32(b_lags),
        b_r8=_f32(b_r8),
        b_r13=_f32(b_r13),
        b_r26=_f32(b_r26),
        b_r52=_f32(b_r52),
        b_lag52=_f32(b_lag52),
        current_b=_f32(current_b),
        city_mean_current_b=_f32(city_mean),
        F_raw=_f32(F_raw),
        nbr_current_b=_f32(nbr_current_b),
        S_raw=_f32(S_raw),
        P=_f32(P),
        band_share=_f32(band_share),
        zc_lag1=_f32(zc_lag1),
        zc_r4=_f32(zc_r4),
        zc_r13=_f32(zc_r13),
        zc_r52=_f32(zc_r52),
        trend_recent=_f32(recent),
        trend_baseline=_f32(baseline),
        T_ratio=_f32(T_ratio),
        T=_f32(T),
        anomaly_current=_f32(current),
        anomaly_mean=_f32(mean),
        anomaly_std=_f32(std),
        anomaly_z=_f32(anomaly_z),
        X=_f32(X),
        days_since=panel.days_since_last.astype(np.float32),
        nbr_zc_r4=_f32(nbr_zc_r4),
        lq=_f32(lq),
        a_spatial=_f32(a_spatial),
        a_recency=_f32(a_recency),
        a_recurrence=_f32(a_recurrence),
        a_consistency=_f32(a_consistency),
        cai=_f32(cai),
        z_r4=_f32(z_r4),
        z_r52=_f32(z_r52),
        city_c_r4=_f32(city_c_r4),
        city_c_r52=_f32(city_c_r52),
    )


@dataclass
class FittedScoringState:
    """Everything learned on training/validation data that the CRS needs at inference."""

    reference: PercentileReference
    recency_half_life_days: dict[str, float]

    def to_json(self) -> dict:
        return {
            "percentile_reference": self.reference.to_json(),
            "recency_half_life_days": self.recency_half_life_days,
        }

    @classmethod
    def from_json(cls, data: dict) -> FittedScoringState:
        return cls(
            reference=PercentileReference.from_json(data["percentile_reference"]),
            recency_half_life_days={k: float(v) for k, v in data["recency_half_life_days"].items()},
        )


def fit_reference(
    cp: ComponentPanel, origin_mask: np.ndarray, panel: CountPanel, s: ScoringConfig
) -> PercentileReference:
    return PercentileReference.fit(
        {"F": cp.F_raw, "S": cp.S_raw},
        origin_mask,
        panel.crime_types,
        panel.bands,
        s.percentile.grid_points,
    )


def finalise_components(
    cp: ComponentPanel,
    panel: CountPanel,
    state: FittedScoringState,
    s: ScoringConfig,
    k_index: np.ndarray | slice = slice(None),
) -> dict[str, np.ndarray]:
    """All seven CRS components, band-level (Z, C, B, K_sel), plus the CRS itself."""
    ct, bands = panel.crime_types, panel.bands
    F = state.reference.transform("F", cp.F_raw[..., k_index], ct, bands)
    S = state.reference.transform("S", cp.S_raw[..., k_index], ct, bands)
    hl = np.array([state.recency_half_life_days[c] for c in ct])[None, :, None]
    R = recency_component(cp.days_since[..., k_index], hl)
    B = len(bands)

    def per_band(x: np.ndarray) -> np.ndarray:
        return np.repeat(x[:, :, None, :], B, axis=2)

    comps = {
        "F": F,
        "R": per_band(R),
        "T": per_band(cp.T[..., k_index]),
        "A": per_band(cp.cai[..., k_index] / 100.0),
        "S": S,
        "P": cp.P[..., k_index],
        "X": per_band(cp.X[..., k_index]),
    }
    comps = {k: np.clip(v, 0.0, 1.0).astype(np.float32) for k, v in comps.items()}
    comps["CRS"] = crs_score(comps, s.crs_weights).astype(np.float32)
    return comps
