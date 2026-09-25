"""Chronological train / validation / test splits over forecast origins.

A row belongs to a split only if its whole forecast window lies inside the split
(window start >= split start and window end <= split end). Windows straddling a
boundary are dropped, which acts as an embargo between splits. Origins without the
full feature history (``required_history`` windows) are excluded from every split.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from ml.preprocessing.panel import CountPanel


@dataclass
class Splits:
    train: np.ndarray
    validation: np.ndarray
    test: np.ndarray
    boundaries: dict[str, str]

    def describe(self, panel: CountPanel) -> dict[str, dict[str, str | int]]:
        out = {}
        for name in ("train", "validation", "test"):
            ks = getattr(self, name)
            if len(ks) == 0:
                out[name] = {"origins": 0}
                continue
            end = panel.origins[ks[-1]] + pd.Timedelta(days=panel.window_days)
            out[name] = {
                "origins": int(len(ks)),
                "first_window_start": panel.origins[ks[0]].date().isoformat(),
                "last_window_end": end.date().isoformat(),
            }
        return out


def make_splits(
    panel: CountPanel, required_history: int, train_end: date, validation_end: date
) -> Splits:
    starts = panel.origins[:-1]  # the last origin's window has no observed counts
    ends = starts + pd.Timedelta(days=panel.window_days)
    k = np.arange(len(starts))
    ok = k >= required_history
    t_end, v_end, as_of = pd.Timestamp(train_end), pd.Timestamp(validation_end), panel.origins[-1]
    train = k[ok & (ends <= t_end)]
    val = k[ok & (starts >= t_end) & (ends <= v_end)]
    test = k[ok & (starts >= v_end) & (ends <= as_of)]
    if len(train) == 0 or len(val) == 0 or len(test) == 0:
        raise ValueError("A split is empty: check the split dates against the data period")
    return Splits(
        train=train,
        validation=val,
        test=test,
        boundaries={
            "train_end": t_end.date().isoformat(),
            "validation_end": v_end.date().isoformat(),
            "test_end": as_of.date().isoformat(),
        },
    )
