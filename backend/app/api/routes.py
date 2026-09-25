"""Versioned HTTP API (mounted at /api/v1)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.schemas.models import (
    AffinityResponse,
    AnomaliesResponse,
    Dashboard,
    Health,
    HotspotsResponse,
    Meta,
    PredictRequest,
    PredictResponse,
    RiskLayer,
    StatesResponse,
    ZoneDetail,
)
from backend.app.services import analytics as svc
from backend.app.services.store import DataStore, NotReadyError, get_store

router = APIRouter()
Store = Annotated[DataStore, Depends(get_store)]
CrimeParam = Annotated[str, Query(description="Crime type code, or ALL")]
BandParam = Annotated[str, Query(description="Time band code, or ALL")]


def _run(fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'\"")) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/health", response_model=Health, tags=["system"])
def health(store: Store) -> Health:
    try:
        store.check_ready()
        return Health(status="ok", versions=svc.versions(store))
    except NotReadyError as e:
        return Health(status="not_ready", detail=str(e))


@router.get("/meta", response_model=Meta, tags=["system"])
def meta(store: Store):
    return svc.meta(store)


@router.get("/crime-types", tags=["reference"])
def crime_types(store: Store):
    return svc.crime_types(store)


@router.get("/crime-types/{code}/profile", tags=["crime types"])
def crime_type_profile(code: str, store: Store):
    return _run(svc.crime_type_profile, store, code)


@router.get("/crime-types/{code}/fingerprint", tags=["crime types"])
def crime_type_fingerprint(code: str, store: Store):
    return _run(svc.crime_type_profile, store, code)["fingerprint"]


@router.get("/crime-types/{code}/affinity", response_model=AffinityResponse, tags=["crime types"])
def crime_type_affinity(code: str, store: Store):
    return _run(svc.affinity_layer, store, code)


@router.get("/official/summary", tags=["official statistics"])
def official_summary(store: Store):
    return svc.official_summary(store)


@router.get("/stations", tags=["reference"])
def stations(store: Store):
    return svc.stations(store)


@router.get("/zones", tags=["reference"])
def zones(store: Store):
    return svc.zones_geojson(store)


@router.get("/zones/{zone_id}", response_model=ZoneDetail, tags=["zones"])
def zone_detail(
    zone_id: str,
    store: Store,
    crime_type: Annotated[str, Query(description="Crime type code")],
    band: Annotated[str, Query(description="Time band code")],
):
    return _run(svc.zone_detail, store, zone_id, crime_type, band)


@router.get("/predictions", response_model=RiskLayer, tags=["predictions"])
def predictions(store: Store, crime_type: CrimeParam = "ALL", band: BandParam = "ALL"):
    return _run(svc.predictions_layer, store, crime_type, band)


@router.post("/predict", response_model=PredictResponse, tags=["predictions"])
def predict(req: PredictRequest, store: Store):
    return _run(svc.predict, store, req.zone_id, req.crime_type, req.window, req.band)


@router.get("/hotspots", response_model=HotspotsResponse, tags=["hotspots"])
def hotspots(
    store: Store,
    crime_type: CrimeParam = "ALL",
    period: Annotated[str, Query(description="24h, 7d, 30d, 90d, 6m, 1y or custom")] = "90d",
    start: Annotated[str | None, Query(description="custom start (YYYY-MM-DD)")] = None,
    end: Annotated[str | None, Query(description="custom end, inclusive (YYYY-MM-DD)")] = None,
    band: BandParam = "ALL",
):
    return _run(svc.hotspots, store, crime_type, period, start, end, band)


@router.get("/emerging-hotspots", response_model=StatesResponse, tags=["hotspots"])
def emerging_hotspots(store: Store, crime_type: CrimeParam = "ALL"):
    return _run(svc.hotspot_states, store, crime_type)


@router.get("/affinity", response_model=AffinityResponse, tags=["hotspots"])
def affinity(store: Store, crime_type: CrimeParam = "ALL"):
    return _run(svc.affinity_layer, store, crime_type)


@router.get("/anomalies", response_model=AnomaliesResponse, tags=["hotspots"])
def anomalies(store: Store, crime_type: CrimeParam = "ALL"):
    return _run(svc.anomalies, store, crime_type)


@router.get("/dashboard/summary", response_model=Dashboard, tags=["dashboard"])
def dashboard(
    store: Store,
    crime_type: CrimeParam = "ALL",
    station_id: Annotated[str | None, Query(description="Restrict to one station")] = None,
):
    return _run(svc.dashboard_summary, store, crime_type, station_id)


@router.get("/model", tags=["model"])
def model(store: Store):
    return svc.model_card(store)


@router.get("/data-quality", tags=["data"])
def data_quality(store: Store):
    return svc.data_quality(store)


@router.get("/incidents", tags=["data"])
def incidents(
    store: Store,
    zone_id: str | None = None,
    crime_type: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    return _run(svc.incidents, store, zone_id, crime_type, start, end, limit)
