"""'Why is this zone flagged?' statements, generated only from actual component inputs.

Each statement is a template filled with the measured values behind one CRS component
(or the hotspot state / surge detector) and is emitted only when that component is
notably high. Statements describe associations in historical reported data; they never
assert causes or certainty.
"""

from __future__ import annotations

from dataclasses import dataclass

# Thresholds on normalised component values above which a statement is shown.
SHOW_WHEN = {"F": 0.75, "T": 0.6, "A": 0.5, "R": 0.5, "S": 0.75, "P": 0.6, "X": 0.33}


@dataclass
class ReasonInputs:
    crime_label: str
    band_label: str
    components: dict[str, float]  # normalised F..X
    contributions: dict[str, float]  # CRS points per component
    current_band_count: float  # frequency-window count, this band
    city_mean_band_count: float
    frequency_weeks: int
    trend_recent: float
    trend_baseline: float
    trend_weeks: int
    cai: float
    lq: float
    days_since: float
    nbr_weighted: float
    band_share: float
    surge_current: float
    surge_mean: float
    surge_z: float
    hotspot_state: str
    hot_periods: int
    n_periods: int
    recent_hot_periods: int
    window_days: int = 7  # length of one panel window (frequency/trend counts are in windows)
    recent_periods: int = 3


def span(n_windows: int, window_days: int) -> str:
    """'8 weeks', '4 weeks', '56 days' ... for ``n_windows`` panel windows."""
    days = n_windows * window_days
    if days % 7 == 0:
        weeks = days // 7
        return f"{weeks} week" + ("s" if weeks != 1 else "")
    return f"{days} day" + ("s" if days != 1 else "")


def unit(window_days: int) -> str:
    return {1: "day", 7: "week"}.get(window_days, f"{window_days}-day window")


def reasons(r: ReasonInputs) -> list[dict]:
    c = r.components
    out: list[dict] = []

    def add(component: str, text: str) -> None:
        out.append(
            {
                "component": component,
                "text": text,
                "contribution_points": round(r.contributions.get(component, 0.0), 2),
            }
        )

    if c["F"] >= SHOW_WHEN["F"]:
        add(
            "F",
            f"Recent activity is above most zones: {r.current_band_count:.0f} "
            f"{r.crime_label} incidents in the {r.band_label} band over the last "
            f"{span(r.frequency_weeks, r.window_days)} "
            f"(average zone: {r.city_mean_band_count:.1f}).",
        )
    if c["T"] >= SHOW_WHEN["T"]:
        pct = (
            (r.trend_recent - r.trend_baseline) / r.trend_baseline * 100
            if r.trend_baseline
            else None
        )
        change = f" ({pct:+.0f}%)" if pct is not None else ""
        add(
            "T",
            f"Recent activity is above this zone's own baseline: {r.trend_recent:.0f} "
            f"incidents in the last {span(r.trend_weeks, r.window_days)} vs a typical "
            f"{r.trend_baseline:.1f}{change}.",
        )
    if c["A"] >= SHOW_WHEN["A"]:
        add(
            "A",
            f"Strong historical association with {r.crime_label} (Crime Affinity "
            f"{r.cai:.0f}/100; its share of incidents here is {r.lq:.1f}x the "
            "city-wide share).",
        )
    if c["R"] >= SHOW_WHEN["R"]:
        when = (
            "within the last day"
            if r.days_since < 1
            else f"{r.days_since:.0f} days before the forecast window"
        )
        add("R", f"A similar incident ({r.crime_label}) was reported in this zone {when}.")
    if c["S"] >= SHOW_WHEN["S"]:
        add(
            "S",
            f"Neighbouring zones show elevated {r.crime_label} activity in this band "
            f"(inverse-distance weighted mean {r.nbr_weighted:.1f} incidents over "
            f"{span(r.frequency_weeks, r.window_days)}).",
        )
    if c["P"] >= SHOW_WHEN["P"]:
        add(
            "P",
            f"The {r.band_label} band resembles this zone's historical high-activity "
            f"period: {r.band_share:.0%} of its {r.crime_label} incidents (smoothed) "
            "fall in this band.",
        )
    if c["X"] >= SHOW_WHEN["X"]:
        add(
            "X",
            f"Unusual surge in the last {unit(r.window_days)}: {r.surge_current:.0f} "
            f"incidents vs a typical {r.surge_mean:.1f} per {unit(r.window_days)} "
            f"(z = {r.surge_z:.1f}).",
        )
    if r.hotspot_state in ("EMERGING", "ACTIVE", "PERSISTENT"):
        out.append(
            {
                "component": "HOTSPOT_STATE",
                "text": f"Hotspot state {r.hotspot_state}: statistically significant hotspot "
                f"(Gi*) in {r.hot_periods} of the last {r.n_periods} analysis periods, "
                f"including {r.recent_hot_periods} of the most recent {r.recent_periods}.",
                "contribution_points": None,
            }
        )
    out.sort(key=lambda d: -(d["contribution_points"] or 0))
    return out
