"""Versioned HTTP API (mounted at /api/v1)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

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
from backend.app.services import intelligence as intel
from backend.app.services import reports
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


@router.get("/stations/overview", tags=["stations"])
def stations_overview(store: Store):
    return _run(intel.station_overview, store)


@router.get("/stations/{station_id}", tags=["stations"])
def station_detail(station_id: str, store: Store, band: BandParam = "ALL"):
    return _run(intel.station_detail, store, station_id, band)


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


@router.get("/zones/{zone_id}/lifecycle", tags=["zones"])
def zone_lifecycle(
    zone_id: str, store: Store, crime_type: Annotated[str, Query(description="Crime type code")]
):
    return _run(intel.zone_lifecycle, store, zone_id, crime_type)


@router.get("/zones/{zone_id}/patterns", tags=["zones"])
def zone_patterns(
    zone_id: str, store: Store, crime_type: Annotated[str, Query(description="Crime type code")]
):
    return _run(intel.zone_patterns, store, zone_id, crime_type)


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


@router.get("/hotspot-lifecycle", tags=["hotspots"])
def hotspot_lifecycle(store: Store, crime_type: CrimeParam = "ALL"):
    return _run(intel.lifecycle_overview, store, crime_type)


@router.get("/hotspot-movement", tags=["hotspots"])
def hotspot_movement(
    store: Store,
    crime_type: CrimeParam = "ALL",
    step: Annotated[int | None, Query(description="Lifecycle step; default latest")] = None,
):
    return _run(intel.movement, store, crime_type, step)


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


@router.get("/reports/stations/{station_id}", response_class=HTMLResponse, tags=["reports"])
def station_report(station_id: str, store: Store):
    return HTMLResponse(_run(reports.station_report, store, station_id))


@router.get("/reports/zones/{zone_id}", response_class=HTMLResponse, tags=["reports"])
def zone_report(
    zone_id: str,
    store: Store,
    crime_type: Annotated[str, Query(description="Crime type code")],
    band: Annotated[str, Query(description="Time band code")],
):
    return HTMLResponse(_run(reports.zone_report, store, zone_id, crime_type, band))
