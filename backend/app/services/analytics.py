"""Query services behind the API. They read pipeline outputs and never re-score.

The only computations done here are descriptive (counts, shares) and on-demand Gi*
hotspot maps for user-selected periods, which reuse the ML package's hotspot engine.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from backend.app.services.store import DataStore
from backend.app.utils.periods import PERIODS, resolve_period
from ml.analytics.fingerprint import fingerprint
from ml.analytics.gistar import CLASS_LABELS
from ml.analytics.hotspot_states import STATE_DESCRIPTIONS, STATES
from ml.analytics.hotspots import hotspot_map, zone_counts
from ml.config import LIMITATION_STATEMENT
from ml.data.official.taxonomy import HEADS_BY_CODE
from ml.scoring.bands import band_table

ALL = "ALL"
STATE_PRIORITY = {
    s: i
    for i, s in enumerate(("EMERGING", "ACTIVE", "PERSISTENT", "DECLINING", "SPORADIC", "STABLE"))
}
COMPONENT_INFO = {
    "F": (
        "Historical frequency",
        "Incidents of this type in this band over the last 8 weeks, "
        "relative to the average zone, as a percentile of the training period.",
    ),
    "R": (
        "Recency",
        "exp(-lambda x days since the last incident of this type in the zone); "
        "lambda tuned per crime type on validation data.",
    ),
    "T": ("Trend", "sigmoid of the change of the last 4 weeks vs the zone's own 52-week baseline."),
    "A": ("Crime affinity", "Crime Affinity Index / 100 (historical association, not causation)."),
    "S": (
        "Neighbour pressure",
        "Inverse-distance weighted same-type activity in neighbouring zones, as a percentile.",
    ),
    "P": (
        "Temporal similarity",
        "Cosine similarity between the zone's time-band profile for "
        "this crime type and the requested band.",
    ),
    "X": (
        "Anomaly",
        "Capped z-score of last week's count vs the previous 52 weeks (Crime Surge Detector).",
    ),
}
KPI_DEFINITIONS = {
    "active_hotspots": "Zone and crime-type pairs in state ACTIVE or PERSISTENT (Gi* hotspot "
    "in the most recent four-week period).",
    "emerging_hotspots": "Zone and crime-type pairs in state EMERGING.",
    "current_anomalies": "Surge alerts: last week's count has z >= alert threshold and at least "
    "the minimum count.",
    "high_risk_zones": "Zones with at least one crime type and time band whose blended risk "
    "score is HIGH or VERY HIGH for the forecast window.",
}


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _check_crime(store: DataStore, crime_type: str, allow_all: bool = True) -> None:
    valid = set(store.cfg.crime_types.modelled) | ({ALL} if allow_all else set())
    if crime_type not in valid:
        raise ValueError(f"crime_type must be one of {sorted(valid)}")


def _check_band(store: DataStore, band: str, allow_all: bool = True) -> None:
    valid = set(store.band_labels) | ({ALL} if allow_all else set())
    if band not in valid:
        raise ValueError(f"band must be one of {sorted(valid)}")


def versions(store: DataStore) -> dict[str, str]:
    m = store.predictions_manifest
    keys = (
        "model_version",
        "training_dataset_version",
        "input_dataset_version",
        "feature_version",
        "generated_at",
    )
    return {k: m[k] for k in keys}


def window(store: DataStore) -> dict[str, Any]:
    m = store.predictions_manifest
    return {
        "start": m["window_start"],
        "end": m["window_end"],
        "days": m["window_days"],
        "label": f"next_{m['window_days']}_days",
    }


def zone_station(store: DataStore) -> dict[str, str]:
    return dict(zip(store.zones["zone_id"], store.zones["station_id"], strict=True))


# ---------------------------------------------------------------------------- meta


def meta(store: DataStore) -> dict[str, Any]:
    cfg = store.cfg
    man = store.predictions_manifest
    b = cfg.region.bbox
    inc = store.incidents
    return {
        "platform": "CrimeX",
        "title": "AI Crime Intelligence",
        "data_label": store.dataset_manifest["data_label"],
        "is_synthetic": store.dataset_manifest["is_synthetic"],
        "limitation_statement": LIMITATION_STATEMENT,
        "as_of": man["as_of"],
        "forecast_window": window(store),
        "event_definition": man["event_definition"],
        "score_definitions": man["scores"],
        "bands": [bd.model_dump() for bd in cfg.time.bands],
        "crime_types": [
            {
                "code": c,
                "label": store.crime_labels[c],
                "label_official": HEADS_BY_CODE[c].label_official,
                "severity": cfg.crime_types.severity.get(c),
            }
            for c in cfg.crime_types.modelled
        ],
        "risk_bands": band_table(cfg.scoring.risk_bands),
        "affinity_bands": band_table(cfg.scoring.affinity_bands),
        "hotspot_states": [{"code": s, "description": STATE_DESCRIPTIONS[s]} for s in STATES],
        "hotspot_classes": [{"code": k, "label": v} for k, v in CLASS_LABELS.items()],
        "periods": [*PERIODS, "custom"],
        "versions": versions(store),
        "data_range": {
            "start": inc["timestamp"].min().isoformat(),
            "end": inc["timestamp"].max().isoformat(),
        },
        "region": {
            "name": cfg.region.name,
            "description": cfg.region.description,
            "bbox": [b.west, b.south, b.east, b.north],
            "center": [(b.west + b.east) / 2, (b.south + b.north) / 2],
            "cell_size_m": cfg.grid.cell_size_m,
            "n_zones": store.grid.n_zones,
        },
        "n_stations": int(len(store.stations)),
        "crs_weights": cfg.scoring.crs_weights,
        "cai_weights": cfg.scoring.cai_weights,
        "blend_ml_weight": cfg.scoring.blend_ml_weight,
    }


def crime_types(store: DataStore) -> dict[str, Any]:
    cfg = store.cfg
    modelled = [
        {
            "code": c,
            "label": store.crime_labels[c],
            "label_official": HEADS_BY_CODE[c].label_official,
            "section": HEADS_BY_CODE[c].section,
            "severity": cfg.crime_types.severity.get(c),
            "allowed_hours": cfg.crime_types.allowed_hours.get(c),
            "spatially_modelled": True,
        }
        for c in cfg.crime_types.modelled
    ]
    not_modelled = [
        {
            "code": c,
            "label": HEADS_BY_CODE[c].label if c in HEADS_BY_CODE else c,
            "label_official": HEADS_BY_CODE[c].label_official if c in HEADS_BY_CODE else c,
            "spatially_modelled": False,
            "reason": reason,
        }
        for c, reason in cfg.crime_types.not_modelled.items()
    ]
    return {"modelled": modelled, "not_modelled": not_modelled}


# ---------------------------------------------------------------------------- official


def official_summary(store: DataStore) -> dict[str, Any]:
    doc = store.official.doc
    values: dict[str, dict[str, dict[str, Any]]] = {}
    for v in doc["values"]:
        values.setdefault(v["head"], {}).setdefault(v["period"], {})[v["metric"]] = v["value"]
    modelled = set(store.cfg.crime_types.modelled)
    sections = []
    for sec in doc["sections"]:
        heads = [
            {
                "code": h["code"],
                "sr": h["sr"],
                "label_official": h["label_official"],
                "label": h["label"],
                "parent": h["parent"],
                "is_aggregate": h["is_aggregate"],
                "legal_reference": h["legal_reference"],
                "spatially_modelled": h["code"] in modelled,
                "values": values.get(h["code"], {}),
            }
            for h in doc["heads"]
            if h["section"] == sec["id"]
        ]
        sections.append({**sec, "heads": heads})
    return {
        "data_nature": "OFFICIAL_AGGREGATE",
        "note": "City-level aggregate statistics exactly as printed in the official statement. "
        "Not incident-level data; not used as model training rows.",
        "report": doc["report"],
        "periods": doc["periods"],
        "sections": sections,
        "checks_summary": doc["checks_summary"],
        "discrepancies": [c for c in doc["checks"] if c["status"] != "pass"],
        "source_notes": doc["source_notes"],
        "extraction_notes": doc["extraction_notes"],
    }


# ---------------------------------------------------------------------------- geography


def stations(store: DataStore) -> dict[str, Any]:
    st = store.stations.copy()
    counts = store.zones["station_id"].value_counts()
    st["zones"] = st["station_id"].map(counts).fillna(0).astype(int)
    return {"data_label": store.dataset_manifest["data_label"], "items": _records(st)}


def zones_geojson(store: DataStore) -> dict[str, Any]:
    geo = store.zones_geojson
    names = dict(
        zip(store.stations.get("station_id", []), store.stations.get("name", []), strict=False)
    )
    for f in geo["features"]:
        f["properties"]["station_name"] = names.get(f["properties"].get("station_id"))
    return geo


# ---------------------------------------------------------------------------- layers


LAYER_COLUMNS = [
    "zone_id",
    "crime_type",
    "band",
    "final_risk",
    "risk_band",
    "crs",
    "crs_band",
    "probability",
    "confidence",
    "expected_count",
    "hotspot_state",
    "cai",
    "affinity_band",
]


def predictions_layer(store: DataStore, crime_type: str, band: str) -> dict[str, Any]:
    _check_crime(store, crime_type)
    _check_band(store, band)
    p = store.predictions
    if crime_type != ALL:
        p = p[p["crime_type"] == crime_type]
    if band != ALL:
        p = p[p["band"] == band]
    # With ALL, each zone shows its highest crime-type/band-specific score (never a sum).
    idx = p.groupby("zone_id")["final_risk"].idxmax()
    layer = p.loc[idx, LAYER_COLUMNS].sort_values("zone_id")
    return {
        "crime_type": crime_type,
        "band": band,
        "aggregation": None
        if (crime_type != ALL and band != ALL)
        else "maximum over the selected crime types / bands",
        "window": window(store),
        "items": _records(layer),
        "summary": layer["risk_band"].value_counts().to_dict(),
        "versions": versions(store),
    }


def hotspots(
    store: DataStore,
    crime_type: str,
    period: str,
    start: str | None,
    end: str | None,
    band: str,
) -> dict[str, Any]:
    _check_crime(store, crime_type)
    _check_band(store, band)
    s, e = resolve_period(period, store.as_of, start, end)
    counts = zone_counts(
        store.incidents,
        store.grid,
        s,
        e,
        None if crime_type == ALL else crime_type,
        None if band == ALL else band,
    )
    df = hotspot_map(counts, store.grid, store.cfg.hotspots)
    return {
        "crime_type": crime_type,
        "band": band,
        "period": period,
        "start": s.isoformat(),
        "end": e.isoformat(),
        "method": "Getis-Ord Gi* on zone counts, queen contiguity including the zone itself; "
        "two-sided normal p-values"
        + (" with Benjamini-Hochberg FDR" if store.cfg.hotspots.fdr_correction else ""),
        "items": _records(df),
        "summary": {
            "total_incidents": int(counts.sum()),
            "classes": df["hotspot_class"].value_counts().to_dict(),
        },
    }


STATE_COLUMNS = [
    "zone_id",
    "crime_type",
    "state",
    "hot_periods",
    "n_periods",
    "recent_hot_periods",
    "final_period_hot",
    "current_hot_run_periods",
    "trend",
    "trend_tau",
    "trend_p",
    "gi_z_last",
    "recent_rate",
    "prior_rate",
]


def hotspot_states(store: DataStore, crime_type: str) -> dict[str, Any]:
    _check_crime(store, crime_type)
    zc = store.zone_crime
    if crime_type != ALL:
        layer = zc[zc["crime_type"] == crime_type][STATE_COLUMNS]
    else:
        # per zone, the most notable state across crime types
        tmp = zc[STATE_COLUMNS].assign(_prio=zc["state"].map(STATE_PRIORITY))
        tmp = tmp.sort_values(["zone_id", "_prio", "hot_periods"], ascending=[True, True, False])
        layer = tmp.groupby("zone_id").head(1).drop(columns="_prio")
    emerging = zc[zc["state"] == "EMERGING"]
    if crime_type != ALL:
        emerging = emerging[emerging["crime_type"] == crime_type]
    top = _top_emerging(store, emerging)
    return {
        "crime_type": crime_type,
        "as_of": store.predictions_manifest["as_of"],
        "analysis": {
            "period_weeks": store.cfg.hotspots.period_weeks,
            "n_periods": store.cfg.hotspots.n_periods,
            "hot_z": store.cfg.hotspots.hot_z,
        },
        "items": _records(layer.sort_values("zone_id")),
        "summary": layer["state"].value_counts().to_dict(),
        "top_emerging": top,
    }


def _top_emerging(store: DataStore, emerging: pd.DataFrame, n: int = 10) -> list[dict]:
    if emerging.empty:
        return []
    p = store.predictions
    best = p.loc[
        p.groupby(["zone_id", "crime_type"])["final_risk"].idxmax(),
        ["zone_id", "crime_type", "final_risk", "risk_band", "band"],
    ]
    e = emerging.merge(best, on=["zone_id", "crime_type"], how="left")
    e["change_ratio"] = (e["recent_rate"] + 1) / (e["prior_rate"] + 1)
    e = e.sort_values(["change_ratio", "final_risk"], ascending=False).head(n)
    e["label"] = e["crime_type"].map(store.crime_labels)
    e["station_id"] = e["zone_id"].map(zone_station(store))
    cols = [
        "zone_id",
        "station_id",
        "crime_type",
        "label",
        "recent_rate",
        "prior_rate",
        "hot_periods",
        "recent_hot_periods",
        "final_risk",
        "risk_band",
        "band",
        "trend",
    ]
    return _records(e[cols])


def affinity_layer(store: DataStore, crime_type: str) -> dict[str, Any]:
    _check_crime(store, crime_type)
    zc = store.zone_crime
    cols = [
        "zone_id",
        "crime_type",
        "cai",
        "affinity_band",
        "a_spatial",
        "a_recency",
        "a_recurrence",
        "a_consistency",
        "location_quotient",
        "incidents_52w",
    ]
    if crime_type != ALL:
        layer = zc[zc["crime_type"] == crime_type][cols]
    else:
        layer = zc.loc[zc.groupby("zone_id")["cai"].idxmax(), cols]
    return {
        "crime_type": crime_type,
        "as_of": store.predictions_manifest["as_of"],
        "window_weeks": store.cfg.scoring.affinity_window_weeks,
        "weights": store.cfg.scoring.cai_weights,
        "aggregation": "maximum CAI over crime types" if crime_type == ALL else None,
        "items": _records(layer.sort_values("zone_id")),
    }


def anomalies(store: DataStore, crime_type: str) -> dict[str, Any]:
    _check_crime(store, crime_type)
    zc = store.zone_crime
    cols = [
        "zone_id",
        "crime_type",
        "surge_current_count",
        "surge_baseline_mean",
        "surge_baseline_std",
        "surge_z",
        "surge_deviation_pct",
        "surge_alert",
        "X",
    ]
    alerts = zc[zc["surge_alert"]][cols].sort_values("surge_z", ascending=False)
    alerts = alerts.assign(
        label=alerts["crime_type"].map(store.crime_labels),
        station_id=alerts["zone_id"].map(zone_station(store)),
    )
    layer = zc if crime_type == ALL else zc[zc["crime_type"] == crime_type]
    layer = layer.loc[layer.groupby("zone_id")["surge_z"].idxmax(), cols]
    as_of = store.as_of
    return {
        "crime_type": crime_type,
        "as_of": as_of.date().isoformat(),
        "detection_window": {
            "start": (as_of - pd.Timedelta(days=store.cfg.time.window_days)).isoformat(),
            "end": as_of.isoformat(),
        },
        "method": "z = (last week's count - mean of the previous "
        f"{store.cfg.scoring.anomaly_history_weeks} weeks) / (std + "
        f"{store.cfg.scoring.anomaly_epsilon}); alert when z >= "
        f"{store.cfg.scoring.anomaly_alert_z} and count >= "
        f"{store.cfg.scoring.anomaly_alert_min_count}",
        "alerts": _records(alerts),
        "items": _records(layer.sort_values("zone_id")),
    }


# ---------------------------------------------------------------------------- zone detail


def _parse_json_cols(rec: dict[str, Any], cols: tuple[str, ...]) -> dict[str, Any]:
    for c in cols:
        if isinstance(rec.get(c), str):
            rec[c] = json.loads(rec[c])
    return rec


def zone_detail(store: DataStore, zone_id: str, crime_type: str, band: str) -> dict[str, Any]:
    _check_crime(store, crime_type, allow_all=False)
    _check_band(store, band, allow_all=False)
    zones = store.zones.set_index("zone_id")
    if zone_id not in zones.index:
        raise KeyError(f"Unknown zone {zone_id}")
    z = zones.loc[zone_id]
    p = store.predictions
    row = p[(p["zone_id"] == zone_id) & (p["crime_type"] == crime_type) & (p["band"] == band)]
    rec = _parse_json_cols(_records(row)[0], ("shap_top", "reasons"))
    zc = store.zone_crime
    zc_row = _parse_json_cols(
        _records(zc[(zc["zone_id"] == zone_id) & (zc["crime_type"] == crime_type)])[0],
        ("gi_z_series", "count_series"),
    )
    s = store.cfg.scoring
    raw = {
        "F": {"band_count_8w": rec["raw_F_band_count"], "city_mean_8w": rec["raw_F_city_mean"]},
        "R": {
            "days_since_last": zc_row["days_since_last"],
            "half_life_days": rec["recency_half_life_days"],
        },
        "T": {
            "recent_4w": zc_row["trend_recent_4w"],
            "baseline_4w": zc_row["trend_baseline_4w"],
            "ratio": zc_row["trend_ratio"],
        },
        "A": {"cai": zc_row["cai"]},
        "S": {"neighbour_weighted_mean_8w": rec["raw_S_neighbour_mean"]},
        "P": {"band_share": rec["raw_P_band_share"]},
        "X": {
            "last_week": zc_row["surge_current_count"],
            "mean_52w": zc_row["surge_baseline_mean"],
            "std_52w": zc_row["surge_baseline_std"],
            "z": zc_row["surge_z"],
        },
    }
    components = [
        {
            "code": c,
            "name": COMPONENT_INFO[c][0],
            "description": COMPONENT_INFO[c][1],
            "value": rec[f"comp_{c}"],
            "weight": s.crs_weights[c],
            "contribution": rec[f"contrib_{c}"],
            "raw": raw[c],
        }
        for c in s.crs_weights
    ]
    same_zone = p[(p["zone_id"] == zone_id) & (p["crime_type"] == crime_type)]
    band_rows = _records(
        same_zone[
            ["band", "final_risk", "risk_band", "probability", "crs", "crs_band", "expected_count"]
        ]
    )
    for b in band_rows:
        b["label"] = store.band_labels[b["band"]]

    zone_p = p[p["zone_id"] == zone_id]
    best = zone_p.loc[zone_p.groupby("crime_type")["final_risk"].idxmax()]
    risk_profile = _records(
        best[["crime_type", "band", "final_risk", "risk_band", "probability", "crs"]].sort_values(
            "final_risk", ascending=False
        )
    )
    zone_zc = zc[zc["zone_id"] == zone_id]
    affinity = _records(
        zone_zc[
            [
                "crime_type",
                "cai",
                "affinity_band",
                "a_spatial",
                "a_recency",
                "a_recurrence",
                "a_consistency",
                "location_quotient",
                "incidents_52w",
                "state",
            ]
        ].sort_values("cai", ascending=False)
    )
    for item in (*risk_profile, *affinity):
        item["label"] = store.crime_labels[item["crime_type"]]

    inc = store.incidents
    zi = inc[(inc["zone_id"] == zone_id) & (inc["crime_type"] == crime_type)]
    as_of = store.as_of
    start = as_of - pd.Timedelta(weeks=52)
    recent = zi[zi["timestamp"] >= start]
    week_idx = ((recent["timestamp"] - start).dt.days // 7).clip(upper=51)
    weekly = np.zeros((52, len(store.band_labels)), dtype=int)
    bands_order = list(store.band_labels)
    np.add.at(weekly, (week_idx.to_numpy(), recent["band"].map(bands_order.index).to_numpy()), 1)
    weekly_rows = [
        {
            "week_start": (start + pd.Timedelta(weeks=i)).date().isoformat(),
            "count": int(weekly[i].sum()),
            **{b: int(weekly[i, j]) for j, b in enumerate(bands_order)},
        }
        for i in range(52)
    ]
    hourly = np.bincount(recent["hour"].to_numpy(), minlength=24).tolist()
    h = store.crs_history
    timeline = h[(h["zone_id"] == zone_id) & (h["crime_type"] == crime_type) & (h["band"] == band)]
    last_inc = zi.sort_values("timestamp", ascending=False).head(10)
    names = dict(
        zip(store.stations.get("station_id", []), store.stations.get("name", []), strict=False)
    )
    area = (store.cfg.grid.cell_size_m / 1000) ** 2 * float(z["land_fraction"])
    return {
        "zone": {
            "zone_id": zone_id,
            "row": int(z["row"]),
            "col": int(z["col"]),
            "centroid": [float(z["centroid_lon"]), float(z["centroid_lat"])],
            "station_id": z["station_id"],
            "station_name": names.get(z["station_id"]),
            "land_fraction": float(z["land_fraction"]),
            "area_km2": round(area, 2),
        },
        "crime_type": crime_type,
        "crime_label": store.crime_labels[crime_type],
        "band": band,
        "band_label": store.band_labels[band],
        "window": window(store),
        "prediction": {
            "prediction_id": rec["prediction_id"],
            "event_definition": (
                f"At least one reported {store.crime_labels[crime_type]} incident in zone "
                f"{zone_id} during {store.band_labels[band]} on any day from "
                f"{rec['window_start'][:10]} to "
                f"{(pd.Timestamp(rec['window_end']) - pd.Timedelta(days=1)).date()}"
            ),
            "probability": rec["probability"],
            "probability_raw": rec["probability_raw"],
            "confidence": rec["confidence"],
            "calibration_gap": rec["calibration_gap"],
            "support_incidents_52w": rec["support_incidents_52w"],
            "expected_count": rec["expected_count"],
            "crs": rec["crs"],
            "crs_band": rec["crs_band"],
            "final_risk": rec["final_risk"],
            "risk_band": rec["risk_band"],
            "blend_ml_weight": s.blend_ml_weight,
            "components": components,
            "reasons": rec["reasons"],
            "shap": {"bias_log_odds": rec["shap_bias_log_odds"], "top": rec["shap_top"]},
        },
        "bands": band_rows,
        "risk_profile": risk_profile,
        "affinity_profile": affinity,
        "hotspot_state": {
            k: zc_row[k]
            for k in (
                "state",
                "hot_periods",
                "n_periods",
                "hot_fraction",
                "recent_hot_periods",
                "final_period_hot",
                "current_hot_run_periods",
                "trend",
                "trend_tau",
                "trend_p",
                "gi_z_last",
                "gi_z_series",
                "count_series",
                "recent_rate",
                "prior_rate",
            )
        }
        | {
            "period_weeks": store.cfg.hotspots.period_weeks,
            "description": STATE_DESCRIPTIONS[zc_row["state"]],
        },
        "surge": {
            "current_count": zc_row["surge_current_count"],
            "baseline_mean": zc_row["surge_baseline_mean"],
            "baseline_std": zc_row["surge_baseline_std"],
            "z_score": zc_row["surge_z"],
            "deviation_pct": zc_row["surge_deviation_pct"],
            "is_alert": zc_row["surge_alert"],
        },
        "history": {
            "weekly": weekly_rows,
            "hourly_52w": hourly,
            "crs_timeline": _records(timeline.drop(columns=["zone_id", "crime_type", "band"])),
        },
        "recent_incidents": _records(
            last_inc[["incident_id", "timestamp", "band", "severity", "source"]]
        ),
        "versions": versions(store),
        "data_label": store.dataset_manifest["data_label"],
        "limitation_statement": LIMITATION_STATEMENT,
    }


def predict(
    store: DataStore, zone_id: str, crime_type: str, window_code: str, band: str | None
) -> dict[str, Any]:
    days = store.cfg.time.window_days
    if window_code not in (f"{days}d",):
        raise ValueError(f"Only the '{days}d' prediction window is available in this version")
    _check_crime(store, crime_type, allow_all=False)
    if band is not None:
        _check_band(store, band, allow_all=False)
    p = store.predictions
    rows = p[(p["zone_id"] == zone_id) & (p["crime_type"] == crime_type)]
    if rows.empty:
        raise KeyError(f"Unknown zone {zone_id}")
    all_bands = _records(rows[["band", "final_risk", "risk_band", "probability", "crs"]])
    row = rows[rows["band"] == band].iloc[0] if band else rows.loc[rows["final_risk"].idxmax()]
    reasons = json.loads(row["reasons"])
    return {
        "zone_id": zone_id,
        "crime_type": crime_type,
        "band": row["band"],
        "band_label": store.band_labels[row["band"]],
        "prediction_window": window(store),
        "risk_score": float(row["final_risk"]),
        "risk_band": row["risk_band"],
        "crs": float(row["crs"]),
        "probability": float(row["probability"]),
        "confidence": row["confidence"],
        "status": row["hotspot_state"].lower(),
        "drivers": [r["component"] for r in reasons],
        "reasons": reasons,
        "event_definition": store.predictions_manifest["event_definition"],
        "all_bands": all_bands,
        "versions": versions(store),
        "note": "Served from the versioned prediction run for the current forecast window.",
        "limitation_statement": LIMITATION_STATEMENT,
    }


# ---------------------------------------------------------------------------- dashboard


def _station_zones(store: DataStore, station_id: str | None) -> set[str] | None:
    if not station_id:
        return None
    z = store.zones[store.zones["station_id"] == station_id]["zone_id"]
    if z.empty:
        raise ValueError(f"Unknown station {station_id}")
    return set(z)


def dashboard_summary(store: DataStore, crime_type: str, station_id: str | None) -> dict:
    _check_crime(store, crime_type)
    zones = _station_zones(store, station_id)
    zc, p, inc = store.zone_crime, store.predictions, store.incidents
    if zones is not None:
        zc, p, inc = (d[d["zone_id"].isin(zones)] for d in (zc, p, inc))
    if crime_type != ALL:
        zc, p, inc = (d[d["crime_type"] == crime_type] for d in (zc, p, inc))
    as_of = store.as_of
    high = p[p["risk_band"].isin(["HIGH", "VERY HIGH"])]["zone_id"].nunique()
    kpis = {
        "active_hotspots": int(zc["state"].isin(["ACTIVE", "PERSISTENT"]).sum()),
        "emerging_hotspots": int((zc["state"] == "EMERGING").sum()),
        "current_anomalies": int(zc["surge_alert"].sum()),
        "high_risk_zones": int(high),
        "zones": len(zones) if zones is not None else store.grid.n_zones,
    }
    y_start = as_of - pd.Timedelta(weeks=52)
    last_year = inc[inc["timestamp"] >= y_start]
    week = ((last_year["timestamp"] - y_start).dt.days // 7).clip(upper=51)
    trend_df = (
        last_year.assign(week=week)
        .groupby(["week", "crime_type"])
        .size()
        .unstack(fill_value=0)
        .reindex(range(52), fill_value=0)
    )
    trend = [
        {
            "week_start": (y_start + pd.Timedelta(weeks=int(i))).date().isoformat(),
            **{c: int(v) for c, v in r.items()},
        }
        for i, r in trend_df.iterrows()
    ]
    dist = last_year["crime_type"].value_counts()
    t4 = as_of - pd.Timedelta(weeks=4)
    t8 = as_of - pd.Timedelta(weeks=8)
    top_types = []
    for c, n52 in dist.items():
        sub = last_year[last_year["crime_type"] == c]
        last4 = int((sub["timestamp"] >= t4).sum())
        prev4 = int(((sub["timestamp"] >= t8) & (sub["timestamp"] < t4)).sum())
        top_types.append(
            {
                "crime_type": c,
                "label": store.crime_labels[c],
                "last_52w": int(n52),
                "last_4w": last4,
                "prev_4w": prev4,
                "change_pct": round(100 * (last4 - prev4) / prev4, 1) if prev4 else None,
            }
        )
    top_types.sort(key=lambda d: -d["last_4w"])
    alerts = zc[zc["surge_alert"]].sort_values("surge_z", ascending=False)
    alerts_out = [
        {
            "zone_id": r.zone_id,
            "crime_type": r.crime_type,
            "label": store.crime_labels[r.crime_type],
            "current_count": int(r.surge_current_count),
            "baseline_mean": r.surge_baseline_mean,
            "z_score": r.surge_z,
            "deviation_pct": r.surge_deviation_pct,
            "station_id": zone_station(store).get(r.zone_id),
        }
        for r in alerts.itertuples()
    ]
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {
        "filters": {"crime_type": crime_type, "station_id": station_id},
        "as_of": as_of.date().isoformat(),
        "window": window(store),
        "kpis": kpis,
        "kpi_definitions": KPI_DEFINITIONS,
        "top_emerging": _top_emerging(store, zc[zc["state"] == "EMERGING"]),
        "top_crime_types": top_types,
        "alerts": alerts_out,
        "trend": trend,
        "distribution": [
            {"crime_type": c, "label": store.crime_labels[c], "count": int(n)}
            for c, n in dist.items()
        ],
        "hourly": [
            {"hour": h, "count": int(n)}
            for h, n in enumerate(np.bincount(last_year["hour"], minlength=24))
        ],
        "weekday": [
            {"day": weekday_names[d], "count": int(n)}
            for d, n in enumerate(np.bincount(last_year["day_of_week"], minlength=7))
        ],
        "lifecycle": [{"state": s, "count": int((zc["state"] == s).sum())} for s in STATES],
        "data_label": store.dataset_manifest["data_label"],
        "versions": versions(store),
    }


# ---------------------------------------------------------------------------- crime type page


def crime_type_profile(store: DataStore, code: str) -> dict[str, Any]:
    _check_crime(store, code, allow_all=False)
    head = HEADS_BY_CODE[code]
    st = store.official
    official = {}
    for per in ("CM", "PM", "CY", "PY"):
        official[per] = {
            "period": st.periods[per],
            "registered": st.value("IPC", code, per, "registered"),
            "detected": st.value("IPC", code, per, "detected"),
        }
    official["difference_registered_ytd"] = st.value(
        "IPC", code, "CY_VS_PY", "difference_registered"
    )
    as_of = store.as_of
    inc = store.incidents[store.incidents["crime_type"] == code]
    y2 = as_of - pd.Timedelta(weeks=104)
    series = inc[inc["timestamp"] >= y2]
    wk = ((series["timestamp"] - y2).dt.days // 7).clip(upper=103)
    weekly = np.bincount(wk, minlength=104)
    last = inc[inc["timestamp"] >= as_of - pd.Timedelta(weeks=52)]
    bands = list(store.band_labels)
    cal = np.zeros((7, len(bands)), dtype=int)
    np.add.at(cal, (last["day_of_week"].to_numpy(), last["band"].map(bands.index).to_numpy()), 1)
    zc = store.zone_crime[store.zone_crime["crime_type"] == code]
    p = store.predictions[store.predictions["crime_type"] == code]
    best = p.loc[p.groupby("zone_id")["final_risk"].idxmax()]
    stations = zone_station(store)
    top_aff = zc.sort_values("cai", ascending=False).head(10)
    top_risk = best.sort_values("final_risk", ascending=False).head(10)
    fp = fingerprint(store.incidents, code, as_of, store.grid, store.zone_crime, store.cfg.scoring)
    t4 = as_of - pd.Timedelta(weeks=4)
    return {
        "crime_type": code,
        "label": head.label,
        "label_official": head.label_official,
        "severity": store.cfg.crime_types.severity.get(code),
        "official": {
            "data_nature": "OFFICIAL_AGGREGATE",
            "note": "Brihan Mumbai city-level registered/detected counts as printed.",
            "values": official,
        },
        "incident_data": {
            "data_label": store.dataset_manifest["data_label"],
            "last_52w": int(len(last)),
            "last_4w": int((inc["timestamp"] >= t4).sum()),
            "total": int(len(inc)),
        },
        "weekly_104w": [
            {"week_start": (y2 + pd.Timedelta(weeks=i)).date().isoformat(), "count": int(n)}
            for i, n in enumerate(weekly)
        ],
        "time_profile": {
            "hourly": np.bincount(last["hour"], minlength=24).tolist(),
            "bands": [
                {"band": b, "label": store.band_labels[b], "count": int(cal[:, j].sum())}
                for j, b in enumerate(bands)
            ],
            "weekday": np.bincount(last["day_of_week"], minlength=7).tolist(),
            "calendar": {
                "rows": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "columns": bands,
                "counts": cal.tolist(),
            },
        },
        "fingerprint": fp,
        "top_zones_affinity": _records(
            top_aff[
                ["zone_id", "cai", "affinity_band", "location_quotient", "incidents_52w", "state"]
            ].assign(station_id=top_aff["zone_id"].map(stations))
        ),
        "top_zones_risk": _records(
            top_risk[
                [
                    "zone_id",
                    "band",
                    "final_risk",
                    "risk_band",
                    "probability",
                    "crs",
                    "hotspot_state",
                ]
            ].assign(station_id=top_risk["zone_id"].map(stations))
        ),
        "states_summary": zc["state"].value_counts().to_dict(),
        "emerging": _top_emerging(store, zc[zc["state"] == "EMERGING"]),
        "anomalies": _records(
            zc[zc["surge_alert"]][
                ["zone_id", "surge_current_count", "surge_baseline_mean", "surge_z"]
            ]
        ),
        "versions": versions(store),
    }


# ---------------------------------------------------------------------------- model + data


def model_card(store: DataStore) -> dict[str, Any]:
    md = store.model_metadata
    keep = (
        "model_version",
        "trained_at",
        "training_dataset_version",
        "data_label",
        "is_synthetic_data",
        "feature_version",
        "crime_types",
        "bands",
        "window_days",
        "target",
        "splits",
        "xgboost_params",
        "random_forest_params",
        "recency_half_life_tuning",
        "decision_thresholds",
        "crs_weights_configured",
        "crs_weights_suggested_by_logistic_fit",
        "model_selection",
        "feature_importance_gain",
        "mean_abs_shap_test_sample",
        "top_k_fraction",
        "training_seconds",
    )
    return {
        "metadata": {k: md.get(k) for k in keep},
        "metrics": store.model_metrics,
        "limitation_statement": LIMITATION_STATEMENT,
    }


def data_quality(store: DataStore) -> dict[str, Any]:
    return {
        "dataset": store.dataset_manifest,
        "report": store.quality_report,
        "note": "All figures are computed from the incident records by the data-quality "
        "monitor; the MVP incident data is synthetic and includes deliberately injected "
        "defects.",
    }


def incidents(
    store: DataStore,
    zone_id: str | None,
    crime_type: str | None,
    start: str | None,
    end: str | None,
    limit: int,
) -> dict[str, Any]:
    inc = store.incidents
    if zone_id:
        inc = inc[inc["zone_id"] == zone_id]
    if crime_type:
        _check_crime(store, crime_type, allow_all=False)
        inc = inc[inc["crime_type"] == crime_type]
    if start:
        inc = inc[inc["timestamp"] >= pd.Timestamp(start)]
    if end:
        inc = inc[inc["timestamp"] < pd.Timestamp(end) + pd.Timedelta(days=1)]
    inc = inc.sort_values("timestamp", ascending=False)
    cols = [
        "incident_id",
        "timestamp",
        "crime_type",
        "latitude",
        "longitude",
        "zone_id",
        "police_station_id",
        "band",
        "severity",
        "source",
    ]
    return {
        "data_label": store.dataset_manifest["data_label"],
        "total": int(len(inc)),
        "items": _records(inc.head(limit)[cols]),
    }
