from __future__ import annotations

import numpy as np
import pandas as pd

from ml.config import SYNTHETIC_SOURCE
from ml.data.official.load import OfficialStatement
from ml.data.synthetic import SyntheticGenerator, hour_distribution
from ml.preprocessing.grid import Grid


def test_every_row_is_labelled_synthetic(generated, small_cfg):
    inc = generated["incidents"]
    assert (inc["source"] == SYNTHETIC_SOURCE).all()
    assert (inc["incident_id"].str.startswith("SYN-")).all()
    assert (small_cfg.paths.raw_dir / "README.txt").read_text().startswith("SYNTHETIC")
    assert generated["stations"]["is_synthetic"].all()


def test_volumes_are_anchored_to_official_counts(generated, small_cfg):
    """Base + hotspot incidents match official registered counts within Poisson noise."""
    stmt = OfficialStatement.load(small_cfg.paths.official_statement)
    inc = generated["incidents"].merge(generated["components"], on="incident_id")
    inc = inc[(inc["component"] != "surge") & inc["timestamp"].notna()]
    ts = pd.to_datetime(inc["timestamp"])
    for key in ("PY", "CY"):
        p = stmt.periods[key]
        in_win = (ts >= p["start"]) & (ts < pd.Timestamp(p["end"]) + pd.Timedelta(days=1))
        counts = inc.loc[in_win, "crime_type"].value_counts()
        for code in small_cfg.crime_types.modelled:
            official = stmt.ipc_registered(code, key)
            got = counts.get(code, 0)
            # defects remove ~1.5% of rows before this check; allow for them plus 5 sigma
            assert abs(got - official) <= 5 * np.sqrt(official) + 0.03 * official + 3, (
                code,
                key,
                got,
                official,
            )


def test_house_breaking_day_and_night_respect_head_definitions(generated):
    inc = generated["incidents"].dropna(subset=["hour"])
    day = inc.loc[inc["crime_type"] == "HBT_DAY", "hour"].astype(int)
    night = inc.loc[inc["crime_type"] == "HBT_NIGHT", "hour"].astype(int)
    assert day.between(6, 17).all()
    assert ((night >= 18) | (night < 6)).all()


def test_hour_distribution_wraps_midnight():
    p = hour_distribution([(23.5, 1.0, 1.0)], allowed=(18, 6))
    assert np.isclose(p.sum(), 1)
    assert p[12] == 0 and p[23] > p[20]


def test_generator_is_deterministic(small_cfg, small_grid, generated):
    stmt = OfficialStatement.load(small_cfg.paths.official_statement)
    again = SyntheticGenerator(small_cfg, small_grid, stmt).generate()
    pd.testing.assert_frame_equal(again["incidents"], generated["incidents"])


def test_all_pattern_kinds_are_planted(generated):
    kinds = {h["kind"] for h in generated["ground_truth"]["hotspots"]}
    assert kinds == {"persistent", "seasonal", "emerging", "declining"}
    assert len(generated["ground_truth"]["anomalies"]) > 0


def test_quality_report_recovers_injected_defects(processed, generated):
    injected = generated["summary"]["injected_defects"]
    checks = {c["id"]: c for c in processed["quality"]["checks"]}
    for name in (
        "duplicate_record",
        "missing_timestamp",
        "missing_location",
        "invalid_coordinates",
        "unknown_crime_type",
    ):
        assert checks[name]["rows_rejected"] == injected[name], name
    assert checks["zone_id_mismatch"]["rows_with_issue"] == 0
    q = processed["quality"]
    assert q["rows_in"] - q["rows_out"] == sum(c["rows_rejected"] for c in q["checks"])


def test_processed_incidents_are_consistent(processed, small_cfg, small_grid: Grid):
    inc = pd.read_parquet(small_cfg.paths.processed_dir / "incidents.parquet")
    assert inc["incident_id"].is_unique
    idx = small_grid.point_to_zone_index(inc["latitude"].to_numpy(), inc["longitude"].to_numpy())
    assert np.array_equal(idx, inc["zone_idx"].to_numpy())
    assert (inc["timestamp"] < pd.Timestamp(small_cfg.time.as_of)).all()
    assert set(inc["band"]) == {b.code for b in small_cfg.time.bands}
    assert processed["manifest"]["is_synthetic"] is True
    assert processed["manifest"]["dataset_version"].startswith("Dataset-")
