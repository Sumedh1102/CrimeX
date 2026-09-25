"""Pydantic request/response models for the v1 API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RiskBand = Literal["LOW", "MODERATE", "ELEVATED", "HIGH", "VERY HIGH"]
HotspotState = Literal["EMERGING", "ACTIVE", "PERSISTENT", "DECLINING", "SPORADIC", "STABLE"]
Confidence = Literal["LOW", "MEDIUM", "HIGH"]


class Open(BaseModel):
    """Response with a documented core and additional descriptive fields."""

    model_config = ConfigDict(extra="allow")


class Versions(BaseModel):
    model_version: str
    training_dataset_version: str
    input_dataset_version: str
    feature_version: str
    generated_at: str


class Window(BaseModel):
    start: str
    end: str
    days: int
    label: str


class Health(BaseModel):
    status: Literal["ok", "not_ready"]
    detail: str | None = None
    versions: Versions | None = None


class Meta(Open):
    data_label: str
    is_synthetic: bool
    limitation_statement: str
    as_of: str
    forecast_window: Window
    event_definition: str
    bands: list[dict[str, Any]]
    crime_types: list[dict[str, Any]]
    risk_bands: list[dict[str, Any]]
    affinity_bands: list[dict[str, Any]]
    hotspot_states: list[dict[str, Any]]
    versions: Versions


class RiskLayerItem(BaseModel):
    zone_id: str
    crime_type: str
    band: str
    final_risk: float = Field(description="Blended score 0-100 (not a probability)")
    risk_band: RiskBand
    crs: float = Field(description="Explainable Crime Risk Score 0-100 (not a probability)")
    crs_band: RiskBand
    probability: float = Field(description="Calibrated probability of the defined event")
    confidence: Confidence
    expected_count: float
    hotspot_state: HotspotState
    cai: float
    affinity_band: str


class RiskLayer(Open):
    crime_type: str
    band: str
    window: Window
    items: list[RiskLayerItem]
    versions: Versions


class HotspotItem(BaseModel):
    zone_id: str
    count: int
    density_per_km2: float
    gi_z: float
    gi_p: float
    hotspot_class: str


class HotspotsResponse(Open):
    crime_type: str
    band: str
    period: str
    start: str
    end: str
    method: str
    items: list[HotspotItem]


class StateItem(Open):
    zone_id: str
    crime_type: str
    state: HotspotState
    hot_periods: int
    n_periods: int
    recent_hot_periods: int
    trend: str


class StatesResponse(Open):
    crime_type: str
    items: list[StateItem]
    summary: dict[str, int]
    top_emerging: list[dict[str, Any]]


class AffinityItem(BaseModel):
    zone_id: str
    crime_type: str
    cai: float
    affinity_band: str
    a_spatial: float
    a_recency: float
    a_recurrence: float
    a_consistency: float
    location_quotient: float
    incidents_52w: int


class AffinityResponse(Open):
    crime_type: str
    items: list[AffinityItem]


class AnomaliesResponse(Open):
    crime_type: str
    method: str
    alerts: list[dict[str, Any]]
    items: list[dict[str, Any]]


class PredictRequest(BaseModel):
    zone_id: str = Field(examples=["Z120"])
    crime_type: str = Field(examples=["ROBBERY_CHAIN_SNATCHING"])
    window: str = Field(default="7d", examples=["7d"])
    band: str | None = Field(default=None, examples=["EVENING"])


class PredictResponse(Open):
    zone_id: str
    crime_type: str
    band: str
    prediction_window: Window
    risk_score: float = Field(description="Blended score 0-100 (not a probability)")
    risk_band: RiskBand
    crs: float
    probability: float
    confidence: Confidence
    status: str
    drivers: list[str]
    event_definition: str
    versions: Versions
    limitation_statement: str


class ZoneDetail(Open):
    zone: dict[str, Any]
    crime_type: str
    band: str
    window: Window
    prediction: dict[str, Any]
    hotspot_state: dict[str, Any]
    versions: Versions
    data_label: str
    limitation_statement: str


class Dashboard(Open):
    kpis: dict[str, int]
    kpi_definitions: dict[str, str]
    top_emerging: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    versions: Versions
