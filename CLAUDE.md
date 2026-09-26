# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

MVP vertical slice built: official-statistics extraction, anchored synthetic incident data with a quality monitor, 1.5 km grid, CAI, Gi* hotspots, hotspot states, surge detector, XGBoost baseline with calibration and SHAP, explainable risk score, FastAPI, and a Next.js dashboard. The source of truth is the project specification ("AI Crime Pattern Prediction & Detection Platform — Project Specification and AI Formula Handbook") plus the user's Mumbai-focused master context. Exact definitions are in `docs/methodology.md`; data provenance is in `docs/data-dictionary.md` and `docs/dataset.md`.

## Commands

Python (3.11, from the repo root):

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # or: uv venv && uv pip install -e ".[dev]"
make install         # venv + Python deps + frontend npm install in one step
make pipeline        # synthetic data -> preprocess -> train -> predictions (about 4 min); or: data, preprocess, train, infer
make api             # uvicorn backend.main:app --reload --port 8000  (docs: /docs)
make web             # Next.js dashboard on :3000 (needs `make api` running)
make test            # pytest ml/tests backend/tests (builds a small pipeline in tmp dirs, about 1 min)
make lint            # ruff check + ruff format --check (make format to fix)
.venv/bin/python -m pytest ml/tests/test_scoring.py::test_cai_worked_example_is_87      # one test
.venv/bin/python -m pytest backend/tests/test_api.py -k zone_detail                     # one API test
make official        # re-extract the official PDF + regenerate docs/official-statistics-reference.md
.venv/bin/python scripts/build_model_card.py   # regenerate docs/model-card.md from the latest bundle
```

Frontend (`frontend/`, Node 22; read `frontend/AGENTS.md` first — this Next.js version differs from older training data, and its docs live in `frontend/node_modules/next/dist/docs/`):

```bash
cd frontend && npm install
npm run dev                          # http://localhost:3000, proxies /api/v1 to CRIMEX_API_URL (default :8000)
npm run lint && npm run typecheck
npm test                             # vitest
npx vitest run src/lib/layers.test.ts -t "probability"   # one test
npm run build
```

## Decisions made (keep consistent)

- **Two data layers, never mixed.** `data/official/` holds the Brihan Mumbai statement (city-level aggregates, as printed, with discrepancy flags). All spatial and temporal work runs on incident data, which is **synthetic** in the MVP (`source = SYNTHETIC_DEMO`, anchored to the official monthly counts).
- **Modelled heads** (`configs/default.yaml → crime_types.modelled`): Robbery, Robbery Chain Snatching, Snatching, H.B.T. Day/Night, Thefts, M.V. Thefts, Hurt, Riots. Other heads are official-statistics only, with reasons in `crime_types.not_modelled`. UI text uses the official labels (`ml/data/official/taxonomy.py`).
- **Prediction unit:** zone (1.5 km cell) × crime type × 7-day window × 6-hour band. The event for the probability is "≥1 incident in the band on any day of the window".
- **Study region and stations are approximations** (land mask + outline; synthetic `SYN-PS-xx` stations). Never present them as official boundaries.
- **Storage:** versioned Parquet/JSON artifacts read through `backend/app/services/store.py`. The PostGIS schema in `docs/db-schema.sql` is the target once feedback and users need writes.
- **Leakage:** features at origin k only use windows < k (`ml/features/rolling.py`); splits embargo boundary-straddling windows. Keep the leakage tests passing.
- **Config over constants:** weights, windows, bands, thresholds and generator assumptions live in `configs/default.yaml`.
- **Dataviz:** map and chart colors come from `frontend/src/lib/colors.ts` (validated ramps). Every layer also uses labels, icons or textures, and every chart card has a table view.
- **Basemap is optional decoration.** `frontend/src/lib/basemap.ts` probes a provider chain (custom `NEXT_PUBLIC_MAP_STYLE_URL`, CARTO vector, OpenFreeMap, CARTO raster) and falls back, including at runtime, to the bundled offline reference map (`frontend/public/geo/`, OSM/ODbL, built by `scripts/build_reference_basemap.py`). Overlays must keep working with no tile server; zone fills go under basemap labels. Locality names (`frontend/src/lib/localities.ts`) are approximate and display-only.

## What the product is

An explainable spatiotemporal crime-intelligence platform for police stations. It is decision support, not "crime prediction". The fundamental unit of every prediction is **`Risk(zone, crimeType, timeWindow)`**, never `Risk(zone)` and never anything about an individual.

## Non-negotiable domain rules

These cut across the UI, API, ML, and reports, so every layer must respect them:

- **Never imply certainty.** Use "elevated predicted risk", "high-risk area based on historical patterns", "emerging crime pattern", "attention priority". Never "crime will happen here". Reports and the UI carry the limitation statement: *"Predictions represent statistical patterns in historical reported incident data and are intended for analytical decision support. They are not guarantees of future criminal activity."*
- **No individual-level profiling.** Operate on aggregated geographic zones only; never label a person as a likely offender.
- **Three distinct numbers, never conflated:**
  - **Crime Affinity (CAI, 0–100):** historical association of a zone with a crime type (statistical, not causal).
  - **Risk Score (CRS, 0–100):** a normalized composite indicator. It is **not a probability**.
  - **Calibrated probability:** only from a calibrated ML classifier, for a precisely defined event Y (e.g. "≥1 incident of type c in zone z during the window").
- **Explanations must trace to actual model inputs and outputs** (formula components, SHAP, feature importance), never text generated after the fact.
- **Synthetic data must be labeled** as synthetic/demonstration data everywhere it surfaces (the `source` field, UI, reports), never presented as real police incidents.
- **Crime-to-place associations are learned from data**, never hard-coded.
- **Display bands are configurable presentation values**, not scientific thresholds. Default risk bands: 0–20 LOW, 21–40 MODERATE, 41–60 ELEVATED, 61–80 HIGH, 81–100 VERY HIGH. Affinity uses the same cut points (Very Low … Very High).
- **Every forecast has an explicit time window**, and every stored prediction records `model_version`, `training_dataset_version`, `feature_version`, and `generated_at`.

## Architecture

```
Next.js (UI, map, charts) -> /api/v1 rewrite -> FastAPI (Pydantic) -> ML package outputs (artifacts/) ; PostgreSQL + PostGIS planned
```

Layout: `frontend/` (Next.js 16 + TypeScript + Tailwind v4, MapLibre GL v6, Recharts, Framer Motion, Zustand, SWR), `backend/app/{api,services,schemas,utils}` + `backend/main.py`, `ml/{data,preprocessing,features,analytics,scoring,training,models,evaluation,explainability,inference}`, `scripts/` (one CLI per pipeline step), `configs/default.yaml`, `docs/` (`architecture.md`, `methodology.md`, `model-card.md` (generated), `dataset.md`, `data-dictionary.md`, `official-statistics-reference.md` (generated), `db-schema.sql`). See `docs/architecture.md`.

All data processing, feature engineering, training, inference, anomaly detection, clustering, and explainability live in Python. The frontend only consumes API results and must not re-derive scores.

The data flow that ties modules together:

```
raw incidents -> data quality -> geospatial gridding (zones) -> crime-type profiling
  -> hotspots / affinity / fingerprints -> feature engineering (temporal, spatial, anomaly)
  -> ML model -> risk + forecast -> risk score / hotspot state / pattern match
  -> XAI -> dashboard -> officer feedback -> dataset -> model update
```

Anomaly/surge detection (CSD) is a **separate layer** from the forecasting model; its output feeds the risk score as the `X` component.

Hotspot states: Active, Persistent, Declining, Emerging, Sporadic, Stable. Lifecycle: NORMAL → EMERGING → ACTIVE → PERSISTENT → DECLINING → RESOLVED.

## Scoring formulas (from the spec's formula handbook)

Notation: `N_(z,c)` = incidents of type c in zone z, `N_z` = all incidents in z, `N_c` = all incidents of type c, `N` = all incidents. Every component must be normalized to [0,1] before weighting; never combine raw values with different units.

**Crime Affinity Index**
- Location Quotient: `LQ = (N_(z,c)/N_z) / (N_c/N)`. Capped: `LQ' = min(LQ, LQ_cap)`, prototype `LQ_cap = 10`. Spatial component: `A_spatial = log(1+LQ') / log(1+LQ_cap)`.
- `A_recency = mean_i(exp(-λ·Δt_i))`
- `A_recurrence = periods containing c / observed periods`
- `A_consistency = clip(1 - σ(C_(z,c)) / (μ(C_(z,c)) + ε), 0, 1)`
- `CAI = 100·(0.45·A_spatial + 0.20·A_recency + 0.20·A_recurrence + 0.15·A_consistency)`

**Crime Risk Score components**
- F (frequency): `C_current / (C_baseline + ε)`, then percentile-normalized (preferred over capping).
- R (recency): `exp(-λ·d)`, where d = days since the last similar incident. λ is tuned on validation and may differ per crime type.
- T (trend): `ratio = (C_recent - C_baseline)/(C_baseline + ε)`, then `T = sigmoid(k·(ratio - b))`.
- A (affinity): `CAI / 100`.
- S (neighbor pressure): `Σ w_zj·C_j / Σ w_zj` over neighbors, with `w_zj = 1/(distance + ε)`, then normalized.
- P (temporal similarity): cosine similarity between the crime type's historical time-distribution vector and the current-context vector.
- X (anomaly): `z = (C_current - μ_hist)/(σ_hist + ε)`, then `X = min(1, max(0, z)/z_cap)`.
- `R_explainable = 0.20F + 0.15R + 0.15T + 0.20A + 0.10S + 0.10P + 0.10X`, and `CRS = 100·R_explainable`.
- Blended final: `FinalRisk = 100·(0.60·P_ML + 0.40·R_explainable)`.

The weights are starting design values. Keep them configurable and tune or compare them against learned models on validation data. Worked examples in the spec that tests can pin: CAI with components (0.92, 0.83, 0.88, 0.76) = **87.0**; CRS with F..X = (0.80, 0.90, 0.75, 0.87, 0.65, 0.92, 0.55) = **79.35**.

## ML rules

- Start with a tabular baseline (XGBoost/LightGBM, with Random Forest for comparison) before any deep model. ConvLSTM / ST-ResNet / GNN models must be justified by measured improvement over the baseline.
- Targets: classification (the zone enters a defined high-risk state in the next window) or regression (expected incident count). The exact statistical definition must be documented.
- **Time-ordered splits only**, never random (e.g. train 2021–2024, validate 2025 H1, test 2025 H2). Watch for leakage in rolling and lag features.
- Evaluate with MAE, RMSE, precision/recall/F1, PR-AUC, Brier score, calibration, and top-K hotspot capture rate. Accuracy alone is insufficient.
- Calibrate probabilities before showing them as percentages.

## Build order

Deliver a complete working vertical slice before breadth. The MVP, in order: synthetic dataset → map → geographic grid → crime-type filter → historical hotspot map → CAI → emerging hotspot detection → XGBoost prediction → explainable risk score → zone detail panel. **All of these are done**, plus a first crime pattern fingerprint, the surge detector (alerts and the anomaly layer) and official-statistics views. Next phases: hotspot lifecycle over successive origins, hotspot movement, historical pattern matching, clustering, the feedback loop with PostGIS persistence, station dashboards and multi-scale views, reports, a 24-hour window (`time.window_days: 1`), scenario simulation, RBAC (ADMIN, STATION_OFFICER, ANALYST, SUPERVISOR, VIEWER), and advanced models only if they beat the baseline.

Synthetic data schema: `incident_id, timestamp, crime_type, latitude, longitude, zone_id, police_station_id, severity, source` (optional: `day_of_week, hour, month, is_weekend`). The generator must produce recurring, emerging, and declining hotspots, crime-type concentration, time-dependent patterns, background noise, anomalies, and neighbor-zone relationships, so that every module has signal to find.

UI direction: dark, restrained analytics dashboard, map-first, compact cards, clean typography. Avoid a movie-like military look. Encode map states with icons, labels, and patterns as well as color.
