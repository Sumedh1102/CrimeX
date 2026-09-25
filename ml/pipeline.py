"""Shared loading of processed data into the count panel and component panel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ml.config import PlatformConfig
from ml.data.official.load import HEADS_LABELS
from ml.features.engine import ComponentPanel, compute_components
from ml.preprocessing.grid import Grid
from ml.preprocessing.panel import CountPanel, build_panel
from ml.preprocessing.pipeline import load_processed


@dataclass
class Inputs:
    cfg: PlatformConfig
    grid: Grid
    incidents: pd.DataFrame
    zones: pd.DataFrame
    manifest: dict[str, Any]
    panel: CountPanel
    components: ComponentPanel

    @property
    def crime_labels(self) -> dict[str, str]:
        return {c: HEADS_LABELS.get(c, c) for c in self.panel.crime_types}


def load_inputs(cfg: PlatformConfig) -> Inputs:
    grid = Grid.build(cfg.region, cfg.grid)
    incidents, zones, manifest = load_processed(cfg)
    if list(zones["zone_id"]) != list(grid.zone_ids):
        raise ValueError("Processed zones do not match the configured grid; re-run preprocessing")
    panel = build_panel(
        incidents,
        grid.zone_ids,
        cfg.crime_types.modelled,
        [b.code for b in cfg.time.bands],
        cfg.time.as_of,
        cfg.time.window_days,
    )
    cp = compute_components(panel, grid, cfg.scoring)
    return Inputs(cfg, grid, incidents, zones, manifest, panel, cp)
