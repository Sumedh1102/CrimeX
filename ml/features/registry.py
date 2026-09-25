"""Model feature definitions: names, human-readable labels, and groups.

Labels are used verbatim in explanations, so every SHAP entry shown to a user traces
back to a named model input.
"""

from __future__ import annotations

# name -> (label, group)
BASE_FEATURES: dict[str, tuple[str, str]] = {
    "b_lag1": ("Incidents in this time band, last week", "recent activity"),
    "b_lag2": ("Incidents in this time band, 2 weeks ago", "recent activity"),
    "b_lag3": ("Incidents in this time band, 3 weeks ago", "recent activity"),
    "b_lag4": ("Incidents in this time band, 4 weeks ago", "recent activity"),
    "b_r8": ("Incidents in this time band, last 8 weeks", "recent activity"),
    "b_r13": ("Incidents in this time band, last 13 weeks", "historical frequency"),
    "b_r26": ("Incidents in this time band, last 26 weeks", "historical frequency"),
    "b_r52": ("Incidents in this time band, last 52 weeks", "historical frequency"),
    "b_lag52": ("Incidents in this time band, same week last year", "seasonality"),
    "zc_lag1": ("Incidents of this type (all hours), last week", "recent activity"),
    "zc_r4": ("Incidents of this type (all hours), last 4 weeks", "recent activity"),
    "zc_r13": ("Incidents of this type (all hours), last 13 weeks", "historical frequency"),
    "zc_r52": ("Incidents of this type (all hours), last 52 weeks", "historical frequency"),
    "days_since_last": ("Days since the last incident of this type in the zone", "recency"),
    "z_r4": ("All incidents in the zone, last 4 weeks", "zone activity"),
    "z_r52": ("All incidents in the zone, last 52 weeks", "zone activity"),
    "nbr_b_r8": ("Neighbouring zones: same type and band, last 8 weeks", "neighbour activity"),
    "nbr_zc_r4": ("Neighbouring zones: same type, last 4 weeks", "neighbour activity"),
    "city_c_r4": ("City-wide average per zone, this type, last 4 weeks", "city trend"),
    "city_c_r52": ("City-wide average per zone, this type, last 52 weeks", "city trend"),
    "city_c_trend": ("City-wide trend for this type (4 weeks vs 52-week rate)", "city trend"),
    "F": ("Frequency component F (percentile)", "risk component"),
    "S": ("Neighbour pressure component S (percentile)", "risk component"),
    "T": ("Trend component T", "risk component"),
    "T_ratio": ("Recent 4 weeks vs own 52-week baseline (ratio)", "trend"),
    "P": ("Temporal similarity component P", "risk component"),
    "X": ("Anomaly component X", "risk component"),
    "anomaly_z": ("Surge z-score of last week", "anomaly"),
    "A": ("Crime affinity component A (CAI / 100)", "crime affinity"),
    "a_spatial": ("Affinity: spatial concentration (LQ)", "crime affinity"),
    "a_recency": ("Affinity: recency", "crime affinity"),
    "a_recurrence": ("Affinity: recurrence", "crime affinity"),
    "a_consistency": ("Affinity: consistency", "crime affinity"),
    "lq": ("Location quotient (capped)", "crime affinity"),
    "woy_sin": ("Week of year (sine)", "calendar"),
    "woy_cos": ("Week of year (cosine)", "calendar"),
    "month": ("Month of the forecast window", "calendar"),
    "zone_row": ("Zone position (north-south)", "location"),
    "zone_col": ("Zone position (west-east)", "location"),
}


def feature_names(crime_types: tuple[str, ...], bands: tuple[str, ...]) -> list[str]:
    return list(BASE_FEATURES) + [f"crime_{c}" for c in crime_types] + [f"band_{b}" for b in bands]


def feature_label(name: str, crime_labels: dict[str, str] | None = None) -> str:
    if name in BASE_FEATURES:
        return BASE_FEATURES[name][0]
    if name.startswith("crime_"):
        code = name.removeprefix("crime_")
        return f"Crime type is {(crime_labels or {}).get(code, code)}"
    if name.startswith("band_"):
        return f"Time band is {name.removeprefix('band_')}"
    return name


def feature_group(name: str) -> str:
    if name in BASE_FEATURES:
        return BASE_FEATURES[name][1]
    return "crime type" if name.startswith("crime_") else "time band"
