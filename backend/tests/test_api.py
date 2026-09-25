from __future__ import annotations

import pytest

from backend.app.services.store import DataStore, set_store
from backend.main import create_app
from ml.config import LIMITATION_STATEMENT

API = "/api/v1"


def test_health_and_meta(client, meta):
    h = client.get(f"{API}/health").json()
    assert h["status"] == "ok"
    assert h["versions"]["model_version"].startswith("CrimeForecast-XGB-")
    assert meta["data_label"] == "SYNTHETIC / DEMONSTRATION DATA"
    assert meta["is_synthetic"] is True
    assert meta["limitation_statement"] == LIMITATION_STATEMENT
    assert [b["code"] for b in meta["bands"]] == ["NIGHT", "MORNING", "AFTERNOON", "EVENING"]
    assert meta["risk_bands"][0] == {"label": "LOW", "min": 0.0, "max": 20.0}
    labels = {c["code"]: c for c in meta["crime_types"]}
    assert labels["HBT_DAY"]["label_official"] == "H.B.T.Day"


def test_crime_types_keep_official_terms_and_reasons(client):
    body = client.get(f"{API}/crime-types").json()
    assert all(c["spatially_modelled"] for c in body["modelled"])
    reasons = {c["code"]: c["reason"] for c in body["not_modelled"]}
    assert "MOLESTATION" in reasons and reasons["OTHER_IPC"]


def test_official_summary_is_aggregate_and_flags_discrepancies(client):
    body = client.get(f"{API}/official/summary").json()
    assert body["data_nature"] == "OFFICIAL_AGGREGATE"
    ipc = next(s for s in body["sections"] if s["id"] == "IPC")
    murder = next(h for h in ipc["heads"] if h["code"] == "MURDER")
    assert murder["values"]["CM"]["registered"] == 16
    assert body["checks_summary"]["discrepancies"] == len(body["discrepancies"]) == 19


def test_zones_geojson(client, meta):
    geo = client.get(f"{API}/zones").json()
    assert geo["type"] == "FeatureCollection"
    assert len(geo["features"]) == meta["region"]["n_zones"]
    assert geo["features"][0]["geometry"]["type"] == "Polygon"


def test_predictions_layer_keeps_scores_distinct(client):
    body = client.get(
        f"{API}/predictions", params={"crime_type": "THEFT", "band": "EVENING"}
    ).json()
    assert body["aggregation"] is None
    items = body["items"]
    assert items and all(i["crime_type"] == "THEFT" and i["band"] == "EVENING" for i in items)
    for i in items:
        assert 0 <= i["probability"] <= 1
        assert 0 <= i["crs"] <= 100 and 0 <= i["final_risk"] <= 100
    overall = client.get(f"{API}/predictions").json()
    assert overall["aggregation"].startswith("maximum")
    assert len({i["zone_id"] for i in overall["items"]}) == len(overall["items"])


@pytest.mark.parametrize("period", ["24h", "7d", "30d", "90d", "6m", "1y"])
def test_hotspot_periods(client, period):
    r = client.get(f"{API}/hotspots", params={"crime_type": "THEFT", "period": period})
    assert r.status_code == 200
    body = r.json()
    assert body["method"].startswith("Getis-Ord Gi*")
    assert sum(i["count"] for i in body["items"]) == body["summary"]["total_incidents"]


def test_custom_period_and_validation(client):
    ok = client.get(
        f"{API}/hotspots", params={"period": "custom", "start": "2025-01-01", "end": "2025-03-31"}
    )
    assert ok.status_code == 200
    assert client.get(f"{API}/hotspots", params={"period": "custom"}).status_code == 422
    assert client.get(f"{API}/hotspots", params={"period": "5y"}).status_code == 422
    assert client.get(f"{API}/predictions", params={"crime_type": "FOO"}).status_code == 422


def test_states_affinity_anomalies(client):
    st = client.get(f"{API}/emerging-hotspots", params={"crime_type": "THEFT"}).json()
    assert set(st["summary"]) <= {
        "EMERGING",
        "ACTIVE",
        "PERSISTENT",
        "DECLINING",
        "SPORADIC",
        "STABLE",
    }
    aff = client.get(f"{API}/affinity", params={"crime_type": "HURT"}).json()
    assert all(0 <= i["cai"] <= 100 for i in aff["items"])
    an = client.get(f"{API}/anomalies").json()
    assert all(a["surge_alert"] for a in an["alerts"])


def test_zone_detail_traces_scores_to_components(client, meta):
    zone = client.get(f"{API}/zones").json()["features"][10]["properties"]["zone_id"]
    r = client.get(f"{API}/zones/{zone}", params={"crime_type": "THEFT", "band": "EVENING"})
    assert r.status_code == 200
    d = r.json()
    pred = d["prediction"]
    assert sum(c["contribution"] for c in pred["components"]) == pytest.approx(pred["crs"], abs=0.1)
    assert {c["code"] for c in pred["components"]} == set("FRTASPX")
    assert all(item["feature"] for item in pred["shap"]["top"])
    assert pred["event_definition"].startswith("At least one reported")
    assert len(d["bands"]) == 4 and len(d["history"]["weekly"]) == 52
    assert d["limitation_statement"] == LIMITATION_STATEMENT
    assert d["data_label"] == "SYNTHETIC / DEMONSTRATION DATA"
    for key in ("model_version", "training_dataset_version", "feature_version", "generated_at"):
        assert d["versions"][key]


def test_zone_detail_errors(client):
    assert (
        client.get(
            f"{API}/zones/Z999", params={"crime_type": "THEFT", "band": "EVENING"}
        ).status_code
        == 404
    )
    zone = client.get(f"{API}/zones").json()["features"][0]["properties"]["zone_id"]
    assert (
        client.get(
            f"{API}/zones/{zone}", params={"crime_type": "ALL", "band": "EVENING"}
        ).status_code
        == 422
    )


def test_predict_endpoint(client):
    zone = client.get(f"{API}/zones").json()["features"][3]["properties"]["zone_id"]
    r = client.post(f"{API}/predict", json={"zone_id": zone, "crime_type": "THEFT", "window": "7d"})
    assert r.status_code == 200
    body = r.json()
    assert body["prediction_window"]["label"] == "next_7_days"
    assert len(body["all_bands"]) == 4
    assert body["risk_score"] == max(b["final_risk"] for b in body["all_bands"])
    bad = client.post(
        f"{API}/predict", json={"zone_id": zone, "crime_type": "THEFT", "window": "24h"}
    )
    assert bad.status_code == 422


def test_dashboard_and_station_filter(client):
    d = client.get(f"{API}/dashboard/summary").json()
    assert set(d["kpis"]) == {
        "active_hotspots",
        "emerging_hotspots",
        "current_anomalies",
        "high_risk_zones",
        "zones",
    }
    assert set(d["kpi_definitions"]) >= {"active_hotspots", "high_risk_zones"}
    assert len(d["trend"]) == 52 and len(d["hourly"]) == 24 and len(d["weekday"]) == 7
    station = client.get(f"{API}/stations").json()["items"][0]["station_id"]
    s = client.get(f"{API}/dashboard/summary", params={"station_id": station}).json()
    assert s["kpis"]["zones"] <= d["kpis"]["zones"]
    assert client.get(f"{API}/dashboard/summary", params={"station_id": "NOPE"}).status_code == 422


def test_crime_type_profile_separates_official_and_synthetic(client):
    p = client.get(f"{API}/crime-types/ROBBERY_CHAIN_SNATCHING/profile").json()
    assert p["official"]["data_nature"] == "OFFICIAL_AGGREGATE"
    assert p["official"]["values"]["CY"]["registered"] == 70
    assert p["incident_data"]["data_label"] == "SYNTHETIC / DEMONSTRATION DATA"
    dims = {d["name"] for d in p["fingerprint"]["dimensions"]}
    assert "spatial_concentration" in dims and len(dims) == 8
    assert all(0 <= d["value"] <= 1 for d in p["fingerprint"]["dimensions"])


def test_model_card_and_quality(client):
    m = client.get(f"{API}/model").json()
    assert "xgboost_calibrated" in m["metrics"]["test"]
    assert m["metadata"]["is_synthetic_data"] is True
    q = client.get(f"{API}/data-quality").json()
    assert q["dataset"]["is_synthetic"] is True
    assert q["report"]["rows_in"] >= q["report"]["rows_out"]


def test_incidents_endpoint(client):
    body = client.get(f"{API}/incidents", params={"limit": 5}).json()
    assert len(body["items"]) == 5
    assert all(i["source"] == "SYNTHETIC_DEMO" for i in body["items"])


def test_not_ready_returns_503(tmp_path, api_cfg):
    empty = api_cfg.model_copy(deep=True)
    empty.paths.data_dir = tmp_path / "data"
    empty.paths.artifacts_dir = tmp_path / "artifacts"
    set_store(DataStore(empty))
    try:
        from fastapi.testclient import TestClient

        with TestClient(create_app()) as c:
            assert c.get(f"{API}/health").json()["status"] == "not_ready"
            assert c.get(f"{API}/predictions").status_code == 503
    finally:
        set_store(DataStore(api_cfg))
