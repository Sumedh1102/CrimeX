"""Crime Surge Detector (CSD): a separate layer from the forecasting model.

For each (zone, crime type) the most recent window is compared with the preceding
``anomaly_history_weeks`` windows: z = (C_current - mean) / (std + anomaly_epsilon). The capped,
normalised z feeds the risk score as component X; zones with z >= anomaly_alert_z and at
least anomaly_alert_min_count incidents are raised as surge alerts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.config import ScoringConfig
from ml.features.engine import ComponentPanel


def surge_table(
    cp: ComponentPanel,
    k: int,
    zones: tuple[str, ...],
    crime_types: tuple[str, ...],
    s: ScoringConfig,
) -> pd.DataFrame:
    cur = cp.anomaly_current[..., k]
    mean = cp.anomaly_mean[..., k]
    std = cp.anomaly_std[..., k]
    z = cp.anomaly_z[..., k]
    zz, cc = np.meshgrid(np.arange(len(zones)), np.arange(len(crime_types)), indexing="ij")
    df = pd.DataFrame(
        {
            "zone_id": np.array(zones)[zz.ravel()],
            "crime_type": np.array(crime_types)[cc.ravel()],
            "current_count": cur.ravel().astype(int),
            "baseline_mean": np.round(mean.ravel(), 3),
            "baseline_std": np.round(std.ravel(), 3),
            "z_score": np.round(z.ravel(), 3),
            "X": np.round(cp.X[..., k].ravel(), 4),
        }
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        dev = np.where(
            df["baseline_mean"] > 0,
            100 * (df["current_count"] - df["baseline_mean"]) / df["baseline_mean"],
            np.nan,
        )
    df["deviation_pct"] = np.round(dev, 1)
    df["is_alert"] = (df["z_score"] >= s.anomaly_alert_z) & (
        df["current_count"] >= s.anomaly_alert_min_count
    )
    return df
