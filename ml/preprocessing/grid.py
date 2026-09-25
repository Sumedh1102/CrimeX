"""Regular square grid over the study region; each active cell is one analysis zone.

Rows are counted from the north edge so that zone numbers (Z001, Z002, ...) follow
reading order on a north-up map. A cell is active when at least
``min_land_fraction`` of its sample points are on land (1 km global land mask) and
inside the region's clip outline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

import numpy as np
import pandas as pd
from global_land_mask import globe

from ml.config import GridConfig, RegionConfig
from ml.preprocessing.geometry import METERS_PER_DEG_LAT, meters_per_deg_lon, points_in_polygon


@dataclass(frozen=True)
class Grid:
    north: float
    west: float
    dlat: float
    dlon: float
    n_rows: int
    n_cols: int
    cell_size_m: float
    rows: np.ndarray  # (Z,) row of each active zone
    cols: np.ndarray  # (Z,) col of each active zone
    land_fraction: np.ndarray  # (Z,)
    zone_ids: tuple[str, ...] = field(default=())

    # ----------------------------------------------------------------- construction
    @classmethod
    def build(cls, region: RegionConfig, cfg: GridConfig) -> Grid:
        b = region.bbox
        mid_lat = (b.south + b.north) / 2
        dlat = cfg.cell_size_m / METERS_PER_DEG_LAT
        dlon = cfg.cell_size_m / meters_per_deg_lon(mid_lat)
        n_rows = math.ceil((b.north - b.south) / dlat)
        n_cols = math.ceil((b.east - b.west) / dlon)

        s = cfg.samples_per_axis
        offsets = (np.arange(s) + 0.5) / s
        rr, cc = np.meshgrid(np.arange(n_rows), np.arange(n_cols), indexing="ij")
        # sample points: (n_rows, n_cols, s, s)
        lat = b.north - (rr[..., None, None] + offsets[:, None]) * dlat
        lon = b.west + (cc[..., None, None] + offsets[None, :]) * dlon
        lat = np.broadcast_to(lat, (n_rows, n_cols, s, s))
        lon = np.broadcast_to(lon, (n_rows, n_cols, s, s))
        on_land = globe.is_land(lat.ravel(), lon.ravel()).reshape(lat.shape)
        in_outline = points_in_polygon(lon.ravel(), lat.ravel(), region.outline).reshape(lat.shape)
        frac = (on_land & in_outline).mean(axis=(2, 3))
        active = frac >= region.min_land_fraction
        rows, cols = np.nonzero(active)  # row-major == reading order from the north-west
        zone_ids = tuple(f"Z{i + 1:03d}" for i in range(len(rows)))
        return cls(
            north=b.north,
            west=b.west,
            dlat=dlat,
            dlon=dlon,
            n_rows=n_rows,
            n_cols=n_cols,
            cell_size_m=cfg.cell_size_m,
            rows=rows.astype(np.int32),
            cols=cols.astype(np.int32),
            land_fraction=frac[active].astype(np.float32),
            zone_ids=zone_ids,
        )

    # ------------------------------------------------------------------- properties
    @property
    def n_zones(self) -> int:
        return len(self.zone_ids)

    @property
    def cell_km(self) -> float:
        return self.cell_size_m / 1000.0

    @cached_property
    def lookup(self) -> np.ndarray:
        """(n_rows, n_cols) array of zone index, -1 where the cell is inactive."""
        lk = np.full((self.n_rows, self.n_cols), -1, dtype=np.int32)
        lk[self.rows, self.cols] = np.arange(self.n_zones, dtype=np.int32)
        return lk

    @cached_property
    def zone_index(self) -> dict[str, int]:
        return {z: i for i, z in enumerate(self.zone_ids)}

    @cached_property
    def centroid_lat(self) -> np.ndarray:
        return self.north - (self.rows + 0.5) * self.dlat

    @cached_property
    def centroid_lon(self) -> np.ndarray:
        return self.west + (self.cols + 0.5) * self.dlon

    # ------------------------------------------------------------------ geometry ops
    def cell_of(self, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        r = np.floor((self.north - np.asarray(lat, dtype=float)) / self.dlat)
        c = np.floor((np.asarray(lon, dtype=float) - self.west) / self.dlon)
        return r, c

    def point_to_zone_index(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        """Zone index for each point, -1 when outside the active grid (or NaN)."""
        r, c = self.cell_of(lat, lon)
        ok = np.isfinite(r) & np.isfinite(c)
        ok &= (r >= 0) & (r < self.n_rows) & (c >= 0) & (c < self.n_cols)
        out = np.full(r.shape, -1, dtype=np.int32)
        out[ok] = self.lookup[r[ok].astype(int), c[ok].astype(int)]
        return out

    def cell_bounds(self, i: int) -> tuple[float, float, float, float]:
        """(south, north, west, east) of zone ``i``."""
        north = self.north - self.rows[i] * self.dlat
        west = self.west + self.cols[i] * self.dlon
        return north - self.dlat, north, west, west + self.dlon

    def cell_polygon(self, i: int) -> list[list[float]]:
        s, n, w, e = self.cell_bounds(i)
        return [[w, s], [e, s], [e, n], [w, n], [w, s]]

    def neighbors(self, radius_cells: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Pairs (i, j, distance_km) of distinct zones within Chebyshev ``radius_cells``."""
        ii, jj, dd = [], [], []
        for dr in range(-radius_cells, radius_cells + 1):
            for dc in range(-radius_cells, radius_cells + 1):
                if dr == 0 and dc == 0:
                    continue
                r2, c2 = self.rows + dr, self.cols + dc
                ok = (r2 >= 0) & (r2 < self.n_rows) & (c2 >= 0) & (c2 < self.n_cols)
                j = np.full(self.n_zones, -1, dtype=np.int32)
                j[ok] = self.lookup[r2[ok], c2[ok]]
                keep = j >= 0
                ii.append(np.nonzero(keep)[0])
                jj.append(j[keep])
                dd.append(np.full(keep.sum(), self.cell_km * math.hypot(dr, dc)))
        return (
            np.concatenate(ii).astype(np.int32),
            np.concatenate(jj).astype(np.int32),
            np.concatenate(dd),
        )

    def binary_weights(self, radius_cells: int, include_self: bool) -> np.ndarray:
        """Dense (Z, Z) 0/1 contiguity matrix (queen contiguity for radius 1)."""
        w = np.zeros((self.n_zones, self.n_zones), dtype=np.float64)
        i, j, _ = self.neighbors(radius_cells)
        w[i, j] = 1.0
        if include_self:
            np.fill_diagonal(w, 1.0)
        return w

    def inverse_distance_weights(self, radius_cells: int, eps_km: float) -> np.ndarray:
        """Dense (Z, Z) matrix with w_zj = 1/(distance + eps) for neighbours, 0 elsewhere."""
        w = np.zeros((self.n_zones, self.n_zones), dtype=np.float64)
        i, j, d = self.neighbors(radius_cells)
        w[i, j] = 1.0 / (d + eps_km)
        return w

    # ------------------------------------------------------------------- export
    def zones_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "zone_id": list(self.zone_ids),
                "row": self.rows,
                "col": self.cols,
                "centroid_lat": self.centroid_lat.round(6),
                "centroid_lon": self.centroid_lon.round(6),
                "land_fraction": self.land_fraction.round(3),
            }
        )

    def to_geojson(self, properties: pd.DataFrame | None = None) -> dict[str, Any]:
        props = properties.set_index("zone_id") if properties is not None else None
        features = []
        for i, zid in enumerate(self.zone_ids):
            p: dict[str, Any] = {"zone_id": zid, "row": int(self.rows[i]), "col": int(self.cols[i])}
            if props is not None and zid in props.index:
                for k, v in props.loc[zid].items():
                    p[k] = v.item() if hasattr(v, "item") else v
            features.append(
                {
                    "type": "Feature",
                    "id": i,
                    "properties": p,
                    "geometry": {"type": "Polygon", "coordinates": [self.cell_polygon(i)]},
                }
            )
        return {"type": "FeatureCollection", "features": features}
