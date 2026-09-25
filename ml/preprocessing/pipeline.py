"""Raw incidents -> data quality -> gridding -> processed, versioned dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.config import SYNTHETIC_LABEL, SYNTHETIC_SOURCE, PlatformConfig
from ml.preprocessing.grid import Grid
from ml.preprocessing.quality import run_quality_checks
from ml.versioning import dataset_version, utc_now

RAW_INCIDENTS = "incidents_synthetic.csv"


def _zone_stations(grid: Grid, clean: pd.DataFrame, raw_dir: Path) -> pd.Series:
    """Zone -> police station: explicit mapping when provided, else majority of incidents."""
    mapping_file = raw_dir / "zone_station_synthetic.csv"
    if mapping_file.exists():
        m = pd.read_csv(mapping_file).set_index("zone_id")["police_station_id"]
        return pd.Series([m.get(z) for z in grid.zone_ids], index=list(grid.zone_ids))
    votes = (
        clean.dropna(subset=["police_station_id"])
        .groupby("zone_id")["police_station_id"]
        .agg(lambda s: s.value_counts().index[0])
    )
    return pd.Series([votes.get(z) for z in grid.zone_ids], index=list(grid.zone_ids))


def preprocess(cfg: PlatformConfig, raw_dir: Path | None = None) -> dict[str, Any]:
    raw_dir = raw_dir or cfg.paths.raw_dir
    out_dir = cfg.paths.processed_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    grid = Grid.build(cfg.region, cfg.grid)
    raw = pd.read_csv(raw_dir / RAW_INCIDENTS, dtype=str, keep_default_na=False)
    result = run_quality_checks(raw, grid, cfg.crime_types.modelled, cfg.time.as_of, cfg.time.bands)
    clean = result.clean

    zones = grid.zones_frame()
    zones["station_id"] = _zone_stations(grid, clean, raw_dir).to_numpy()
    stations_file = raw_dir / "police_stations_synthetic.csv"
    stations = pd.read_csv(stations_file) if stations_file.exists() else pd.DataFrame()

    version = dataset_version(clean, cfg.time.as_of)
    sources = sorted(clean["source"].unique().tolist())
    is_synthetic = sources == [SYNTHETIC_SOURCE]
    manifest = {
        "dataset_version": version,
        "created_at": utc_now(),
        "as_of": cfg.time.as_of.isoformat(),
        "sources": sources,
        "is_synthetic": is_synthetic,
        "data_label": SYNTHETIC_LABEL if is_synthetic else "Incident data",
        "rows": int(len(clean)),
        "timestamp_range": result.report["timestamp_range"],
        "n_zones": grid.n_zones,
        "crime_types": sorted(clean["crime_type"].unique().tolist()),
        "grid_fingerprint": cfg.fingerprint("region", "grid"),
        "cell_size_m": cfg.grid.cell_size_m,
    }
    report = {"dataset_version": version, "generated_at": manifest["created_at"], **result.report}

    clean.to_parquet(out_dir / "incidents.parquet", index=False)
    zones.to_parquet(out_dir / "zones.parquet", index=False)
    if len(stations):
        stations.to_parquet(out_dir / "stations.parquet", index=False)
    geo = grid.to_geojson(zones[["zone_id", "station_id", "land_fraction"]])
    (out_dir / "zones.geojson").write_text(json.dumps(geo), encoding="utf-8")
    (out_dir / "quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"manifest": manifest, "quality": report, "zones": zones}


def load_processed(cfg: PlatformConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    d = cfg.paths.processed_dir
    incidents = pd.read_parquet(d / "incidents.parquet")
    zones = pd.read_parquet(d / "zones.parquet")
    manifest = json.loads((d / "dataset_manifest.json").read_text(encoding="utf-8"))
    incidents["zone_idx"] = incidents["zone_idx"].astype(np.int32)
    return incidents, zones, manifest
