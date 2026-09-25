"""Train, calibrate and evaluate the baseline forecasting models.

Target event Y (classification): at least one reported incident of crime type c in
zone z during time band b on any day of the forecast window [t, t + window_days).
Regression target: the number of such incidents.

Procedure
1. Chronological splits (train 2021-2024, validation 2025, test 2026 by default).
2. Percentile references for F and S fitted on training origins only.
3. Recency half-life per crime type tuned on validation (CRS PR-AUC).
4. XGBoost classifier and Poisson regressor trained on the training split.
5. Isotonic calibration of the classifier on validation.
6. Comparison on validation and test against a Random Forest (calibrated the same way),
   a historical-rate baseline, the explainable CRS, and the blended score.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score

from ml.evaluation.metrics import (
    best_f1_threshold,
    count_metrics,
    probability_metrics,
    ranking_metrics,
    reliability_table,
    top_k_capture,
)
from ml.features.builder import FeatureMatrix, build_matrix, targets
from ml.features.engine import FittedScoringState, finalise_components, fit_reference
from ml.features.registry import feature_label
from ml.models.registry import ModelBundle
from ml.pipeline import Inputs
from ml.scoring.formulas import recency_component
from ml.training.calibration import IsotonicCalibrator
from ml.training.splits import Splits, make_splits
from ml.versioning import feature_version, short_hash, utc_now

Log = Callable[[str], None]


def _xgb_params(inputs: Inputs) -> dict[str, Any]:
    p = inputs.cfg.training.xgb.model_dump()
    p["n_jobs"] = p["n_jobs"] or None
    return p


def _origin_mask(K: int, ks: np.ndarray) -> np.ndarray:
    m = np.zeros(K, dtype=bool)
    m[ks] = True
    return m


def tune_recency_half_life(
    inputs: Inputs, state: FittedScoringState, val: FeatureMatrix, y_val: np.ndarray
) -> dict[str, dict[str, float]]:
    """Per crime type, pick the half-life (days) that maximises validation CRS PR-AUC."""
    s = inputs.cfg.scoring
    panel, cp = inputs.panel, inputs.components
    comps = val.components
    w_r = s.crs_weights["R"]
    base_crs = val.flatten(comps["CRS"])
    base_r = val.flatten(comps["R"])
    days = np.repeat(cp.days_since[..., val.ks][:, :, None, :], len(panel.bands), axis=2)
    days = val.flatten(days)
    crime_idx = val.row_keys()["c"]
    results: dict[str, dict[str, float]] = {}
    for ci, code in enumerate(panel.crime_types):
        m = crime_idx == ci
        if y_val[m].sum() == 0:
            results[code] = {"chosen": s.recency_half_life_days_default}
            continue
        scores = {}
        for hl in s.recency_half_life_grid_days:
            r_new = recency_component(days[m], hl)
            crs = base_crs[m] - 100 * w_r * base_r[m] + 100 * w_r * r_new
            scores[str(hl)] = round(float(average_precision_score(y_val[m], crs)), 5)
        chosen = float(max(scores, key=scores.get))
        results[code] = {"chosen": chosen, **{f"pr_auc@{k}d": v for k, v in scores.items()}}
    return results


def _evaluate_block(
    name_scores: dict[str, tuple[str, np.ndarray]],
    y: np.ndarray,
    y_count: np.ndarray,
    shape: tuple[int, int, int, int],
    thresholds: dict[str, float],
    k_frac: float,
    crime_types: tuple[str, ...],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, (kind, score) in name_scores.items():
        if kind == "probability":
            m = probability_metrics(y, score, thresholds[name])
        else:
            m = ranking_metrics(y, score)
        cap = top_k_capture(score, y_count, shape, k_frac)
        cap["per_crime_type"] = {crime_types[c]: v for c, v in cap["per_crime_type"].items()}
        m["top_k"] = cap
        m["kind"] = kind
        out[name] = m
    return out


def train_models(inputs: Inputs, log: Log = print) -> ModelBundle:
    cfg = inputs.cfg
    s, tr = cfg.scoring, cfg.training
    panel, cp, grid = inputs.panel, inputs.components, inputs.grid
    t0 = time.time()

    splits: Splits = make_splits(
        panel, cp.windows.required_history, tr.splits.train_end, tr.splits.validation_end
    )
    log(f"splits: {splits.describe(panel)}")

    reference = fit_reference(cp, _origin_mask(panel.K, splits.train), panel, s)
    default_hl = {c: s.recency_half_life_days_default for c in panel.crime_types}
    state = FittedScoringState(reference=reference, recency_half_life_days=default_hl)

    mats = {
        name: build_matrix(panel, cp, state, grid, s, getattr(splits, name))
        for name in ("train", "validation", "test")
    }
    ys = {name: targets(panel, m.ks) for name, m in mats.items()}
    yb = {name: (y > 0).astype(np.int8) for name, y in ys.items()}
    log(
        "rows: "
        + ", ".join(f"{k}={m.n_rows:,} (positive {yb[k].mean():.3%})" for k, m in mats.items())
        + f" [{time.time() - t0:.0f}s]"
    )

    tuning = tune_recency_half_life(inputs, state, mats["validation"], yb["validation"])
    state.recency_half_life_days = {c: v["chosen"] for c, v in tuning.items()}
    for m in mats.values():  # recompute the CRS with the tuned half-lives
        m.components = finalise_components(cp, panel, state, s, m.ks)
    log(f"recency half-lives (days): {state.recency_half_life_days}")

    names = mats["train"].names
    params = _xgb_params(inputs)
    clf = xgb.XGBClassifier(objective="binary:logistic", eval_metric="aucpr", **params)
    clf.fit(mats["train"].X, yb["train"])
    clf.get_booster().feature_names = names
    log(f"xgboost classifier trained [{time.time() - t0:.0f}s]")
    reg = xgb.XGBRegressor(objective="count:poisson", **params)
    reg.fit(mats["train"].X, ys["train"])
    reg.get_booster().feature_names = names
    log(f"xgboost count regressor trained [{time.time() - t0:.0f}s]")

    # Data-driven comparison for the hand-set CRS weights: a logistic model on the same
    # seven components. Reported only; the configured weights stay a human decision.
    comp_names = list(s.crs_weights)

    def comp_matrix(split: str) -> np.ndarray:
        m = mats[split]
        return np.column_stack([m.flatten(m.components[c]) for c in comp_names])

    crs_lr = LogisticRegression(max_iter=500)
    crs_lr.fit(comp_matrix("train"), yb["train"])
    coef = np.clip(crs_lr.coef_[0], 0, None)
    suggested = (
        {c: round(float(v / coef.sum()), 3) for c, v in zip(comp_names, coef, strict=True)}
        if coef.sum()
        else {}
    )
    log(f"logistic weights on CRS components (normalised, >=0): {suggested}")

    rng = np.random.default_rng(0)
    n_rf = min(tr.rf.max_train_rows, mats["train"].n_rows)
    rf_idx = rng.choice(mats["train"].n_rows, n_rf, replace=False)
    rf = RandomForestClassifier(
        n_estimators=tr.rf.n_estimators,
        max_depth=tr.rf.max_depth,
        min_samples_leaf=tr.rf.min_samples_leaf,
        n_jobs=-1,
        random_state=0,
    )
    rf.fit(mats["train"].X[rf_idx], yb["train"][rf_idx])
    log(f"random forest trained on {n_rf:,} rows [{time.time() - t0:.0f}s]")

    raw = {n: clf.predict_proba(m.X)[:, 1] for n, m in mats.items() if n != "train"}
    rf_raw = {n: rf.predict_proba(m.X)[:, 1] for n, m in mats.items() if n != "train"}
    calib = IsotonicCalibrator.fit(raw["validation"], yb["validation"])
    rf_calib = IsotonicCalibrator.fit(rf_raw["validation"], yb["validation"])
    mu = {n: reg.predict(m.X) for n, m in mats.items() if n != "train"}

    def model_scores(split: str) -> dict[str, tuple[str, np.ndarray]]:
        m = mats[split]
        rate = m.X[:, names.index("b_r52")] / 52.0 * (panel.window_days / 7)
        p_cal = calib.predict(raw[split])
        crs = m.flatten(m.components["CRS"])
        return {
            "xgboost_calibrated": ("probability", p_cal),
            "xgboost_raw": ("probability", raw[split]),
            "random_forest_calibrated": ("probability", rf_calib.predict(rf_raw[split])),
            "historical_rate_baseline": ("probability", 1.0 - np.exp(-rate)),
            "crs_explainable": ("score", crs / 100.0),
            "crs_components_logistic": (
                "probability",
                crs_lr.predict_proba(comp_matrix(split))[:, 1],
            ),
            "blended_score": (
                "score",
                s.blend_ml_weight * p_cal + (1 - s.blend_ml_weight) * crs / 100.0,
            ),
        }

    val_scores = model_scores("validation")
    thresholds = {
        n: best_f1_threshold(yb["validation"], sc)
        for n, (kind, sc) in val_scores.items()
        if kind == "probability"
    }
    k_frac = tr.top_k_fraction
    metrics: dict[str, Any] = {
        "validation": _evaluate_block(
            val_scores,
            yb["validation"],
            ys["validation"],
            mats["validation"].shape,
            thresholds,
            k_frac,
            panel.crime_types,
        ),
    }
    test_scores = model_scores("test")
    metrics["test"] = _evaluate_block(
        test_scores,
        yb["test"],
        ys["test"],
        mats["test"].shape,
        thresholds,
        k_frac,
        panel.crime_types,
    )
    rate_test = mats["test"].X[:, names.index("b_r52")] / 52.0 * (panel.window_days / 7)
    metrics["test_counts"] = {
        "xgboost_poisson": count_metrics(ys["test"], mu["test"]),
        "historical_rate_baseline": count_metrics(ys["test"], rate_test),
    }

    # per crime type (test) for the deployed model and the CRS
    p_test = test_scores["xgboost_calibrated"][1]
    crs_test = test_scores["crs_explainable"][1]
    c_idx = mats["test"].row_keys()["c"]
    per_type = {}
    for ci, code in enumerate(panel.crime_types):
        m = c_idx == ci
        if yb["test"][m].sum() == 0 or yb["test"][m].sum() == m.sum():
            continue
        per_type[code] = {
            "rows": int(m.sum()),
            "base_rate": round(float(yb["test"][m].mean()), 5),
            "xgboost_calibrated": probability_metrics(
                yb["test"][m], p_test[m], thresholds["xgboost_calibrated"]
            ),
            "crs_explainable": ranking_metrics(yb["test"][m], crs_test[m]),
        }
    metrics["test_per_crime_type"] = per_type
    metrics["reliability"] = {
        "validation": reliability_table(yb["validation"], val_scores["xgboost_calibrated"][1]),
        "test": reliability_table(yb["test"], p_test),
    }
    metrics["confidence_bins_test"] = reliability_table(yb["test"], p_test, n_bins=20)

    booster = clf.get_booster()
    gain = booster.get_score(importance_type="gain")
    total_gain = sum(gain.values()) or 1.0
    importance = sorted(
        (
            {
                "feature": f,
                "label": feature_label(f, inputs.crime_labels),
                "gain_share": round(g / total_gain, 5),
            }
            for f, g in gain.items()
        ),
        key=lambda d: -d["gain_share"],
    )[:25]
    sample = rng.choice(mats["test"].n_rows, min(40_000, mats["test"].n_rows), replace=False)
    contrib = booster.predict(
        xgb.DMatrix(mats["test"].X[sample], feature_names=names), pred_contribs=True
    )[:, :-1]
    mean_abs = np.abs(contrib).mean(axis=0)
    shap_rank = sorted(
        (
            {
                "feature": f,
                "label": feature_label(f, inputs.crime_labels),
                "mean_abs_shap": round(float(v), 5),
            }
            for f, v in zip(names, mean_abs, strict=True)
        ),
        key=lambda d: -d["mean_abs_shap"],
    )[:25]

    trained_at = utc_now()
    blob = booster.save_raw("json")
    model_version = (
        f"CrimeForecast-XGB-{trained_at[:16].replace('-', '').replace(':', '')}Z-"
        f"{short_hash(bytes(blob), 6)}"
    )
    val_pr = {n: metrics["validation"][n]["pr_auc"] for n in val_scores}
    metadata = {
        "model_version": model_version,
        "trained_at": trained_at,
        "training_dataset_version": inputs.manifest["dataset_version"],
        "data_label": inputs.manifest["data_label"],
        "is_synthetic_data": inputs.manifest["is_synthetic"],
        "feature_version": feature_version(cfg.fingerprint("scoring", "time", "grid")),
        "feature_names": names,
        "crime_types": list(panel.crime_types),
        "bands": list(panel.bands),
        "window_days": panel.window_days,
        "target": {
            "classification": "At least one reported incident of the crime type in the zone "
            "during the time band on any day of the forecast window.",
            "regression": "Number of reported incidents of the crime type in the zone during "
            "the time band over the forecast window.",
        },
        "splits": {**splits.boundaries, **splits.describe(panel)},
        "required_history_windows": cp.windows.required_history,
        "xgboost_params": params,
        "random_forest_params": tr.rf.model_dump(),
        "recency_half_life_tuning": tuning,
        "decision_thresholds": thresholds,
        "crs_weights_configured": s.crs_weights,
        "crs_weights_suggested_by_logistic_fit": suggested,
        "model_selection": {
            "deployed": "xgboost_calibrated",
            "validation_pr_auc": val_pr,
            "note": "XGBoost is the deployed baseline; the other models are reported for "
            "comparison on the same validation and test windows.",
        },
        "feature_importance_gain": importance,
        "mean_abs_shap_test_sample": shap_rank,
        "top_k_fraction": k_frac,
        "training_seconds": round(time.time() - t0, 1),
    }
    log(f"done [{time.time() - t0:.0f}s]; model_version={model_version}")
    return ModelBundle(
        model_version=model_version,
        classifier=booster,
        regressor=reg.get_booster(),
        calibrator=calib,
        scoring_state=state,
        metadata=metadata,
        metrics=metrics,
    )
