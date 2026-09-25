"""Version identifiers recorded with every dataset, model and prediction."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pandas as pd

# Bump when the definition of any model feature or score component changes.
FEATURE_VERSION = "FeatureSet-1.0"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def short_hash(data: bytes, n: int = 8) -> str:
    return hashlib.sha256(data).hexdigest()[:n]


def dataset_version(incidents: pd.DataFrame, as_of: date) -> str:
    """Content hash of the cleaned incident table, e.g. ``Dataset-2026-09-01-3fa2c1d0``."""
    cols = ["incident_id", "timestamp", "crime_type", "latitude", "longitude", "source"]
    payload = incidents[cols].to_csv(index=False).encode()
    return f"Dataset-{as_of.isoformat()}-{short_hash(payload)}"


def feature_version(config_fingerprint: str) -> str:
    return f"{FEATURE_VERSION}-{config_fingerprint[:6]}"
