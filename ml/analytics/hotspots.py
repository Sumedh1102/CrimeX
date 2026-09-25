"""Hotspot Detection Engine: Gi* hotspot maps for any crime type and period."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from ml.analytics.gistar import benjamini_hochberg, classify, gi_star, p_values
from ml.config import HotspotConfig
from ml.preprocessing.grid import Grid


def zone_counts(
    incidents: pd.DataFrame,
    grid: Grid,
    start: datetime | pd.Timestamp,
    end: datetime | pd.Timestamp,
    crime_type: str | None = None,
    band: str | None = None,
) -> np.ndarray:
    """Incidents per zone in [start, end), optionally for one crime type / band."""
    m = (incidents["timestamp"] >= pd.Timestamp(start)) & (
        incidents["timestamp"] < pd.Timestamp(end)
    )
    if crime_type:
        m &= incidents["crime_type"] == crime_type
    if band:
        m &= incidents["band"] == band
    idx = incidents.loc[m, "zone_idx"].to_numpy()
    return np.bincount(idx, minlength=grid.n_zones)


def hotspot_map(counts: np.ndarray, grid: Grid, cfg: HotspotConfig) -> pd.DataFrame:
    w = grid.binary_weights(cfg.gi_neighbor_radius_cells, include_self=True)
    z = gi_star(counts, w)
    p = p_values(z)
    significant = benjamini_hochberg(p) if cfg.fdr_correction else None
    area_km2 = (grid.cell_size_m / 1000.0) ** 2 * grid.land_fraction
    return pd.DataFrame(
        {
            "zone_id": list(grid.zone_ids),
            "count": counts.astype(int),
            "density_per_km2": np.round(counts / np.maximum(area_km2, 1e-9), 3),
            "gi_z": np.round(z, 3),
            "gi_p": np.round(p, 5),
            "hotspot_class": classify(z, significant),
        }
    )
