"""Percentile normalisation against a reference distribution fitted on training data.

Used for the F (frequency) and S (neighbour pressure) components. The reference is a
quantile grid per (component, crime type, band) fitted on training-period origins only,
then stored with the model so inference uses exactly the same scale. The transform is the
strict empirical CDF P(X_ref < x): no activity maps to 0, the top of the reference to ~1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PercentileReference:
    grids: dict[str, list[float]] = field(default_factory=dict)

    @staticmethod
    def key(component: str, crime_type: str, band: str) -> str:
        return f"{component}|{crime_type}|{band}"

    @classmethod
    def fit(
        cls,
        values: dict[str, np.ndarray],
        origin_mask: np.ndarray,
        crime_types: tuple[str, ...],
        bands: tuple[str, ...],
        n_points: int,
    ) -> PercentileReference:
        """``values[name]`` has shape (Z, C, B, K); only origins where ``origin_mask`` is set."""
        q = np.linspace(0.0, 1.0, n_points)
        grids: dict[str, list[float]] = {}
        for name, arr in values.items():
            for ci, c in enumerate(crime_types):
                for bi, b in enumerate(bands):
                    sample = arr[:, ci, bi, :][:, origin_mask].ravel()
                    if sample.size == 0:
                        raise ValueError("Empty reference sample")
                    grids[cls.key(name, c, b)] = np.quantile(sample, q).round(6).tolist()
        return cls(grids)

    def transform(
        self, name: str, arr: np.ndarray, crime_types: tuple[str, ...], bands: tuple[str, ...]
    ) -> np.ndarray:
        """Map raw values of shape (Z, C, B, ...) to [0, 1]."""
        out = np.empty(arr.shape, dtype=np.float32)
        for ci, c in enumerate(crime_types):
            for bi, b in enumerate(bands):
                grid = np.asarray(self.grids[self.key(name, c, b)])
                out[:, ci, bi] = np.searchsorted(grid, arr[:, ci, bi], side="left") / len(grid)
        return out

    def to_json(self) -> dict[str, list[float]]:
        return self.grids

    @classmethod
    def from_json(cls, data: dict[str, list[float]]) -> PercentileReference:
        return cls(dict(data))
