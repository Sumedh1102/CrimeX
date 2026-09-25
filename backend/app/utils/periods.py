"""Named analysis periods relative to the forecast origin (as_of)."""

from __future__ import annotations

import pandas as pd

PERIODS = {
    "24h": pd.Timedelta(hours=24),
    "7d": pd.Timedelta(days=7),
    "30d": pd.Timedelta(days=30),
    "90d": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=182),
    "1y": pd.Timedelta(days=365),
}


def resolve_period(
    period: str, as_of: pd.Timestamp, start: str | None = None, end: str | None = None
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return [start, end) for a named period ending at as_of, or a custom range."""
    if period == "custom":
        if not start or not end:
            raise ValueError("custom period requires start and end (YYYY-MM-DD)")
        s, e = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)
        if e <= s:
            raise ValueError("end must not be before start")
        return s, min(e, as_of)
    if period not in PERIODS:
        raise ValueError(f"period must be one of {[*PERIODS, 'custom']}")
    return as_of - PERIODS[period], as_of
