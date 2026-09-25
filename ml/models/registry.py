"""Versioned model bundles on disk (JSON only; no pickled objects).

artifacts/models/<model_version>/
    classifier.json      XGBoost booster: P(>=1 incident in window and band), uncalibrated
    regressor.json       XGBoost booster: expected incident count (Poisson)
    calibrator.json      isotonic map raw probability -> calibrated probability
    scoring_state.json   percentile references (F, S) and tuned recency half-lives (R)
    metadata.json        versions, periods, parameters, feature list
    metrics.json         validation and test metrics for every compared model
artifacts/models/LATEST  name of the most recent bundle
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb

from ml.features.engine import FittedScoringState
from ml.training.calibration import IsotonicCalibrator


@dataclass
class ModelBundle:
    model_version: str
    classifier: xgb.Booster
    regressor: xgb.Booster
    calibrator: IsotonicCalibrator
    scoring_state: FittedScoringState
    metadata: dict[str, Any]
    metrics: dict[str, Any]

    @property
    def feature_names(self) -> list[str]:
        return list(self.metadata["feature_names"])

    def _dmatrix(self, X: np.ndarray) -> xgb.DMatrix:
        return xgb.DMatrix(X, feature_names=self.feature_names)

    def predict_raw_probability(self, X: np.ndarray) -> np.ndarray:
        return self.classifier.predict(self._dmatrix(X))

    def predict_probability(self, X: np.ndarray) -> np.ndarray:
        return self.calibrator.predict(self.predict_raw_probability(X))

    def predict_count(self, X: np.ndarray) -> np.ndarray:
        return self.regressor.predict(self._dmatrix(X))

    def shap_values(self, X: np.ndarray) -> np.ndarray:
        """TreeSHAP contributions in log-odds space; last column is the bias term."""
        return self.classifier.predict(self._dmatrix(X), pred_contribs=True)

    # ------------------------------------------------------------------ persistence
    def save(self, models_dir: Path) -> Path:
        d = models_dir / self.model_version
        d.mkdir(parents=True, exist_ok=True)
        self.classifier.save_model(d / "classifier.json")
        self.regressor.save_model(d / "regressor.json")
        _write(d / "calibrator.json", self.calibrator.to_json())
        _write(d / "scoring_state.json", self.scoring_state.to_json())
        _write(d / "metadata.json", self.metadata)
        _write(d / "metrics.json", self.metrics)
        (models_dir / "LATEST").write_text(self.model_version + "\n", encoding="utf-8")
        return d

    @classmethod
    def load(cls, models_dir: Path, version: str | None = None) -> ModelBundle:
        version = version or (models_dir / "LATEST").read_text(encoding="utf-8").strip()
        d = models_dir / version
        clf = xgb.Booster()
        clf.load_model(d / "classifier.json")
        reg = xgb.Booster()
        reg.load_model(d / "regressor.json")
        return cls(
            model_version=version,
            classifier=clf,
            regressor=reg,
            calibrator=IsotonicCalibrator.from_json(_read(d / "calibrator.json")),
            scoring_state=FittedScoringState.from_json(_read(d / "scoring_state.json")),
            metadata=_read(d / "metadata.json"),
            metrics=_read(d / "metrics.json"),
        )


def _write(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=_json_default), encoding="utf-8")


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_default(o: Any) -> Any:
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Not JSON serialisable: {type(o)}")
