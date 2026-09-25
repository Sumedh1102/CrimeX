"""Data-quality monitor for incident records.

Every figure in the report is computed from the data; nothing is estimated. Each
rejected row is attributed to the first failing check (in ``CHECK_ORDER``) so the
per-check counts add up to ``rows_in - rows_out``; ``rows_with_issue`` additionally
counts every row that fails a check, regardless of order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from ml.config import TimeBand
from ml.preprocessing.grid import Grid

CHECK_LABELS = {
    "duplicate_record": "Duplicate records",
    "missing_timestamp": "Missing timestamps",
    "invalid_timestamp": "Unparseable timestamps",
    "missing_location": "Missing locations",
    "invalid_coordinates": "Invalid coordinates",
    "unknown_crime_type": "Unknown crime types",
    "after_forecast_origin": "Timestamps at/after the forecast origin",
}
CHECK_ORDER = list(CHECK_LABELS)

REQUIRED_COLUMNS = ["incident_id", "timestamp", "crime_type", "latitude", "longitude"]


@dataclass
class QualityResult:
    clean: pd.DataFrame
    report: dict[str, Any]


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype("string").str.strip() == "")


def assign_band(hours: np.ndarray, bands: list[TimeBand]) -> np.ndarray:
    lut = np.empty(24, dtype=object)
    for b in bands:
        lut[b.start_hour : b.end_hour] = b.code
    return lut[hours]


def run_quality_checks(
    raw: pd.DataFrame,
    grid: Grid,
    crime_types: list[str],
    as_of: date,
    bands: list[TimeBand],
) -> QualityResult:
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing_cols:
        raise ValueError(f"Incident data is missing required columns: {missing_cols}")

    df = raw.copy().reset_index(drop=True)
    n = len(df)
    fails: dict[str, pd.Series] = {}

    fails["duplicate_record"] = df["incident_id"].duplicated(keep="first")

    ts_blank = _blank(df["timestamp"])
    ts = pd.to_datetime(df["timestamp"].where(~ts_blank), errors="coerce", format="ISO8601")
    fails["missing_timestamp"] = ts_blank
    fails["invalid_timestamp"] = ~ts_blank & ts.isna()

    lat = pd.to_numeric(df["latitude"], errors="coerce")
    lon = pd.to_numeric(df["longitude"], errors="coerce")
    loc_missing = lat.isna() | lon.isna()
    fails["missing_location"] = loc_missing
    zone_idx = grid.point_to_zone_index(lat.to_numpy(), lon.to_numpy())
    out_of_range = ~lat.between(-90, 90) | ~lon.between(-180, 180)
    null_island = (lat == 0) & (lon == 0)
    outside_region = pd.Series(zone_idx < 0, index=df.index)
    fails["invalid_coordinates"] = ~loc_missing & (out_of_range | null_island | outside_region)

    fails["unknown_crime_type"] = ~df["crime_type"].isin(crime_types)
    fails["after_forecast_origin"] = ts.notna() & (ts >= pd.Timestamp(as_of))

    first_fail = pd.Series(pd.NA, index=df.index, dtype="string")
    for check in CHECK_ORDER:
        first_fail = first_fail.mask(first_fail.isna() & fails[check], check)
    keep = first_fail.isna()

    provided_zone = df.get("zone_id")
    recomputed = pd.Series(
        np.where(
            zone_idx >= 0, np.array(grid.zone_ids, dtype=object)[np.maximum(zone_idx, 0)], None
        ),
        index=df.index,
    )
    zone_mismatch = 0
    if provided_zone is not None:
        zone_mismatch = int((keep & provided_zone.notna() & (provided_zone != recomputed)).sum())

    source_missing = 0
    if "source" in df.columns:
        source_missing = int((keep & _blank(df["source"])).sum())

    clean = pd.DataFrame(
        {
            "incident_id": df["incident_id"],
            "timestamp": ts,
            "crime_type": df["crime_type"],
            "latitude": lat,
            "longitude": lon,
            "zone_id": recomputed,
            "zone_idx": zone_idx,
            "police_station_id": df.get("police_station_id"),
            "severity": pd.to_numeric(df.get("severity"), errors="coerce"),
            "source": df["source"].where(~_blank(df["source"]), "UNKNOWN")
            if "source" in df.columns
            else "UNKNOWN",
        }
    )[keep.to_numpy()]
    clean = clean.sort_values(["timestamp", "incident_id"], kind="stable").reset_index(drop=True)
    hours = clean["timestamp"].dt.hour.to_numpy()
    clean["hour"] = hours.astype(np.int16)
    clean["day_of_week"] = clean["timestamp"].dt.dayofweek.astype(np.int16)
    clean["month"] = clean["timestamp"].dt.month.astype(np.int16)
    clean["is_weekend"] = clean["day_of_week"] >= 5
    clean["band"] = assign_band(hours, bands)
    clean["zone_idx"] = clean["zone_idx"].astype(np.int32)

    counts_first = first_fail.value_counts().to_dict()
    checks = []
    for check in CHECK_ORDER:
        c = int(counts_first.get(check, 0))
        checks.append(
            {
                "id": check,
                "label": CHECK_LABELS[check],
                "rows_rejected": c,
                "rate": round(c / n, 6) if n else 0.0,
                "rows_with_issue": int(fails[check].sum()),
                "action": "dropped",
            }
        )
    checks.append(
        {
            "id": "zone_id_mismatch",
            "label": "Provided zone_id differs from the zone of the coordinates",
            "rows_rejected": 0,
            "rate": round(zone_mismatch / n, 6) if n else 0.0,
            "rows_with_issue": zone_mismatch,
            "action": "corrected (zone recomputed from coordinates)",
        }
    )
    checks.append(
        {
            "id": "missing_source",
            "label": "Missing source label",
            "rows_rejected": 0,
            "rate": round(source_missing / n, 6) if n else 0.0,
            "rows_with_issue": source_missing,
            "action": "flagged (source set to UNKNOWN)",
        }
    )
    report = {
        "rows_in": int(n),
        "rows_out": int(keep.sum()),
        "rows_rejected": int(n - keep.sum()),
        "checks": checks,
        "sources": clean["source"].value_counts().to_dict(),
        "crime_type_counts": clean["crime_type"].value_counts().to_dict(),
        "timestamp_range": {
            "min": clean["timestamp"].min().isoformat() if len(clean) else None,
            "max": clean["timestamp"].max().isoformat() if len(clean) else None,
        },
    }
    return QualityResult(clean=clean, report=report)
