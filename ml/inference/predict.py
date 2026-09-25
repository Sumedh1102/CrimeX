"""Generate versioned predictions for the forecast window starting at ``as_of``.

For every (zone, crime type, time band) the output keeps the three numbers separate:

* ``probability``   calibrated P(>= 1 reported incident in the zone, band and window)
* ``crs``           explainable risk score (0-100, not a probability) and its components
* ``final_risk``    blended score 100 * (w * probability + (1 - w) * crs / 100)

plus CAI (per zone and crime type), hotspot state, surge statistics, SHAP drivers, and
"why flagged" statements generated from the component inputs. Every row records
model_version, training_dataset_version, feature_version and generated_at.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.analytics.anomaly import surge_table
from ml.analytics.hotspot_states import classify_states
from ml.config import LIMITATION_STATEMENT
from ml.explainability.narrative import ReasonInputs, reasons
from ml.explainability.shap_values import top_contributions
from ml.features.builder import build_matrix
from ml.features.engine import finalise_components
from ml.models.registry import ModelBundle
from ml.pipeline import Inputs
from ml.scoring.bands import assign_bands, round_score
from ml.scoring.formulas import CRS_COMPONENTS, blended_risk, crs_contributions
from ml.versioning import utc_now

HISTORY_WINDOWS = 12


def confidence_labels(
    p: np.ndarray, support: np.ndarray, bins: list[dict]
) -> tuple[np.ndarray, np.ndarray]:
    """Evidence-strength label for each probability.

    LOW    fewer than 3 incidents of this type in the zone in the last 52 weeks, or the
           held-out calibration gap near this probability exceeds 0.05
    HIGH   at least 12 such incidents and a calibration gap of at most 0.02
    MEDIUM otherwise
    """
    upper = np.array([b["p_max"] for b in bins])
    gaps = np.array([abs(b["observed_rate"] - b["mean_predicted"]) for b in bins])
    idx = np.clip(np.searchsorted(upper, p, side="left"), 0, len(bins) - 1)
    gap = gaps[idx]
    label = np.full(p.shape, "MEDIUM", dtype=object)
    label[(support >= 12) & (gap <= 0.02)] = "HIGH"
    label[(support < 3) | (gap > 0.05)] = "LOW"
    return label, gap


def generate_predictions(inputs: Inputs, bundle: ModelBundle) -> dict[str, Any]:
    cfg, panel, cp, grid = inputs.cfg, inputs.panel, inputs.components, inputs.grid
    s = cfg.scoring
    if list(panel.crime_types) != bundle.metadata["crime_types"]:
        raise ValueError("Model was trained on different crime types")
    k = panel.W  # origin == as_of
    generated_at = utc_now()
    Z, C, B = len(panel.zones), len(panel.crime_types), len(panel.bands)
    labels = inputs.crime_labels
    band_labels = {b.code: b.label for b in cfg.time.bands}
    window_start = panel.origins[k]
    window_end = window_start + pd.Timedelta(days=panel.window_days)

    fm = build_matrix(panel, cp, bundle.scoring_state, grid, s, np.array([k]))
    if fm.names != bundle.feature_names:
        raise ValueError("Feature definitions differ from the trained model")
    p_raw = bundle.predict_raw_probability(fm.X)
    p = bundle.predict_probability(fm.X)
    mu = bundle.predict_count(fm.X)
    comps = {name: fm.flatten(fm.components[name]) for name in (*CRS_COMPONENTS, "CRS")}
    contrib = crs_contributions(comps, s.crs_weights)
    crs = comps["CRS"]
    final = blended_risk(p, crs / 100.0, s.blend_ml_weight)
    keys = fm.row_keys()
    zi, ci, bi = keys["z"], keys["c"], keys["b"]

    shap = bundle.shap_values(fm.X)[:, :-1]
    shap_top = top_contributions(shap, fm.X, fm.names, cfg.training.shap_top_k, labels)

    states = classify_states(panel.zc_counts, k, grid, panel.crime_types, cfg.hotspots)
    states_idx = states.set_index(["zone_id", "crime_type"])
    surges = surge_table(cp, k, panel.zones, panel.crime_types, s)

    support = cp.zc_r52[zi, ci, k]
    conf, gap = confidence_labels(p, support, bundle.metrics["confidence_bins_test"])

    zone_ids = np.array(panel.zones)[zi]
    crime_codes = np.array(panel.crime_types)[ci]
    band_codes = np.array(panel.bands)[bi]
    state_col = [
        states_idx.loc[(z, c), "state"] for z, c in zip(zone_ids, crime_codes, strict=True)
    ]
    win = cp.windows
    reason_rows = []
    for r in range(len(p)):
        z, c, b = zi[r], ci[r], bi[r]
        st = states_idx.loc[(zone_ids[r], crime_codes[r])]
        reason_rows.append(
            reasons(
                ReasonInputs(
                    crime_label=labels[crime_codes[r]],
                    band_label=band_labels[band_codes[r]],
                    components={n: float(comps[n][r]) for n in CRS_COMPONENTS},
                    contributions={n: float(contrib[n][r]) for n in CRS_COMPONENTS},
                    current_band_count=float(cp.current_b[z, c, b, k]),
                    city_mean_band_count=float(cp.city_mean_current_b[0, c, b, k]),
                    frequency_weeks=win.frequency,
                    trend_recent=float(cp.trend_recent[z, c, k]),
                    trend_baseline=float(cp.trend_baseline[z, c, k]),
                    trend_weeks=win.trend_recent,
                    cai=float(cp.cai[z, c, k]),
                    lq=float(cp.lq[z, c, k]),
                    days_since=float(cp.days_since[z, c, k]),
                    nbr_weighted=float(cp.nbr_current_b[z, c, b, k]),
                    band_share=float(cp.band_share[z, c, b, k]),
                    surge_current=float(cp.anomaly_current[z, c, k]),
                    surge_mean=float(cp.anomaly_mean[z, c, k]),
                    surge_z=float(cp.anomaly_z[z, c, k]),
                    hotspot_state=st["state"],
                    hot_periods=int(st["hot_periods"]),
                    n_periods=int(st["n_periods"]),
                    recent_hot_periods=int(st["recent_hot_periods"]),
                )
            )
        )

    versions = {
        "model_version": bundle.model_version,
        "training_dataset_version": bundle.metadata["training_dataset_version"],
        "input_dataset_version": inputs.manifest["dataset_version"],
        "feature_version": bundle.metadata["feature_version"],
        "generated_at": generated_at,
    }
    crs_r = round_score(crs)
    final_r = round_score(final)
    cai_rows = cp.cai[zi, ci, k]
    pred = pd.DataFrame(
        {
            "prediction_id": [
                f"P-{window_start:%Y%m%d}-{z}-{c}-{b}"
                for z, c, b in zip(zone_ids, crime_codes, band_codes, strict=True)
            ],
            "zone_id": zone_ids,
            "crime_type": crime_codes,
            "band": band_codes,
            "window_start": window_start,
            "window_end": window_end,
            "probability": np.round(p, 5),
            "probability_raw": np.round(p_raw, 5),
            "expected_count": np.round(mu, 4),
            "confidence": conf,
            "calibration_gap": np.round(gap, 5),
            "support_incidents_52w": support.astype(int),
            "crs": crs_r,
            "crs_band": assign_bands(crs_r, s.risk_bands),
            "final_risk": final_r,
            "risk_band": assign_bands(final_r, s.risk_bands),
            "cai": round_score(cai_rows),
            "affinity_band": assign_bands(round_score(cai_rows), s.affinity_bands),
            "hotspot_state": state_col,
            **{f"comp_{n}": np.round(comps[n], 4) for n in CRS_COMPONENTS},
            **{f"contrib_{n}": np.round(contrib[n], 3) for n in CRS_COMPONENTS},
            # raw inputs behind the band-level components (for display, never re-scored)
            "raw_F_band_count": cp.current_b[zi, ci, bi, k].astype(int),
            "raw_F_city_mean": np.round(cp.city_mean_current_b[0, ci, bi, k], 3),
            "raw_S_neighbour_mean": np.round(cp.nbr_current_b[zi, ci, bi, k], 3),
            "raw_P_band_share": np.round(cp.band_share[zi, ci, bi, k], 4),
            "recency_half_life_days": [
                bundle.scoring_state.recency_half_life_days[c] for c in crime_codes
            ],
            "shap_top": [json.dumps(x) for x in shap_top],
            "shap_bias_log_odds": np.round(bundle.shap_values(fm.X[:1])[0, -1], 4),
            "reasons": [json.dumps(x) for x in reason_rows],
            **versions,
            "data_label": inputs.manifest["data_label"],
        }
    )

    # zone x crime-type table: affinity, hotspot state, surge statistics
    zz, cc = np.meshgrid(np.arange(Z), np.arange(C), indexing="ij")
    zc = pd.DataFrame(
        {
            "zone_id": np.array(panel.zones)[zz.ravel()],
            "crime_type": np.array(panel.crime_types)[cc.ravel()],
            "cai": round_score(cp.cai[..., k].ravel()),
            "affinity_band": assign_bands(round_score(cp.cai[..., k].ravel()), s.affinity_bands),
            "a_spatial": np.round(cp.a_spatial[..., k].ravel(), 4),
            "a_recency": np.round(cp.a_recency[..., k].ravel(), 4),
            "a_recurrence": np.round(cp.a_recurrence[..., k].ravel(), 4),
            "a_consistency": np.round(cp.a_consistency[..., k].ravel(), 4),
            "location_quotient": np.round(cp.lq[..., k].ravel(), 3),
            "incidents_52w": cp.zc_r52[..., k].ravel().astype(int),
            "incidents_4w": cp.zc_r4[..., k].ravel().astype(int),
            "days_since_last": np.round(cp.days_since[..., k].ravel(), 2),
            "trend_recent_4w": cp.trend_recent[..., k].ravel().astype(int),
            "trend_baseline_4w": np.round(cp.trend_baseline[..., k].ravel(), 3),
            "trend_ratio": np.round(cp.T_ratio[..., k].ravel(), 3),
            "T": np.round(cp.T[..., k].ravel(), 4),
        }
    )
    zc = zc.merge(states, on=["zone_id", "crime_type"], how="left")
    zc = zc.merge(
        surges.rename(
            columns={
                "current_count": "surge_current_count",
                "baseline_mean": "surge_baseline_mean",
                "baseline_std": "surge_baseline_std",
                "z_score": "surge_z",
                "deviation_pct": "surge_deviation_pct",
                "is_alert": "surge_alert",
            }
        ),
        on=["zone_id", "crime_type"],
        how="left",
    )
    for col in ("gi_z_series", "count_series"):
        zc[col] = zc[col].map(json.dumps)
    for key, val in versions.items():
        zc[key] = val

    # CRS history for the last windows (risk explanation timeline)
    ks = np.arange(max(cp.windows.required_history, k - HISTORY_WINDOWS + 1), k + 1)
    hist_comps = finalise_components(cp, panel, bundle.scoring_state, s, ks)
    hk, hz, hc, hb = np.meshgrid(ks, np.arange(Z), np.arange(C), np.arange(B), indexing="ij")

    def flat(a):
        return np.moveaxis(a, -1, 0).ravel()

    history = pd.DataFrame(
        {
            "zone_id": np.array(panel.zones)[hz.ravel()],
            "crime_type": np.array(panel.crime_types)[hc.ravel()],
            "band": np.array(panel.bands)[hb.ravel()],
            "window_start": panel.origins[hk.ravel()],
            "crs": np.round(flat(hist_comps["CRS"]), 2),
            **{n: np.round(flat(hist_comps[n]), 4) for n in CRS_COMPONENTS},
            "observed_count": np.concatenate(
                [
                    np.moveaxis(panel.counts[..., kk : kk + 1], -1, 0).ravel()
                    if kk < panel.W
                    else np.full(Z * C * B, -1)
                    for kk in ks
                ]
            ),
        }
    )

    manifest = {
        **versions,
        "as_of": window_start.date().isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "window_days": panel.window_days,
        "bands": [b.model_dump() for b in cfg.time.bands],
        "crime_types": [{"code": c, "label": labels[c]} for c in panel.crime_types],
        "event_definition": (
            "At least one reported incident of the crime type in the zone during the time "
            "band on any day of the forecast window."
        ),
        "scores": {
            "probability": "Calibrated probability of the event (isotonic calibration on the "
            "validation period). The only number that is a probability.",
            "crs": "Explainable Crime Risk Score (0-100): weighted sum of normalised components "
            "F, R, T, A, S, P, X. A composite indicator, not a probability.",
            "final_risk": f"Blended score = 100 x ({s.blend_ml_weight} x probability + "
            f"{1 - s.blend_ml_weight:.2f} x CRS/100). A score, not a probability.",
            "cai": "Crime Affinity Index (0-100): historical association of the zone with the "
            "crime type. Statistical association, not causation.",
        },
        "crs_weights": s.crs_weights,
        "cai_weights": s.cai_weights,
        "risk_bands": s.risk_bands,
        "affinity_bands": s.affinity_bands,
        "data_label": inputs.manifest["data_label"],
        "is_synthetic_data": inputs.manifest["is_synthetic"],
        "limitation_statement": LIMITATION_STATEMENT,
        "counts": {
            "predictions": len(pred),
            "surge_alerts": int(zc["surge_alert"].sum()),
            "states": zc["state"].value_counts().to_dict(),
        },
    }
    return {"predictions": pred, "zone_crime": zc, "history": history, "manifest": manifest}


def write_predictions(out: dict[str, Any], predictions_dir: Path) -> Path:
    m = out["manifest"]
    name = f"{m['as_of']}__{m['model_version']}"
    d = predictions_dir / name
    d.mkdir(parents=True, exist_ok=True)
    out["predictions"].to_parquet(d / "predictions.parquet", index=False)
    out["zone_crime"].to_parquet(d / "zone_crime.parquet", index=False)
    out["history"].to_parquet(d / "crs_history.parquet", index=False)
    (d / "manifest.json").write_text(json.dumps(m, indent=2, default=str), encoding="utf-8")
    (predictions_dir / "LATEST").write_text(name + "\n", encoding="utf-8")
    return d
