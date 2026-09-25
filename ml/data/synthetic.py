"""Synthetic incident-level generator (SYNTHETIC / DEMONSTRATION DATA).

What is anchored to official data
    The expected city-wide daily volume of every modelled head comes from the IPC table
    of the official statement (registered counts; see ``anchored_daily_rates``).

What is assumed (documented in ``configs/default.yaml -> synthetic``)
    Where incidents happen (smooth latent activity / place-type fields), hour-of-day and
    weekday profiles, and the planted patterns: persistent, seasonal, emerging and
    declining hotspots, short surges, and uniform background noise.

The planted patterns are written to a separate ground-truth file for evaluation only.
Analytics and models never read the generator's settings or ground truth; they must
rediscover the patterns from the incidents.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from global_land_mask import globe
from scipy.ndimage import gaussian_filter
from sklearn.cluster import KMeans

from ml.config import SYNTHETIC_LABEL, SYNTHETIC_SOURCE, CrimeProfile, PlatformConfig
from ml.data.official.load import OfficialStatement
from ml.preprocessing.geometry import points_in_polygon
from ml.preprocessing.grid import Grid

# Keep generated points this far (~2 m) inside their cell so 6-decimal rounding of the
# published coordinates can never move them into a neighbouring zone.
_EDGE_MARGIN_DEG = 2e-5

INCIDENT_COLUMNS = [
    "incident_id",
    "timestamp",
    "crime_type",
    "latitude",
    "longitude",
    "zone_id",
    "police_station_id",
    "severity",
    "source",
    "day_of_week",
    "hour",
    "month",
    "is_weekend",
]


# --------------------------------------------------------------------------- anchoring


def _period(stmt: OfficialStatement, key: str) -> tuple[date, date]:
    p = stmt.periods[key]
    return date.fromisoformat(p["start"]), date.fromisoformat(p["end"])


def anchored_daily_rates(
    stmt: OfficialStatement, codes: list[str], days: pd.DatetimeIndex
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Expected city-wide incidents per day for each head, shape (C, D).

    Official windows: PY (Jan-Aug 2025), CY - PM - CM (Jan-Jun 2026), PM (Jul 2026),
    CM (Aug 2026). Before PY the PY rate is held (assumption); between PY and CY the rate
    is interpolated linearly (assumption); after CM the CM rate is held (assumption).
    """
    py0, py1 = _period(stmt, "PY")
    cy0, _ = _period(stmt, "CY")
    pm0, pm1 = _period(stmt, "PM")
    cm0, cm1 = _period(stmt, "CM")
    n_py = (py1 - py0).days + 1
    n_h1 = (pm0 - cy0).days
    n_pm = (pm1 - pm0).days + 1
    n_cm = (cm1 - cm0).days + 1

    d = days.date
    rates = np.zeros((len(codes), len(days)))
    table = []
    for ci, code in enumerate(codes):
        py = stmt.ipc_registered(code, "PY")
        cy = stmt.ipc_registered(code, "CY")
        pm = stmt.ipc_registered(code, "PM")
        cm = stmt.ipc_registered(code, "CM")
        h1 = cy - pm - cm
        if h1 < 0:
            raise ValueError(f"{code}: CY - PM - CM is negative in the official data")
        r_py, r_h1, r_pm, r_cm = py / n_py, h1 / n_h1, pm / n_pm, cm / n_cm
        r = np.full(len(days), r_py)
        gap = np.array([(py1 < x < cy0) for x in d])
        if gap.any():
            frac = np.array([(x - py1).days / (cy0 - py1).days for x in d[gap]])
            r[gap] = r_py + frac * (r_h1 - r_py)
        r[np.array([(cy0 <= x < pm0) for x in d])] = r_h1
        r[np.array([(pm0 <= x <= pm1) for x in d])] = r_pm
        r[np.array([x >= cm0 for x in d])] = r_cm
        rates[ci] = r
        table.append(
            {
                "crime_type": code,
                "official_registered": {"PY": py, "CY": cy, "PM": pm, "CM": cm},
                "daily_rate": {
                    "jan_aug_2025": round(r_py, 4),
                    "jan_jun_2026_derived": round(r_h1, 4),
                    "jul_2026": round(r_pm, 4),
                    "aug_2026": round(r_cm, 4),
                },
            }
        )
    return rates, table


# ------------------------------------------------------------------------ patterns


@dataclass
class Hotspot:
    id: str
    kind: str  # persistent | seasonal | emerging | declining
    crime_type: str
    center_zone: str
    zones: list[str]
    center_share: float
    peak_hour: float
    focal_lat: float
    focal_lon: float
    params: dict[str, Any] = field(default_factory=dict)
    # not serialised
    zone_idx: np.ndarray = field(default=None, repr=False)
    zone_weight: np.ndarray = field(default=None, repr=False)
    profile: np.ndarray = field(default=None, repr=False)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("zone_idx", "zone_weight", "profile"):
            d.pop(k)
        return d


@dataclass
class Anomaly:
    id: str
    crime_type: str
    zone: str
    start: str
    end: str
    extra_daily_rate: float
    zone_idx: int = field(default=-1, repr=False)
    day0: int = field(default=0, repr=False)
    day1: int = field(default=0, repr=False)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("zone_idx", "day0", "day1"):
            d.pop(k)
        return d


def hour_distribution(
    peaks: list[tuple[float, float, float]], allowed: tuple[int, int] | None, floor: float = 0.03
) -> np.ndarray:
    """Probability over the 24 hours from circular Gaussian peaks (hour, width, weight)."""
    h = np.arange(24) + 0.5
    p = np.zeros(24)
    for peak, width, weight in peaks:
        delta = np.minimum(np.abs(h - peak), 24 - np.abs(h - peak))
        p += weight * np.exp(-0.5 * (delta / width) ** 2)
    p += floor * p.mean()
    if allowed is not None:
        start, end = allowed
        hours = np.arange(24)
        mask = (hours >= start) & (hours < end) if start < end else (hours >= start) | (hours < end)
        p = np.where(mask, p, 0.0)
    return p / p.sum()


def _smooth_field(rng: np.random.Generator, grid: Grid, sigma: float) -> np.ndarray:
    raw = gaussian_filter(rng.standard_normal((grid.n_rows, grid.n_cols)), sigma=sigma)
    vals = raw[grid.rows, grid.cols]
    return (vals - vals.mean()) / (vals.std() + 1e-12)


class SyntheticGenerator:
    def __init__(self, cfg: PlatformConfig, grid: Grid, stmt: OfficialStatement):
        self.cfg = cfg
        self.s = cfg.synthetic
        self.grid = grid
        self.stmt = stmt
        self.codes = list(cfg.crime_types.modelled)
        missing = [c for c in self.codes if c not in self.s.profiles]
        if missing:
            raise ValueError(f"No synthetic profile for modelled heads: {missing}")
        self.rng = np.random.default_rng(self.s.seed)
        self.days = pd.date_range(self.s.start_date, self.s.end_date, freq="D")

    # ------------------------------------------------------------------ spatial base
    def _base_weights(self) -> tuple[np.ndarray, np.ndarray]:
        g, s = self.grid, self.s
        activity = np.exp(s.activity_sigma * _smooth_field(self.rng, g, s.field_smoothing_cells))
        low = np.zeros(g.n_zones, dtype=bool)
        for poly in self.cfg.region.low_activity_areas:
            low |= points_in_polygon(g.centroid_lon, g.centroid_lat, poly)
        activity = np.where(low, activity * s.low_activity_multiplier, activity)
        mix = np.stack(
            [np.exp(_smooth_field(self.rng, g, s.field_smoothing_cells)) for _ in s.land_uses],
            axis=1,
        )
        mix /= mix.sum(axis=1, keepdims=True)
        base = np.zeros((g.n_zones, len(self.codes)))
        for ci, code in enumerate(self.codes):
            aff = np.array([self.s.profiles[code].land_use_affinity[u] for u in s.land_uses])
            w = activity * (mix @ aff)
            base[:, ci] = w / w.sum()
        self._low_activity = low
        return base, activity

    # ------------------------------------------------------------------ helpers
    def _random_land_points(self, zone_idx: np.ndarray, rounds: int = 12, rng=None):
        """Uniform points inside the given cells, re-sampled while they fall in water."""
        g = self.grid
        rng = rng if rng is not None else self.rng
        n = len(zone_idx)
        lat = np.empty(n)
        lon = np.empty(n)
        todo = np.arange(n)
        for _ in range(rounds):
            if len(todo) == 0:
                break
            z = zone_idx[todo]
            north = g.north - g.rows[z] * g.dlat
            west = g.west + g.cols[z] * g.dlon
            m = _EDGE_MARGIN_DEG
            lat[todo] = north - m - rng.random(len(todo)) * (g.dlat - 2 * m)
            lon[todo] = west + m + rng.random(len(todo)) * (g.dlon - 2 * m)
            ok = globe.is_land(lat[todo], lon[todo]) & points_in_polygon(
                lon[todo], lat[todo], self.cfg.region.outline
            )
            todo = todo[~ok]
        return lat, lon

    def _points_near(self, zone: int, focal_lat: float, focal_lon: float, n: int, sd_m=200.0):
        """Gaussian scatter around a focal point, re-sampled until inside the zone's cell."""
        s, nth, w, e = self.grid.cell_bounds(zone)
        m = _EDGE_MARGIN_DEG
        sd_lat = sd_m / 111_320.0
        sd_lon = sd_m / (111_320.0 * np.cos(np.radians(focal_lat)))
        lat = np.empty(n)
        lon = np.empty(n)
        todo = np.arange(n)
        for _ in range(20):
            if len(todo) == 0:
                break
            lat[todo] = focal_lat + self.rng.normal(0, sd_lat, len(todo))
            lon[todo] = focal_lon + self.rng.normal(0, sd_lon, len(todo))
            inside = (lat[todo] > s + m) & (lat[todo] < nth - m)
            inside &= (lon[todo] > w + m) & (lon[todo] < e - m)
            todo = todo[~inside]
        if len(todo):  # extremely rare: fall back to uniform points in the cell
            lat[todo], lon[todo] = self._random_land_points(np.full(len(todo), zone))
        return lat, lon

    def _neighbors_of(self, z: int) -> np.ndarray:
        g = self.grid
        out = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == dc == 0:
                    continue
                r, c = g.rows[z] + dr, g.cols[z] + dc
                if 0 <= r < g.n_rows and 0 <= c < g.n_cols and g.lookup[r, c] >= 0:
                    out.append(g.lookup[r, c])
        return np.array(out, dtype=int)

    # ------------------------------------------------------------------ hotspots
    def _plant_hotspots(self, base: np.ndarray, rates: np.ndarray) -> list[Hotspot]:
        s, rng = self.s, self.rng
        mean_rate = rates.mean(axis=1)
        boost = np.clip(np.sqrt(np.median(mean_rate) / mean_rate), 1.0, s.rarity_boost_max)
        volume_w = np.sqrt(mean_rate) / np.sqrt(mean_rate).sum()

        kinds: list[tuple[str, int]] = []
        for ci in range(len(self.codes)):
            kinds += [("persistent", ci)] * s.hotspots.persistent_per_type
        for kind, n in (
            ("persistent", s.hotspots.persistent_extra),
            ("seasonal", s.hotspots.seasonal),
            ("emerging", s.hotspots.emerging),
            ("declining", s.hotspots.declining),
        ):
            kinds += [(kind, int(ci)) for ci in rng.choice(len(self.codes), n, p=volume_w)]

        centers: dict[int, list[int]] = {}
        n_days = len(self.days)
        day_idx = np.arange(n_days)
        end = self.days[-1]
        hotspots = []
        used = np.zeros(self.grid.n_zones)
        for k, (kind, ci) in enumerate(kinds):
            rng = np.random.default_rng([s.seed, 1000 + k])  # independent stream per hotspot
            code = self.codes[ci]
            # prefer places already suited to the crime type, but spread hotspots out
            p = base[:, ci] ** 1.5 * 0.2**used
            p[self._low_activity] = 0
            spaced = p.copy()
            for c0 in centers.get(ci, []):
                far = np.maximum(
                    np.abs(self.grid.rows - self.grid.rows[c0]),
                    np.abs(self.grid.cols - self.grid.cols[c0]),
                )
                spaced[far <= 2] = 0
            if spaced.sum() > 0:  # small grids may leave no well-spaced candidate
                p = spaced
            z = int(rng.choice(self.grid.n_zones, p=p / p.sum()))
            centers.setdefault(ci, []).append(z)
            used[z] += 1
            nbrs = self._neighbors_of(z)
            share = rng.uniform(*s.hotspot_share_range) * boost[ci]
            prof = self.s.profiles[code]
            pk = prof.hour_peaks[rng.choice(len(prof.hour_peaks))]
            peak_hour = float((pk[0] + rng.uniform(-1, 1)) % 24)
            flat, flon = self._random_land_points(np.array([z]), rng=rng)
            params: dict[str, Any] = {}
            if kind == "persistent":
                profile = np.ones(n_days)
            elif kind == "seasonal":
                dur = int(rng.integers(*s.seasonal_duration_weeks, endpoint=True)) * 7
                start_doy = int(rng.integers(1, 366))
                doy = self.days.dayofyear.to_numpy()
                in_season = ((doy - start_doy) % 365) < dur
                profile = in_season.astype(float)
                params = {"season_start_day_of_year": start_doy, "season_length_days": dur}
            elif kind == "emerging":
                onset_w = int(rng.integers(*s.emerging_onset_weeks_before_end, endpoint=True))
                ramp_w = int(rng.integers(*s.emerging_ramp_weeks, endpoint=True))
                onset = end - pd.Timedelta(weeks=onset_w)
                d0 = int(self.days.get_loc(onset))
                profile = np.clip((day_idx - d0) / (ramp_w * 7), 0, 1)
                params = {"onset": onset.date().isoformat(), "ramp_weeks": ramp_w}
            else:  # declining
                lo, hi = s.declining_start_range
                ds = lo + timedelta(days=int(rng.integers(0, (hi - lo).days)))
                hl = int(rng.integers(*s.declining_half_life_weeks, endpoint=True))
                d0 = int(self.days.get_loc(pd.Timestamp(ds)))
                profile = np.where(day_idx < d0, 1.0, 0.5 ** ((day_idx - d0) / (hl * 7)))
                params = {"decline_start": ds.isoformat(), "half_life_weeks": hl}
            zone_idx = np.concatenate([[z], nbrs])
            weight = np.concatenate([[1.0], np.full(len(nbrs), s.hotspot_spill)])
            hotspots.append(
                Hotspot(
                    id=f"HS{k + 1:02d}",
                    kind=kind,
                    crime_type=code,
                    center_zone=self.grid.zone_ids[z],
                    zones=[self.grid.zone_ids[i] for i in zone_idx],
                    center_share=round(float(share), 4),
                    peak_hour=round(peak_hour, 2),
                    focal_lat=round(float(flat[0]), 6),
                    focal_lon=round(float(flon[0]), 6),
                    params=params,
                    zone_idx=zone_idx,
                    zone_weight=weight,
                    profile=profile,
                )
            )
        return hotspots

    def _plant_anomalies(self, base: np.ndarray, rates: np.ndarray) -> list[Anomaly]:
        s = self.s
        mean_rate = rates.mean(axis=1)
        type_w = np.sqrt(mean_rate) / np.sqrt(mean_rate).sum()
        n_days = len(self.days)
        out = []
        for k in range(s.n_anomalies):
            rng = np.random.default_rng([s.seed, 2000 + k])  # independent stream per surge
            ci = int(rng.choice(len(self.codes), p=type_w))
            p = base[:, ci].copy()
            p[self._low_activity] = 0
            z = int(rng.choice(self.grid.n_zones, p=p / p.sum()))
            length = int(rng.integers(*s.anomaly_days, endpoint=True))
            if k < s.n_recent_anomalies:  # surges under way in the final forecast window
                length = min(length, self.cfg.time.window_days)
                d0 = n_days - length
            else:
                d0 = int(rng.integers(0, n_days - length))
            zone_rate = rates[ci, d0 : d0 + length].mean() * base[z, ci]
            extra = max(rng.uniform(*s.anomaly_multiplier) * zone_rate, s.anomaly_min_daily)
            out.append(
                Anomaly(
                    id=f"AN{k + 1:02d}",
                    crime_type=self.codes[ci],
                    zone=self.grid.zone_ids[z],
                    start=self.days[d0].date().isoformat(),
                    end=self.days[d0 + length - 1].date().isoformat(),
                    extra_daily_rate=round(float(extra), 4),
                    zone_idx=z,
                    day0=d0,
                    day1=d0 + length,
                )
            )
        return out

    # ------------------------------------------------------------------ stations
    def _stations(self, activity: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
        g = self.grid
        xy = np.column_stack(
            [g.centroid_lon * np.cos(np.radians(g.centroid_lat.mean())), g.centroid_lat]
        )
        km = KMeans(n_clusters=self.s.n_stations, n_init=10, random_state=self.s.seed)
        labels = km.fit_predict(xy, sample_weight=np.sqrt(activity))
        centers = km.cluster_centers_
        order = np.argsort(-centers[:, 1])  # number stations north to south
        rank = np.empty_like(order)
        rank[order] = np.arange(len(order))
        station_ids = [f"SYN-PS-{i + 1:02d}" for i in range(len(order))]
        lat_c = centers[order, 1]
        lon_c = centers[order, 0] / np.cos(np.radians(g.centroid_lat.mean()))
        stations = pd.DataFrame(
            {
                "station_id": station_ids,
                "name": [f"Synthetic Station {i + 1:02d}" for i in range(len(order))],
                "latitude": lat_c.round(6),
                "longitude": lon_c.round(6),
                "is_synthetic": True,
                "source": SYNTHETIC_SOURCE,
            }
        )
        zone_station = np.array(station_ids)[rank[labels]]
        return stations, zone_station

    # ------------------------------------------------------------------ sampling
    def _sample_hours(self, dist: np.ndarray, n: int) -> np.ndarray:
        return self.rng.choice(24, size=n, p=dist)

    def generate(self) -> dict[str, Any]:
        cfg, s, g, rng = self.cfg, self.s, self.grid, self.rng
        rates, anchor_table = anchored_daily_rates(self.stmt, self.codes, self.days)
        base, activity = self._base_weights()
        base = (1 - s.noise_share) * base + s.noise_share / g.n_zones
        hotspots = self._plant_hotspots(base, rates)
        anomalies = self._plant_anomalies(base, rates)
        stations, zone_station = self._stations(activity)

        weekday = self.days.dayofweek.to_numpy()
        n_days = len(self.days)
        parts: list[pd.DataFrame] = []

        for ci, code in enumerate(self.codes):
            prof: CrimeProfile = s.profiles[code]
            allowed = cfg.crime_types.allowed_hours.get(code)
            wk = np.asarray(prof.weekday_weights, dtype=float)
            wk = wk / wk.mean()
            day_rate = rates[ci] * wk[weekday]  # (D,)
            hs = [h for h in hotspots if h.crime_type == code]
            # normaliser: base weights sum to 1; hotspot shares add on top
            extra = np.zeros(n_days)
            for h in hs:
                extra += h.center_share * h.profile * h.zone_weight.sum()
            norm = 1.0 + extra  # (D,)
            type_hours = hour_distribution(prof.hour_peaks, allowed)

            # base component: Poisson per (zone, day)
            lam = base[:, ci][:, None] * (day_rate / norm)[None, :]
            counts = rng.poisson(lam)
            zi, di = np.nonzero(counts)
            reps = counts[zi, di]
            parts.append(
                self._records(
                    code, np.repeat(zi, reps), np.repeat(di, reps), type_hours, "base", ""
                )
            )
            # hotspot components
            for h in hs:
                sig = hour_distribution([(h.peak_hour, 1.5, 1.0)], allowed)
                mixed = (
                    s.hotspot_time_signature_share * sig
                    + (1 - s.hotspot_time_signature_share) * type_hours
                )
                lam_h = (h.center_share * h.zone_weight)[:, None] * (h.profile * day_rate / norm)[
                    None, :
                ]
                ch = rng.poisson(lam_h)
                zi, di = np.nonzero(ch)
                reps = ch[zi, di]
                parts.append(
                    self._records(
                        code,
                        h.zone_idx[np.repeat(zi, reps)],
                        np.repeat(di, reps),
                        mixed,
                        "hotspot",
                        h.id,
                        focal=(h.focal_lat, h.focal_lon, h.zone_idx[0]),
                    )
                )
            # surge components (additive)
            for a in (a for a in anomalies if a.crime_type == code):
                n_each = rng.poisson(a.extra_daily_rate, a.day1 - a.day0)
                di = np.repeat(np.arange(a.day0, a.day1), n_each)
                parts.append(
                    self._records(code, np.full(len(di), a.zone_idx), di, type_hours, "surge", a.id)
                )

        df = pd.concat(parts, ignore_index=True)
        df = df.sort_values("timestamp", kind="stable").reset_index(drop=True)
        df["incident_id"] = [f"SYN-{i + 1:07d}" for i in range(len(df))]
        df["police_station_id"] = zone_station[df["_zone_idx"].to_numpy()]
        df["severity"] = df["crime_type"].map(cfg.crime_types.severity).astype(int)
        df["source"] = SYNTHETIC_SOURCE
        ts = df["timestamp"]
        df["day_of_week"] = ts.dt.dayofweek
        df["hour"] = ts.dt.hour
        df["month"] = ts.dt.month
        df["is_weekend"] = ts.dt.dayofweek >= 5

        components = df[["incident_id", "_component", "_component_id"]].rename(
            columns={"_component": "component", "_component_id": "component_id"}
        )
        clean = df[INCIDENT_COLUMNS].copy()
        published, defects = self._inject_defects(clean)
        return {
            "incidents": published,
            "components": components,
            "stations": stations,
            "zone_station": pd.DataFrame(
                {"zone_id": list(g.zone_ids), "police_station_id": zone_station}
            ),
            "ground_truth": {
                "label": SYNTHETIC_LABEL,
                "note": "Planted patterns for evaluation only. Never an input to analytics.",
                "hotspots": [h.to_json() for h in hotspots],
                "anomalies": [a.to_json() for a in anomalies],
            },
            "summary": self._summary(clean, anchor_table, defects, len(published)),
        }

    def _records(self, code, zone_idx, day_idx, hour_dist, component, component_id, focal=None):
        n = len(zone_idx)
        if n == 0:
            return pd.DataFrame()
        hours = self._sample_hours(hour_dist, n)
        seconds = self.rng.integers(0, 3600, n)
        ts = (
            self.days[day_idx].to_numpy()
            + hours.astype("timedelta64[h]")
            + seconds.astype("timedelta64[s]")
        )
        if focal is not None:
            flat, flon, center = focal
            lat = np.empty(n)
            lon = np.empty(n)
            at_center = zone_idx == center
            if at_center.any():
                lat[at_center], lon[at_center] = self._points_near(
                    center, flat, flon, int(at_center.sum())
                )
            if (~at_center).any():
                lat[~at_center], lon[~at_center] = self._random_land_points(zone_idx[~at_center])
        else:
            lat, lon = self._random_land_points(zone_idx)
        # zone is derived from the published (rounded) coordinates, exactly as
        # preprocessing will do it; points are kept a margin inside their cell.
        lat, lon = lat.round(6), lon.round(6)
        zi = self.grid.point_to_zone_index(lat, lon)
        if not np.array_equal(zi, zone_idx):
            raise AssertionError("Generated point fell outside its intended zone")
        return pd.DataFrame(
            {
                "timestamp": ts,
                "crime_type": code,
                "latitude": lat,
                "longitude": lon,
                "zone_id": np.array(self.grid.zone_ids)[zi],
                "_zone_idx": zi,
                "_component": component,
                "_component_id": component_id,
            }
        )

    # ------------------------------------------------------------------ defects
    def _inject_defects(self, df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
        rates = self.s.defect_rates
        n = len(df)
        out = df.copy()
        out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        out = out.astype(
            {
                "latitude": object,
                "longitude": object,
                "day_of_week": "Int64",
                "hour": "Int64",
                "month": "Int64",
                "is_weekend": "boolean",
            }
        )
        perm = self.rng.permutation(n)
        cursor = 0
        counts: dict[str, int] = {}

        def take(name: str) -> np.ndarray:
            nonlocal cursor
            k = int(round(rates.get(name, 0.0) * n))
            idx = perm[cursor : cursor + k]
            cursor += k
            counts[name] = k
            return idx

        idx = take("missing_timestamp")
        out.loc[idx, ["timestamp", "day_of_week", "hour", "month", "is_weekend"]] = None
        idx = take("missing_location")
        out.loc[idx, ["latitude", "longitude"]] = None
        idx = take("invalid_coordinates")
        half = len(idx) // 2
        out.loc[idx[:half], ["latitude", "longitude"]] = 0.0
        swapped = idx[half:]
        lat = out.loc[swapped, "latitude"].to_numpy()
        out.loc[swapped, "latitude"] = out.loc[swapped, "longitude"].to_numpy()
        out.loc[swapped, "longitude"] = lat
        idx = take("unknown_crime_type")
        out.loc[idx, "crime_type"] = "UNSPECIFIED"
        k = int(round(rates.get("duplicate_record", 0.0) * n))
        dup_src = perm[cursor : cursor + k]
        counts["duplicate_record"] = k
        out = pd.concat([out, out.loc[dup_src]], ignore_index=True)
        out = out.iloc[self.rng.permutation(len(out))].reset_index(drop=True)
        return out, counts

    def _summary(self, clean: pd.DataFrame, anchor_table, defects, n_published) -> dict[str, Any]:
        stmt = self.stmt
        by_period = {}
        for key in ("PY", "CY", "PM", "CM"):
            a, b = _period(stmt, key)
            mask = (clean["timestamp"] >= pd.Timestamp(a)) & (
                clean["timestamp"] < pd.Timestamp(b) + pd.Timedelta(days=1)
            )
            by_period[key] = clean.loc[mask, "crime_type"].value_counts().to_dict()
        for row in anchor_table:
            row["synthetic_generated"] = {
                k: int(by_period[k].get(row["crime_type"], 0)) for k in by_period
            }
        return {
            "label": SYNTHETIC_LABEL,
            "source": SYNTHETIC_SOURCE,
            "seed": self.s.seed,
            "period": {
                "start": self.s.start_date.isoformat(),
                "end": self.s.end_date.isoformat(),
            },
            "n_zones": self.grid.n_zones,
            "n_incidents_clean": int(len(clean)),
            "n_rows_published": int(n_published),
            "injected_defects": defects,
            "anchoring": anchor_table,
            "config_fingerprint": self.cfg.fingerprint(
                "region", "grid", "crime_types", "synthetic"
            ),
        }


def write_outputs(result: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    result["incidents"].to_csv(out_dir / "incidents_synthetic.csv", index=False)
    result["components"].to_parquet(out_dir / "ground_truth_components.parquet", index=False)
    result["stations"].to_csv(out_dir / "police_stations_synthetic.csv", index=False)
    result["zone_station"].to_csv(out_dir / "zone_station_synthetic.csv", index=False)
    (out_dir / "ground_truth.json").write_text(
        json.dumps(result["ground_truth"], indent=2), encoding="utf-8"
    )
    (out_dir / "generation_summary.json").write_text(
        json.dumps(result["summary"], indent=2), encoding="utf-8"
    )
    (out_dir / "README.txt").write_text(
        f"{SYNTHETIC_LABEL}\n\nEvery row in this directory is simulated. None of it is a real "
        "police incident. City-wide volumes are anchored to the official Brihan Mumbai "
        "statement; locations, times and patterns are generator assumptions.\n",
        encoding="utf-8",
    )
