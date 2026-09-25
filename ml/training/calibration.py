"""Isotonic probability calibration, stored as plain JSON (no pickles)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression


@dataclass
class IsotonicCalibrator:
    x: list[float]
    y: list[float]

    @classmethod
    def fit(cls, raw: np.ndarray, y: np.ndarray) -> IsotonicCalibrator:
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        iso.fit(raw.astype(float), y.astype(float))
        return cls(x=iso.X_thresholds_.tolist(), y=iso.y_thresholds_.tolist())

    def predict(self, raw: np.ndarray) -> np.ndarray:
        # identical to IsotonicRegression.predict with out_of_bounds="clip"
        return np.interp(np.asarray(raw, dtype=float), self.x, self.y)

    def to_json(self) -> dict:
        return {"method": "isotonic", "x": self.x, "y": self.y}

    @classmethod
    def from_json(cls, d: dict) -> IsotonicCalibrator:
        return cls(x=list(d["x"]), y=list(d["y"]))
