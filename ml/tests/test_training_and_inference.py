"""End-to-end: train on the small synthetic dataset, then generate predictions."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from ml.features.builder import build_matrix
from ml.features.engine import FittedScoringState, fit_reference
from ml.inference.predict import generate_predictions, write_predictions
from ml.models.registry import ModelBundle
from ml.pipeline import load_inputs
from ml.scoring.formulas import CRS_COMPONENTS
from ml.training.splits import make_splits
from ml.training.train import train_models


@pytest.fixture(scope="module")
def inputs(small_cfg, processed):
    return load_inputs(small_cfg)


@pytest.fixture(scope="module")
def bundle(inputs, small_cfg):
    b = train_models(inputs, log=lambda _: None)
    b.save(small_cfg.paths.artifacts_dir / "models")
    return b


@pytest.fixture(scope="module")
def output(inputs, bundle, small_cfg):
    out = generate_predictions(inputs, bundle)
    write_predictions(out, small_cfg.paths.artifacts_dir / "predictions")
    return out


def test_splits_are_chronological_and_embargoed(inputs, small_cfg):
    p = inputs.panel
    sp = make_splits(
        p,
        inputs.components.windows.required_history,
        small_cfg.training.splits.train_end,
        small_cfg.training.splits.validation_end,
    )
    end = lambda k: p.origins[k] + pd.Timedelta(days=p.window_days)  # noqa: E731
    assert end(sp.train[-1]) <= pd.Timestamp(small_cfg.training.splits.train_end)
    assert p.origins[sp.validation[0]] >= pd.Timestamp(small_cfg.training.splits.train_end)
    assert end(sp.validation[-1]) <= pd.Timestamp(small_cfg.training.splits.validation_end)
    assert p.origins[sp.test[0]] >= pd.Timestamp(small_cfg.training.splits.validation_end)
    assert end(sp.test[-1]) <= p.origins[-1]
    assert sp.train[0] >= inputs.components.windows.required_history


def test_feature_matrix_shapes_and_leakage(inputs, small_cfg):
    p, cp = inputs.panel, inputs.components
    ks = np.array([p.W - 5, p.W - 1])
    state = FittedScoringState(
        reference=fit_reference(cp, np.ones(p.K, dtype=bool), p, small_cfg.scoring),
        recency_half_life_days={c: 14.0 for c in p.crime_types},
    )
    fm = build_matrix(p, cp, state, inputs.grid, small_cfg.scoring, ks)
    Z, C, B = len(p.zones), len(p.crime_types), len(p.bands)
    assert fm.X.shape == (2 * Z * C * B, len(fm.names))
    assert np.isfinite(fm.X).all()
    keys = fm.row_keys()
    # the b_lag1 feature of a row equals last week's count for that zone/crime/band
    j = fm.names.index("b_lag1")
    r = 123
    assert fm.X[r, j] == p.counts[keys["z"][r], keys["c"][r], keys["b"][r], keys["k"][r] - 1]


def test_bundle_records_versions_and_metrics(bundle):
    md = bundle.metadata
    for key in ("model_version", "training_dataset_version", "feature_version", "trained_at"):
        assert md[key]
    assert md["is_synthetic_data"] is True
    test = bundle.metrics["test"]
    for name in (
        "xgboost_calibrated",
        "random_forest_calibrated",
        "historical_rate_baseline",
        "crs_explainable",
        "blended_score",
    ):
        assert name in test
        assert 0 <= test[name]["pr_auc"] <= 1
        assert 0 <= test[name]["top_k"]["capture_rate"] <= 1
    assert "brier" in test["xgboost_calibrated"] and "brier" not in test["crs_explainable"]
    assert {"mae", "rmse"} <= set(bundle.metrics["test_counts"]["xgboost_poisson"])


def test_bundle_round_trip(bundle, small_cfg, inputs):
    loaded = ModelBundle.load(small_cfg.paths.artifacts_dir / "models")
    assert loaded.model_version == bundle.model_version
    fm = build_matrix(
        inputs.panel,
        inputs.components,
        loaded.scoring_state,
        inputs.grid,
        small_cfg.scoring,
        np.array([inputs.panel.W - 1]),
    )
    assert np.allclose(loaded.predict_probability(fm.X), bundle.predict_probability(fm.X))


def test_predictions_keep_the_three_numbers_distinct(output, small_cfg):
    p = output["predictions"]
    s = small_cfg.scoring
    assert p["probability"].between(0, 1).all()
    assert p["crs"].between(0, 100).all() and p["final_risk"].between(0, 100).all()
    # CRS is exactly the weighted sum of its components
    crs = 100 * sum(s.crs_weights[c] * p[f"comp_{c}"] for c in CRS_COMPONENTS)
    assert np.allclose(crs, p["crs"], atol=0.06)
    # contributions add up to the CRS
    assert np.allclose(sum(p[f"contrib_{c}"] for c in CRS_COMPONENTS), p["crs"], atol=0.06)
    # blended score formula
    blend = 100 * (s.blend_ml_weight * p["probability"] + (1 - s.blend_ml_weight) * p["crs"] / 100)
    assert np.allclose(blend, p["final_risk"], atol=0.1)  # both sides rounded to 0.1
    assert set(p["risk_band"]) <= {"LOW", "MODERATE", "ELEVATED", "HIGH", "VERY HIGH"}
    assert set(p["confidence"]) <= {"LOW", "MEDIUM", "HIGH"}


def test_every_prediction_is_versioned_and_labelled(output):
    p = output["predictions"]
    for col in ("model_version", "training_dataset_version", "feature_version", "generated_at"):
        assert p[col].notna().all() and (p[col] != "").all()
    assert (p["data_label"] == "SYNTHETIC / DEMONSTRATION DATA").all()
    assert output["manifest"]["limitation_statement"].startswith("Predictions represent")
    assert (p["window_end"] - p["window_start"] == pd.Timedelta(days=7)).all()


def test_explanations_trace_to_model_inputs(output, bundle):
    p = output["predictions"]
    names = set(bundle.feature_names)
    for raw in p["shap_top"].head(200):
        for item in json.loads(raw):
            assert item["feature"] in names
    comps = set(CRS_COMPONENTS) | {"HOTSPOT_STATE"}
    for raw in p["reasons"]:
        for item in json.loads(raw):
            assert item["component"] in comps
            assert item["text"]


def test_zone_crime_table(output, inputs):
    zc = output["zone_crime"]
    assert len(zc) == len(inputs.panel.zones) * len(inputs.panel.crime_types)
    assert zc["cai"].between(0, 100).all()
    assert set(zc["state"]) <= {
        "EMERGING",
        "ACTIVE",
        "PERSISTENT",
        "DECLINING",
        "SPORADIC",
        "STABLE",
    }
    h = output["history"]
    assert h["crs"].between(0, 100).all()


def test_24_hour_window_end_to_end(tmp_path):
    """time.window_days = 1: the pipeline runs, and weekly settings convert to windows."""
    from ml.config import load_config
    from ml.data.official.load import OfficialStatement
    from ml.data.synthetic import SyntheticGenerator, write_outputs
    from ml.inference.predict import generate_predictions
    from ml.pipeline import load_inputs
    from ml.preprocessing.grid import Grid
    from ml.preprocessing.pipeline import preprocess
    from ml.training.train import train_models

    cfg = load_config(
        None,
        time__window_days=1,
        grid__cell_size_m=3000,
        synthetic__start_date="2023-01-01",
        synthetic__n_stations=5,
        training__xgb__n_estimators=40,
        training__rf__n_estimators=20,
        training__rf__max_train_rows=30_000,
        paths__data_dir=str(tmp_path / "data"),
        paths__artifacts_dir=str(tmp_path / "artifacts"),
    )
    grid = Grid.build(cfg.region, cfg.grid)
    stmt = OfficialStatement.load(cfg.paths.official_statement)
    write_outputs(SyntheticGenerator(cfg, grid, stmt).generate(), cfg.paths.raw_dir)
    preprocess(cfg)
    inputs = load_inputs(cfg)
    assert inputs.panel.window_days == 1
    bundle = train_models(inputs, log=lambda _: None)
    out = generate_predictions(inputs, bundle)
    m = out["manifest"]
    assert m["window_days"] == 1
    assert pd.Timestamp(m["window_end"]) - pd.Timestamp(m["window_start"]) == pd.Timedelta(days=1)
    assert m["analysis_period_windows"] == 28  # 4-week analysis periods in 1-day windows
    assert m["pattern_lookback_windows"] == 56
    p = out["predictions"]
    assert p["probability"].between(0, 1).all()
    assert len(p) == grid.n_zones * len(cfg.crime_types.modelled) * len(cfg.time.bands)
    assert not out["lifecycle"].empty
    reasons = " ".join(p["reasons"])
    assert "last week" not in reasons and "per week" not in reasons
