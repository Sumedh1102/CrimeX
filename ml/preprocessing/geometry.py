"""Small, dependency-free planar geometry helpers (city scale, WGS84 degrees)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

METERS_PER_DEG_LAT = 111_320.0


def points_in_polygon(
    lons: np.ndarray, lats: np.ndarray, polygon: Sequence[Sequence[float]]
) -> np.ndarray:
    """Vectorised even-odd ray casting. ``polygon`` is a ring of [lon, lat] vertices."""
    lons = np.asarray(lons, dtype=float)
    lats = np.asarray(lats, dtype=float)
    poly = np.asarray(polygon, dtype=float)
    if len(poly) < 3:
        raise ValueError("Polygon needs at least 3 vertices")
    inside = np.zeros(lons.shape, dtype=bool)
    x0, y0 = poly[-1]
    for x1, y1 in poly:
        crosses = (y1 > lats) != (y0 > lats)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at = (x0 - x1) * (lats - y1) / (y0 - y1) + x1
        inside ^= crosses & (lons < x_at)
        x0, y0 = x1, y1
    return inside


def meters_per_deg_lon(lat: float) -> float:
    return METERS_PER_DEG_LAT * float(np.cos(np.radians(lat)))
