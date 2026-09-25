"""Typed platform configuration (loaded from ``configs/default.yaml``).

Every tunable number in the platform (grid size, time bands, score weights, display
bands, model hyper-parameters, synthetic-generator assumptions) lives here so it can
be reviewed, versioned, and changed without touching code.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "default.yaml"

SYNTHETIC_SOURCE = "SYNTHETIC_DEMO"
SYNTHETIC_LABEL = "SYNTHETIC / DEMONSTRATION DATA"
LIMITATION_STATEMENT = (
    "Predictions represent statistical patterns in historical reported incident data and "
    "are intended for analytical decision support. They are not guarantees of future "
    "criminal activity."
)


class BBox(BaseModel):
    south: float
    north: float
    west: float
    east: float


class RegionConfig(BaseModel):
    name: str
    description: str
    bbox: BBox
    # [lon, lat] vertices of an approximate clip outline (not an official boundary).
    outline: list[tuple[float, float]]
    min_land_fraction: float = 0.5
    # Approximate areas with little built-up activity (used only by the synthetic generator).
    low_activity_areas: list[list[tuple[float, float]]] = Field(default_factory=list)


class GridConfig(BaseModel):
    cell_size_m: float = 1500.0
    samples_per_axis: int = 5  # land-fraction sampling inside each cell


class TimeBand(BaseModel):
    code: str
    label: str
    start_hour: int
    end_hour: int  # exclusive; 24 means midnight

    @model_validator(mode="after")
    def _check(self) -> TimeBand:
        if not (0 <= self.start_hour < self.end_hour <= 24):
            raise ValueError(f"Invalid band hours for {self.code}")
        return self

    @property
    def hours(self) -> list[int]:
        return list(range(self.start_hour, self.end_hour))


class TimeConfig(BaseModel):
    bands: list[TimeBand]
    window_days: int = 7
    # Forecast origin. The latest window starts here; history is everything before it.
    as_of: date

    @model_validator(mode="after")
    def _bands_cover_day(self) -> TimeConfig:
        hours = sorted(h for b in self.bands for h in b.hours)
        if hours != list(range(24)):
            raise ValueError("Time bands must partition the 24 hours of the day exactly once")
        return self


class CrimeTypesConfig(BaseModel):
    """Which official heads are modelled spatially (the rest stay official-stats only)."""

    modelled: list[str]
    not_modelled: dict[str, str]  # code -> reason
    # Project-defined ordinal severity (1-5). NOT from the official statement.
    severity: dict[str, int]
    # Hour windows implied by the official head definition (e.g. H.B.T. Day vs Night).
    allowed_hours: dict[str, tuple[int, int]] = Field(default_factory=dict)


class CrimeProfile(BaseModel):
    """Synthetic-generator assumptions for one crime type (never used by analytics)."""

    hour_peaks: list[tuple[float, float, float]]  # (hour, width_hours, weight)
    weekday_weights: list[float]  # Monday..Sunday
    land_use_affinity: dict[str, float]


class HotspotCounts(BaseModel):
    persistent_per_type: int = 1
    persistent_extra: int = 3
    seasonal: int = 4
    emerging: int = 6
    declining: int = 5


class SyntheticConfig(BaseModel):
    seed: int = 20260901
    start_date: date
    end_date: date
    n_stations: int = 12
    land_uses: list[str]
    profiles: dict[str, CrimeProfile]
    activity_sigma: float = 0.8
    field_smoothing_cells: float = 2.0
    low_activity_multiplier: float = 0.08
    noise_share: float = 0.06
    hotspots: HotspotCounts = HotspotCounts()
    hotspot_share_range: tuple[float, float] = (0.025, 0.05)
    hotspot_spill: float = 0.3
    rarity_boost_max: float = 3.0
    emerging_onset_weeks_before_end: tuple[int, int] = (8, 22)
    emerging_ramp_weeks: tuple[int, int] = (4, 10)
    declining_start_range: tuple[date, date]
    declining_half_life_weeks: tuple[int, int] = (6, 16)
    seasonal_duration_weeks: tuple[int, int] = (6, 10)
    n_anomalies: int = 30
    n_recent_anomalies: int = 4
    anomaly_days: tuple[int, int] = (5, 12)
    anomaly_multiplier: tuple[float, float] = (5.0, 9.0)
    anomaly_min_daily: float = 0.35
    hotspot_time_signature_share: float = 0.6
    # Injected record-level defects so the data-quality monitor has something to find.
    defect_rates: dict[str, float] = Field(default_factory=dict)


class PercentileRef(BaseModel):
    grid_points: int = 2001


class ScoringConfig(BaseModel):
    cai_weights: dict[str, float] = {
        "spatial": 0.45,
        "recency": 0.20,
        "recurrence": 0.20,
        "consistency": 0.15,
    }
    crs_weights: dict[str, float] = {
        "F": 0.20,
        "R": 0.15,
        "T": 0.15,
        "A": 0.20,
        "S": 0.10,
        "P": 0.10,
        "X": 0.10,
    }
    blend_ml_weight: float = 0.60
    lq_cap: float = 10.0
    count_epsilon: float = 1.0
    consistency_epsilon: float = 1e-6
    neighbor_distance_epsilon_km: float = 0.1
    neighbor_radius_cells: int = 2
    affinity_window_weeks: int = 52
    affinity_period_weeks: int = 4
    affinity_recency_half_life_days: float = 90.0
    frequency_window_weeks: int = 8
    trend_recent_weeks: int = 4
    baseline_weeks: int = 52
    trend_k: float = 3.0
    trend_b: float = 0.5
    anomaly_history_weeks: int = 52
    anomaly_z_cap: float = 3.0
    anomaly_alert_z: float = 3.0
    anomaly_alert_min_count: int = 3
    temporal_profile_prior: float = 10.0
    recency_half_life_days_default: float = 14.0
    recency_half_life_grid_days: list[float] = [3, 7, 14, 30, 60, 120]
    percentile: PercentileRef = PercentileRef()
    risk_bands: list[tuple[float, str]] = [
        (20, "LOW"),
        (40, "MODERATE"),
        (60, "ELEVATED"),
        (80, "HIGH"),
        (100, "VERY HIGH"),
    ]
    affinity_bands: list[tuple[float, str]] = [
        (20, "Very Low"),
        (40, "Low"),
        (60, "Moderate"),
        (80, "High"),
        (100, "Very High"),
    ]

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> ScoringConfig:
        for name, w in (("cai_weights", self.cai_weights), ("crs_weights", self.crs_weights)):
            if abs(sum(w.values()) - 1.0) > 1e-9:
                raise ValueError(f"{name} must sum to 1, got {sum(w.values())}")
        return self


class HotspotConfig(BaseModel):
    gi_neighbor_radius_cells: int = 1
    fdr_correction: bool = False
    period_weeks: int = 4
    n_periods: int = 26
    recent_periods: int = 3
    hot_z: float = 1.96
    trend_alpha: float = 0.05
    persistent_min_fraction: float = 0.8
    declining_min_early_fraction: float = 0.5
    emerging_max_prior_fraction: float = 0.15
    sporadic_min_hot_periods: int = 2


class SplitConfig(BaseModel):
    train_end: date
    validation_end: date


class XGBParams(BaseModel):
    n_estimators: int = 400
    learning_rate: float = 0.05
    max_depth: int = 6
    min_child_weight: float = 5.0
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_lambda: float = 1.0
    tree_method: str = "hist"
    n_jobs: int = 0  # 0 = all cores


class RFParams(BaseModel):
    n_estimators: int = 150
    max_depth: int = 14
    min_samples_leaf: int = 20
    max_train_rows: int = 400_000


class TrainingConfig(BaseModel):
    splits: SplitConfig
    min_history_weeks: int = 52
    xgb: XGBParams = XGBParams()
    rf: RFParams = RFParams()
    top_k_fraction: float = 0.10
    calibration: Literal["isotonic"] = "isotonic"
    shap_top_k: int = 6


class PathsConfig(BaseModel):
    data_dir: Path = Path("data")
    artifacts_dir: Path = Path("artifacts")
    official_statement: Path = Path("data/official/mumbai_police_statement_2026-08.json")

    def resolve(self, root: Path = REPO_ROOT) -> PathsConfig:
        def r(p: Path) -> Path:
            return p if p.is_absolute() else root / p

        return PathsConfig(
            data_dir=r(self.data_dir),
            artifacts_dir=r(self.artifacts_dir),
            official_statement=r(self.official_statement),
        )

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw" / "synthetic"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


class PlatformConfig(BaseModel):
    region: RegionConfig
    grid: GridConfig = GridConfig()
    time: TimeConfig
    crime_types: CrimeTypesConfig
    synthetic: SyntheticConfig
    scoring: ScoringConfig = ScoringConfig()
    hotspots: HotspotConfig = HotspotConfig()
    training: TrainingConfig
    paths: PathsConfig = PathsConfig()

    def fingerprint(self, *sections: str) -> str:
        """Stable short hash of the given config sections (for version strings)."""
        payload = {s: getattr(self, s).model_dump(mode="json") for s in sections}
        blob = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:10]


def load_config(path: str | Path | None = None, **overrides) -> PlatformConfig:
    path = Path(path) if path else DEFAULT_CONFIG_PATH
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    for dotted, value in overrides.items():
        node = raw
        *parents, leaf = dotted.split("__")
        for p in parents:
            node = node.setdefault(p, {})
        node[leaf] = value
    cfg = PlatformConfig.model_validate(raw)
    cfg.paths = cfg.paths.resolve()
    return cfg
