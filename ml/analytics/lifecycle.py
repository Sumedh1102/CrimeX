"""Hotspot lifecycle over successive origins, and hotspot movement between them.

Lifecycle
    The hotspot-state classifier (``hotspot_states.classify_states``) is re-run at
    ``lifecycle_steps`` origins, one analysis period apart, ending at the forecast origin.
    Each state maps to a lifecycle stage:

    EMERGING, ACTIVE, PERSISTENT, DECLINING   -> the same stage
    SPORADIC, STABLE                          -> RESOLVED if the previous step was one of
                                                 the four stages above, else NORMAL

    The first step has no predecessor, so SPORADIC/STABLE map to NORMAL there.

Movement
    At each step, zones whose Gi* z-score for the final period is >= ``hot_z`` are grouped
    into clusters (queen contiguity). A cluster is linked to clusters of the previous step
    that share a zone or, failing that, to the nearest one whose z-weighted centroid lies
    within ``movement_max_km``. Kinds:

    NEW         no linked earlier cluster
    CONTINUED   linked; centroid moved less than half a cell
    SHIFTED     linked; centroid moved at least half a cell
    DISSIPATED  an earlier cluster with no linked successor
    Clusters linked to several predecessors are flagged ``merged``; a predecessor linked to
    several successors flags them ``split``.

Both are descriptive summaries of historical reported incidents; they do not predict
where activity will move next.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from ml.analytics.hotspot_states import classify_states
from ml.config import HotspotConfig
from ml.preprocessing.grid import Grid

LIFECYCLE_STAGES = ("NORMAL", "EMERGING", "ACTIVE", "PERSISTENT", "DECLINING", "RESOLVED")
HOT_STAGES = frozenset({"EMERGING", "ACTIVE", "PERSISTENT", "DECLINING"})
STAGE_DESCRIPTIONS = {
    "NORMAL": "No hotspot pattern at this origin.",
    "EMERGING": "Recently became a statistically significant hotspot.",
    "ACTIVE": "A statistically significant hotspot in the most recent period.",
    "PERSISTENT": "A hotspot in most periods of the analysis window.",
    "DECLINING": "Hotspot intensity decreasing or absent after earlier activity.",
    "RESOLVED": "Was a hotspot at the previous origin; no longer shows a hotspot pattern.",
}
COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def lifecycle_origins(origin_k: int, period: int, n_periods: int, steps: int) -> list[int]:
    """Origins (window indices) for the lifecycle, oldest first; skips those lacking history."""
    ks = [origin_k - (steps - 1 - t) * period for t in range(steps)]
    return [k for k in ks if k - period * n_periods >= 0]


def stage_of(state: str, previous_stage: str | None) -> str:
    if state in HOT_STAGES:
        return state
    return "RESOLVED" if previous_stage in HOT_STAGES else "NORMAL"


def hotspot_lifecycle(
    zc_counts: np.ndarray,
    origin_k: int,
    origins: pd.DatetimeIndex,
    grid: Grid,
    crime_types: tuple[str, ...],
    cfg: HotspotConfig,
    period: int,
) -> pd.DataFrame:
    """Long table: one row per (step, zone, crime type) with state and lifecycle stage."""
    ks = lifecycle_origins(origin_k, period, cfg.n_periods, cfg.lifecycle_steps)
    frames = []
    prev: pd.Series | None = None
    for step, k in enumerate(ks):
        st = classify_states(zc_counts, k, grid, crime_types, cfg, period_windows=period)
        st = st[["zone_id", "crime_type", "state", "final_period_hot", "gi_z_last"]].copy()
        key = st["zone_id"] + "|" + st["crime_type"]
        prev_stage = key.map(prev) if prev is not None else pd.Series(None, index=st.index)
        st["stage"] = [
            stage_of(s, p if isinstance(p, str) else None)
            for s, p in zip(st["state"], prev_stage, strict=True)
        ]
        st["step"] = step
        st["origin_k"] = k
        st["period_end"] = origins[k]
        st["period_start"] = origins[max(k - period, 0)]
        prev = pd.Series(st["stage"].to_numpy(), index=key.to_numpy())
        frames.append(st)
    if not frames:
        return pd.DataFrame(
            columns=[
                "zone_id",
                "crime_type",
                "state",
                "final_period_hot",
                "gi_z_last",
                "stage",
                "step",
                "origin_k",
                "period_end",
                "period_start",
            ]
        )
    return pd.concat(frames, ignore_index=True)


def lifecycle_summary(lc: pd.DataFrame) -> pd.DataFrame:
    """Per (zone, crime type): current and previous stage, and how long it has held."""
    rows = []
    for (z, c), g in lc.sort_values("step").groupby(["zone_id", "crime_type"], sort=False):
        stages = g["stage"].tolist()
        cur = stages[-1]
        run = 0
        for s in reversed(stages):
            if s != cur:
                break
            run += 1
        rows.append(
            {
                "zone_id": z,
                "crime_type": c,
                "stage": cur,
                "previous_stage": stages[-2] if len(stages) > 1 else None,
                "stage_changed": len(stages) > 1 and stages[-2] != cur,
                "steps_in_stage": run,
                "ever_hot": any(s in HOT_STAGES for s in stages),
            }
        )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------ movement


def _km(lat1, lon1, lat2, lon2) -> float:
    mid = math.radians((lat1 + lat2) / 2)
    dy = (lat2 - lat1) * 110.574
    dx = (lon2 - lon1) * 111.320 * math.cos(mid)
    return math.hypot(dx, dy)


def bearing(lat1, lon1, lat2, lon2) -> float:
    """Compass bearing in degrees (0 = north, 90 = east) on a local flat approximation."""
    mid = math.radians((lat1 + lat2) / 2)
    dy = lat2 - lat1
    dx = (lon2 - lon1) * math.cos(mid)
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def compass(deg: float) -> str:
    return COMPASS[int((deg + 22.5) // 45) % 8]


def hot_clusters(z: np.ndarray, grid: Grid, hot_z: float) -> list[dict]:
    """Connected clusters of hot zones with a z-weighted centroid."""
    hot = np.nonzero(z >= hot_z)[0]
    if len(hot) == 0:
        return []
    i, j, _ = grid.neighbors(1)
    pos = np.full(grid.n_zones, -1)
    pos[hot] = np.arange(len(hot))
    keep = (pos[i] >= 0) & (pos[j] >= 0)
    adj = csr_matrix(
        (np.ones(keep.sum()), (pos[i][keep], pos[j][keep])), shape=(len(hot), len(hot))
    )
    n, lab = connected_components(adj, directed=False)
    out = []
    for c in range(n):
        members = hot[lab == c]
        w = z[members]
        out.append(
            {
                "members": members,
                "lat": float((grid.centroid_lat[members] * w).sum() / w.sum()),
                "lon": float((grid.centroid_lon[members] * w).sum() / w.sum()),
                "peak_z": float(w.max()),
            }
        )
    out.sort(key=lambda d: -d["peak_z"])
    return out


def _links(prev: list[dict], cur: list[dict], max_km: float) -> list[tuple[int, int]]:
    links = []
    for ci, c in enumerate(cur):
        overlap = [
            pi for pi, p in enumerate(prev) if np.intersect1d(p["members"], c["members"]).size
        ]
        if overlap:
            links += [(pi, ci) for pi in overlap]
            continue
        best, best_d = None, max_km
        for pi, p in enumerate(prev):
            d = _km(p["lat"], p["lon"], c["lat"], c["lon"])
            if d <= best_d:
                best, best_d = pi, d
        if best is not None:
            links.append((best, ci))
    return links


def hotspot_movement(lc: pd.DataFrame, grid: Grid, cfg: HotspotConfig) -> pd.DataFrame:
    """Cluster-level movement records for every step and crime type (see module doc)."""
    rows: list[dict] = []
    if lc.empty:
        return pd.DataFrame(rows)
    zidx = grid.zone_index
    half_cell_km = grid.cell_km / 2
    for code, g in lc.groupby("crime_type", sort=False):
        prev: list[dict] = []
        prev_ids: list[str] = []
        for step, gs in g.groupby("step"):
            z = np.zeros(grid.n_zones)
            z[[zidx[x] for x in gs["zone_id"]]] = gs["gi_z_last"].to_numpy()
            cur = hot_clusters(z, grid, cfg.hot_z)
            end = pd.Timestamp(gs["period_end"].iloc[0]).date().isoformat()
            ids = [f"{code}-S{step}-C{i + 1}" for i in range(len(cur))]
            links = _links(prev, cur, cfg.movement_max_km) if step > 0 else []
            succ = {pi: [c for p, c in links if p == pi] for pi in range(len(prev))}
            for ci, c in enumerate(cur):
                preds = [p for p, cc in links if cc == ci]
                base = {
                    "crime_type": code,
                    "step": int(step),
                    "period_end": end,
                    "cluster_id": ids[ci],
                    "zones": [grid.zone_ids[m] for m in c["members"]],
                    "n_zones": len(c["members"]),
                    "lat": round(c["lat"], 6),
                    "lon": round(c["lon"], 6),
                    "peak_z": round(c["peak_z"], 3),
                    "merged": len(preds) > 1,
                    "split": any(len(succ[p]) > 1 for p in preds),
                }
                if step == 0:
                    rows.append({**base, "kind": "BASELINE", "from_cluster_ids": []})
                    continue
                if not preds:
                    rows.append({**base, "kind": "NEW", "from_cluster_ids": []})
                    continue
                # displacement from the largest linked predecessor
                p = max(preds, key=lambda i: len(prev[i]["members"]))
                d = _km(prev[p]["lat"], prev[p]["lon"], c["lat"], c["lon"])
                b = bearing(prev[p]["lat"], prev[p]["lon"], c["lat"], c["lon"])
                rows.append(
                    {
                        **base,
                        "kind": "SHIFTED" if d >= half_cell_km else "CONTINUED",
                        "from_cluster_ids": [prev_ids[i] for i in preds],
                        "from_lat": round(prev[p]["lat"], 6),
                        "from_lon": round(prev[p]["lon"], 6),
                        "distance_km": round(d, 3),
                        "bearing_deg": round(b, 1),
                        "direction": compass(b) if d >= half_cell_km else None,
                    }
                )
            if step > 0:
                for pi, p in enumerate(prev):
                    if not succ[pi]:
                        rows.append(
                            {
                                "crime_type": code,
                                "step": int(step),
                                "period_end": end,
                                "cluster_id": prev_ids[pi],
                                "zones": [grid.zone_ids[m] for m in p["members"]],
                                "n_zones": len(p["members"]),
                                "lat": round(p["lat"], 6),
                                "lon": round(p["lon"], 6),
                                "peak_z": round(p["peak_z"], 3),
                                "merged": False,
                                "split": False,
                                "kind": "DISSIPATED",
                                "from_cluster_ids": [],
                            }
                        )
            prev, prev_ids = cur, ids
    return pd.DataFrame(rows)
