"""Hotspot lifecycle, hotspot movement, historical pattern matching and station roll-ups.

All numbers are read from pipeline artifacts (``lifecycle``, ``movement``, ``analogs``,
``predictions``, ``zone_crime``); nothing is re-scored here.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from backend.app.services.analytics import (
    ALL,
    KPI_DEFINITIONS,
    _check_band,
    _check_crime,
    _records,
    versions,
    window,
    zone_station,
)
from backend.app.services.store import DataStore
from ml.analytics.lifecycle import LIFECYCLE_STAGES, STAGE_DESCRIPTIONS
from ml.config import LIMITATION_STATEMENT

STAGE_PRIORITY = {
    s: i
    for i, s in enumerate(("EMERGING", "ACTIVE", "PERSISTENT", "DECLINING", "RESOLVED", "NORMAL"))
}
MOVEMENT_NOTE = (
    "Hotspot movement summarises where statistically significant clusters of historical "
    "reported incidents were between successive analysis periods. It does not predict where "
    "activity will move next."
)
PATTERN_NOTE = (
    "Analogs are past periods of this zone and crime type whose weekly counts resemble the "
    "recent ones, with what followed them. They are a descriptive comparison, not a forecast; "
    "the calibrated model probability is the only probability."
)


def _check_zone(store: DataStore, zone_id: str) -> None:
    if zone_id not in store.grid.zone_index:
        raise KeyError(f"Unknown zone {zone_id}")


def _analysis(store: DataStore) -> dict[str, Any]:
    h = store.cfg.hotspots
    return {
        "period_weeks": h.period_weeks,
        "period_windows": store.predictions_manifest.get("analysis_period_windows"),
        "n_periods": h.n_periods,
        "hot_z": h.hot_z,
        "steps": h.lifecycle_steps,
    }


# ---------------------------------------------------------------------------- lifecycle


def _step_dates(lc: pd.DataFrame) -> list[dict[str, Any]]:
    d = lc.drop_duplicates("step").sort_values("step")
    return [
        {
            "step": int(r.step),
            "period_start": pd.Timestamp(r.period_start).date().isoformat(),
            "period_end": pd.Timestamp(r.period_end).date().isoformat(),
        }
        for r in d.itertuples()
    ]


def lifecycle_overview(store: DataStore, crime_type: str) -> dict[str, Any]:
    """Stage counts per step, transitions into the latest step, and each zone's stage."""
    _check_crime(store, crime_type)
    lc = store.lifecycle
    if crime_type != ALL:
        lc = lc[lc["crime_type"] == crime_type]
    steps = _step_dates(lc)
    counts = lc.groupby(["step", "stage"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=list(LIFECYCLE_STAGES), fill_value=0)
    by_step = [
        {**s, **{st: int(counts.loc[s["step"], st]) for st in LIFECYCLE_STAGES}} for s in steps
    ]
    transitions: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    if steps:
        last = steps[-1]["step"]
        cur = lc[lc["step"] == last].set_index(["zone_id", "crime_type"])["stage"]
        if last > 0:
            prev = lc[lc["step"] == last - 1].set_index(["zone_id", "crime_type"])["stage"]
            pair = pd.DataFrame({"from": prev, "to": cur}).dropna()
            t = pair.groupby(["from", "to"]).size().reset_index(name="count")
            t = t[t["from"] != t["to"]].sort_values("count", ascending=False)
            transitions = _records(t)
        latest = lc[lc["step"] == last][["zone_id", "crime_type", "stage", "state"]]
        if crime_type == ALL:
            latest = (
                latest.assign(_p=latest["stage"].map(STAGE_PRIORITY))
                .sort_values(["zone_id", "_p"])
                .groupby("zone_id")
                .head(1)
                .drop(columns="_p")
            )
        items = _records(latest.sort_values("zone_id"))
    return {
        "crime_type": crime_type,
        "as_of": store.predictions_manifest["as_of"],
        "analysis": _analysis(store),
        "stages": [{"stage": s, "description": STAGE_DESCRIPTIONS[s]} for s in LIFECYCLE_STAGES],
        "steps": by_step,
        "transitions_latest": transitions,
        "items": items,
        "aggregation": None if crime_type != ALL else "most notable stage over crime types",
        "data_label": store.dataset_manifest["data_label"],
        "versions": versions(store),
    }


def zone_lifecycle(store: DataStore, zone_id: str, crime_type: str) -> dict[str, Any]:
    _check_zone(store, zone_id)
    _check_crime(store, crime_type, allow_all=False)
    lc = store.lifecycle
    g = lc[(lc["zone_id"] == zone_id) & (lc["crime_type"] == crime_type)].sort_values("step")
    timeline = [
        {
            "step": int(r.step),
            "period_start": pd.Timestamp(r.period_start).date().isoformat(),
            "period_end": pd.Timestamp(r.period_end).date().isoformat(),
            "state": r.state,
            "stage": r.stage,
            "gi_z_last": round(float(r.gi_z_last), 3),
            "final_period_hot": bool(r.final_period_hot),
        }
        for r in g.itertuples()
    ]
    stages = [t["stage"] for t in timeline]
    run = 0
    for s in reversed(stages):
        if stages and s != stages[-1]:
            break
        run += 1
    return {
        "zone_id": zone_id,
        "crime_type": crime_type,
        "label": store.crime_labels[crime_type],
        "analysis": _analysis(store),
        "current_stage": stages[-1] if stages else None,
        "previous_stage": stages[-2] if len(stages) > 1 else None,
        "steps_in_stage": run,
        "stage_description": STAGE_DESCRIPTIONS.get(stages[-1]) if stages else None,
        "timeline": timeline,
        "data_label": store.dataset_manifest["data_label"],
        "versions": versions(store),
    }


# ---------------------------------------------------------------------------- movement


def movement(store: DataStore, crime_type: str, step: int | None) -> dict[str, Any]:
    _check_crime(store, crime_type)
    mv = store.movement
    if not mv.empty and crime_type != ALL:
        mv = mv[mv["crime_type"] == crime_type]
    steps = sorted(int(s) for s in mv["step"].unique()) if not mv.empty else []
    if step is None:
        step = steps[-1] if steps else 0
    elif steps and step not in steps:
        raise ValueError(f"step must be one of {steps}")
    cur = mv[mv["step"] == step] if not mv.empty else mv
    items = []
    for r in _records(cur):
        for col in ("zones", "from_cluster_ids"):
            if isinstance(r.get(col), str):
                r[col] = json.loads(r[col])
        r["label"] = store.crime_labels.get(r["crime_type"], r["crime_type"])
        items.append(r)
    summary = cur["kind"].value_counts().to_dict() if not cur.empty else {}
    shifted = cur[cur["kind"] == "SHIFTED"] if not cur.empty else cur
    return {
        "crime_type": crime_type,
        "step": step,
        "steps": steps,
        "period_end": items[0]["period_end"] if items else None,
        "analysis": _analysis(store) | {"movement_max_km": store.cfg.hotspots.movement_max_km},
        "summary": summary,
        "mean_shift_km": round(float(shifted["distance_km"].mean()), 3)
        if not shifted.empty
        else None,
        "items": items,
        "note": MOVEMENT_NOTE,
        "data_label": store.dataset_manifest["data_label"],
        "versions": versions(store),
    }


# ---------------------------------------------------------------------------- patterns


def zone_patterns(store: DataStore, zone_id: str, crime_type: str) -> dict[str, Any]:
    _check_zone(store, zone_id)
    _check_crime(store, crime_type, allow_all=False)
    a = store.analogs
    row = a[(a["zone_id"] == zone_id) & (a["crime_type"] == crime_type)]
    rec = _records(row)[0]
    for col in ("current_counts", "analogs"):
        rec[col] = json.loads(rec[col])
    lookback = store.predictions_manifest.get("pattern_lookback_windows")
    return {
        **rec,
        "label": store.crime_labels[crime_type],
        "lookback_windows": lookback,
        "window_days": store.predictions_manifest["window_days"],
        "method": "RMSE on log(1 + count) sequences; similarity = exp(-RMSE); "
        "non-overlapping top matches whose outcome precedes the current sequence.",
        "note": PATTERN_NOTE,
        "data_label": store.dataset_manifest["data_label"],
        "versions": versions(store),
    }


# ---------------------------------------------------------------------------- stations


def station_detail(store: DataStore, station_id: str, band: str = ALL) -> dict[str, Any]:
    _check_band(store, band)
    st = store.stations
    if st.empty or station_id not in set(st["station_id"]):
        raise KeyError(f"Unknown station {station_id}")
    info = st[st["station_id"] == station_id].iloc[0]
    zones = set(store.zones.loc[store.zones["station_id"] == station_id, "zone_id"])
    p = store.predictions[store.predictions["zone_id"].isin(zones)]
    if band != ALL:
        p = p[p["band"] == band]
    zc = store.zone_crime[store.zone_crime["zone_id"].isin(zones)]
    top = (
        p.sort_values("final_risk", ascending=False)
        .head(10)[
            [
                "zone_id",
                "crime_type",
                "band",
                "final_risk",
                "risk_band",
                "probability",
                "confidence",
                "crs",
                "cai",
                "hotspot_state",
            ]
        ]
        .assign(label=lambda d: d["crime_type"].map(store.crime_labels))
    )
    best = p.loc[p.groupby("zone_id")["final_risk"].idxmax()] if not p.empty else p
    zone_rows = (
        best[["zone_id", "crime_type", "band", "final_risk", "risk_band"]]
        .sort_values("final_risk", ascending=False)
        .assign(label=lambda d: d["crime_type"].map(store.crime_labels))
    )
    mix = (
        zc.groupby("crime_type")[["incidents_52w", "incidents_4w"]]
        .sum()
        .reset_index()
        .sort_values("incidents_52w", ascending=False)
    )
    mix["label"] = mix["crime_type"].map(store.crime_labels)
    alerts = zc[zc["surge_alert"]].sort_values("surge_z", ascending=False)
    return {
        "station": {
            "station_id": station_id,
            "name": info["name"],
            "latitude": float(info["latitude"]),
            "longitude": float(info["longitude"]),
            "is_synthetic": bool(info.get("is_synthetic", True)),
            "zones": sorted(zones),
        },
        "band": band,
        "as_of": store.predictions_manifest["as_of"],
        "window": window(store),
        "kpis": {
            "zones": len(zones),
            "high_risk_zones": int(
                p.loc[p["risk_band"].isin(["HIGH", "VERY HIGH"]), "zone_id"].nunique()
            ),
            "active_hotspots": int(zc["state"].isin(["ACTIVE", "PERSISTENT"]).sum()),
            "emerging_hotspots": int((zc["state"] == "EMERGING").sum()),
            "current_anomalies": int(zc["surge_alert"].sum()),
            "incidents_4w": int(zc["incidents_4w"].sum()),
        },
        "kpi_definitions": KPI_DEFINITIONS,
        "top_attention": _records(top),
        "zones": _records(zone_rows),
        "crime_mix": _records(mix),
        "lifecycle": {s: int((zc["lifecycle_stage"] == s).sum()) for s in LIFECYCLE_STAGES},
        "alerts": [
            {
                "zone_id": r.zone_id,
                "crime_type": r.crime_type,
                "label": store.crime_labels[r.crime_type],
                "current_count": int(r.surge_current_count),
                "baseline_mean": r.surge_baseline_mean,
                "z_score": r.surge_z,
            }
            for r in alerts.itertuples()
        ],
        "boundary_note": "Station areas are synthetic approximations (nearest synthetic "
        "station per zone), not official police jurisdictions.",
        "data_label": store.dataset_manifest["data_label"],
        "limitation_statement": LIMITATION_STATEMENT,
        "versions": versions(store),
    }


def station_overview(store: DataStore) -> dict[str, Any]:
    """Compact roll-up of every station for the station selector."""
    zs = zone_station(store)
    p = store.predictions.assign(station_id=lambda d: d["zone_id"].map(zs))
    zc = store.zone_crime.assign(station_id=lambda d: d["zone_id"].map(zs))
    high = p[p["risk_band"].isin(["HIGH", "VERY HIGH"])].groupby("station_id")["zone_id"].nunique()
    peak = p.groupby("station_id")["final_risk"].max()
    alerts = zc.groupby("station_id")["surge_alert"].sum()
    emerging = zc[zc["state"] == "EMERGING"].groupby("station_id").size()
    zones = store.zones["station_id"].value_counts()
    items = [
        {
            "station_id": r.station_id,
            "name": r.name,
            "zones": int(zones.get(r.station_id, 0)),
            "high_risk_zones": int(high.get(r.station_id, 0)),
            "peak_final_risk": float(peak.get(r.station_id, 0.0)),
            "surge_alerts": int(alerts.get(r.station_id, 0)),
            "emerging_hotspots": int(emerging.get(r.station_id, 0)),
        }
        for r in store.stations.itertuples()
    ]
    items.sort(key=lambda d: (-d["high_risk_zones"], -d["peak_final_risk"]))
    return {
        "items": items,
        "window": window(store),
        "data_label": store.dataset_manifest["data_label"],
        "versions": versions(store),
    }
