"""Read-only access to pipeline outputs (processed data, model bundle metadata, predictions).

The MVP serves versioned Parquet/JSON artifacts written by the ML pipeline; the frontend
never re-derives scores. A PostGIS-backed repository can replace this class later with
the same interface.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import pandas as pd

from ml.config import PlatformConfig, load_config
from ml.data.official.load import HEADS_LABELS, OfficialStatement
from ml.preprocessing.grid import Grid


class NotReadyError(RuntimeError):
    """Pipeline outputs are missing (run `make pipeline`)."""


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise NotReadyError(f"Missing {path}. Run `make pipeline` to generate it.")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise NotReadyError(f"Missing {path}. Run `make pipeline` to generate it.")
    return pd.read_parquet(path)


def _latest(directory: Path) -> Path:
    pointer = directory / "LATEST"
    if not pointer.exists():
        raise NotReadyError(f"No LATEST pointer in {directory}. Run `make pipeline`.")
    return directory / pointer.read_text(encoding="utf-8").strip()


@dataclass
class DataStore:
    cfg: PlatformConfig

    @classmethod
    def from_config_path(cls, path: Path | None) -> DataStore:
        return cls(load_config(path))

    # ---------------------------------------------------------------- reference data
    @cached_property
    def grid(self) -> Grid:
        return Grid.build(self.cfg.region, self.cfg.grid)

    @cached_property
    def official(self) -> OfficialStatement:
        return OfficialStatement.load(self.cfg.paths.official_statement)

    @property
    def crime_labels(self) -> dict[str, str]:
        return {c: HEADS_LABELS.get(c, c) for c in self.cfg.crime_types.modelled}

    @property
    def band_labels(self) -> dict[str, str]:
        return {b.code: b.label for b in self.cfg.time.bands}

    # ---------------------------------------------------------------- processed data
    @cached_property
    def incidents(self) -> pd.DataFrame:
        return _read_parquet(self.cfg.paths.processed_dir / "incidents.parquet")

    @cached_property
    def zones(self) -> pd.DataFrame:
        return _read_parquet(self.cfg.paths.processed_dir / "zones.parquet")

    @cached_property
    def stations(self) -> pd.DataFrame:
        path = self.cfg.paths.processed_dir / "stations.parquet"
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()

    @cached_property
    def dataset_manifest(self) -> dict[str, Any]:
        return _read_json(self.cfg.paths.processed_dir / "dataset_manifest.json")

    @cached_property
    def quality_report(self) -> dict[str, Any]:
        return _read_json(self.cfg.paths.processed_dir / "quality_report.json")

    @cached_property
    def zones_geojson(self) -> dict[str, Any]:
        return _read_json(self.cfg.paths.processed_dir / "zones.geojson")

    # ---------------------------------------------------------------- model + predictions
    @cached_property
    def model_dir(self) -> Path:
        return _latest(self.cfg.paths.artifacts_dir / "models")

    @cached_property
    def model_metadata(self) -> dict[str, Any]:
        return _read_json(self.model_dir / "metadata.json")

    @cached_property
    def model_metrics(self) -> dict[str, Any]:
        return _read_json(self.model_dir / "metrics.json")

    @cached_property
    def predictions_dir(self) -> Path:
        return _latest(self.cfg.paths.artifacts_dir / "predictions")

    @cached_property
    def predictions_manifest(self) -> dict[str, Any]:
        return _read_json(self.predictions_dir / "manifest.json")

    @cached_property
    def predictions(self) -> pd.DataFrame:
        return _read_parquet(self.predictions_dir / "predictions.parquet")

    @cached_property
    def zone_crime(self) -> pd.DataFrame:
        return _read_parquet(self.predictions_dir / "zone_crime.parquet")

    @cached_property
    def crs_history(self) -> pd.DataFrame:
        return _read_parquet(self.predictions_dir / "crs_history.parquet")

    @cached_property
    def lifecycle(self) -> pd.DataFrame:
        return _read_parquet(self.predictions_dir / "lifecycle.parquet")

    @cached_property
    def movement(self) -> pd.DataFrame:
        return _read_parquet(self.predictions_dir / "movement.parquet")

    @cached_property
    def analogs(self) -> pd.DataFrame:
        return _read_parquet(self.predictions_dir / "analogs.parquet")

    @property
    def as_of(self) -> pd.Timestamp:
        return pd.Timestamp(self.predictions_manifest["as_of"])

    def check_ready(self) -> None:
        for prop in ("incidents", "predictions", "zone_crime", "model_metadata"):
            getattr(self, prop)


_store: DataStore | None = None
_lock = threading.Lock()


def get_store() -> DataStore:
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                from backend.app.settings import get_settings

                _store = DataStore.from_config_path(get_settings().config_path)
    return _store


def set_store(store: DataStore | None) -> None:
    """Replace the process-wide store (tests, or after re-running the pipeline)."""
    global _store
    _store = store
