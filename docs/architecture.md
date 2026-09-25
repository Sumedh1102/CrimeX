# Architecture

```
                 ┌──────────────────────────── Python (ml/) ─────────────────────────────┐
 Official PDF ──►│ official extraction ─► validated JSON (layer A, aggregates)           │
                 │                                                                       │
 Incidents  ────►│ quality monitor ─► gridding (zones) ─► weekly count panel             │
 (synthetic in   │      │                                        │                       │
  the MVP)       │      ▼                                        ▼                       │
                 │ data_quality report          feature engine: CAI, F R T A S P X,      │
                 │                              lags/rolling counts, neighbours          │
                 │                                        │                              │
                 │     hotspot engine (Gi*) ◄─────────────┤                              │
                 │     hotspot states (Gi* + Mann-Kendall)│                              │
                 │     surge detector (CSD, feeds X)      ▼                              │
                 │                         XGBoost (+RF, baseline) ─► isotonic calibration│
                 │                                        │                              │
                 │                         inference: probability, CRS, blended score,   │
                 │                         SHAP, reasons, versions ─► artifacts/         │
                 └───────────────────────────────────────┬───────────────────────────────┘
                                                         │ Parquet / JSON (versioned)
                                         FastAPI (backend/, Pydantic) /api/v1
                                                         │  JSON
                                  Next.js (frontend/) — rewrite /api/v1 → FastAPI
                                  map, dashboard, zone panel, analytics pages
```

## Components

| Path | Responsibility |
|---|---|
| `ml/data/official/` | Parse the official PDF into long-format records with provenance; consistency checks |
| `ml/data/synthetic.py` | Anchored synthetic incident generator (SYNTHETIC / DEMONSTRATION) |
| `ml/preprocessing/` | Grid (`grid.py`), data-quality monitor (`quality.py`), processed dataset (`pipeline.py`), count panel (`panel.py`) |
| `ml/features/` | Leak-safe rolling operations, component engine (CAI, F…X), percentile references, model matrix, feature registry |
| `ml/analytics/` | Gi* hotspots, Mann-Kendall, hotspot states, surge detector, crime pattern fingerprint |
| `ml/scoring/` | Formula handbook (CAI, CRS, blended score) and display bands |
| `ml/training/`, `ml/evaluation/` | Chronological splits, training, calibration, metrics |
| `ml/models/registry.py` | JSON-only model bundles (`artifacts/models/<version>/`) |
| `ml/explainability/` | TreeSHAP top contributions; template "why flagged" statements |
| `ml/inference/predict.py` | Versioned predictions for the forecast window |
| `backend/` | FastAPI app: read-only services over the artifacts, Pydantic schemas |
| `frontend/` | Next.js dashboard; displays API values only |
| `scripts/` | CLI entry points for each pipeline step |
| `configs/default.yaml` | Every tunable value (grid, bands, weights, bands, splits, generator assumptions) |

## Storage

The MVP stores pipeline outputs as versioned files, which keeps the whole system runnable
without a database server:

```
data/official/                         official PDF + extracted JSON (committed)
data/raw/synthetic/                    generated incidents and ground truth (gitignored)
data/processed/                        cleaned incidents, zones, quality report, dataset manifest
artifacts/models/<model_version>/      classifier, regressor, calibrator, scoring state, metadata, metrics
artifacts/predictions/<as_of>__<model>/ predictions, zone × crime table, CRS history, manifest
```

`backend/app/services/store.py` is the only reader, behind one interface. The target schema
for PostgreSQL + PostGIS is in [db-schema.sql](db-schema.sql); it becomes necessary once
officer feedback, users/RBAC and real station boundaries need transactional writes. At that
point a PostGIS-backed store can implement the same interface.

## Versioning

Every prediction row records:

- `model_version`: e.g. `CrimeForecast-XGB-20260925T1119Z-5cc819` (training timestamp + hash of the booster)
- `training_dataset_version` and `input_dataset_version`: content hashes of the cleaned incidents, e.g. `Dataset-2026-09-01-005b2007`
- `feature_version`: e.g. `FeatureSet-1.0-4d0d26` (code version + hash of the scoring/time/grid config)
- `generated_at`: UTC timestamp

## API (`/api/v1`)

| Method & path | Returns |
|---|---|
| `GET /health` | readiness and versions |
| `GET /meta` | data label, limitation statement, forecast window, bands, crime types, display bands, versions |
| `GET /crime-types` | modelled heads (official labels) and heads kept out of modelling, with reasons |
| `GET /crime-types/{code}/profile` · `/fingerprint` · `/affinity` | crime-type page data |
| `GET /official/summary` | official statistics by section, checks, discrepancies, notes |
| `GET /stations` | synthetic stations |
| `GET /zones` | zone grid as GeoJSON |
| `GET /zones/{zone_id}?crime_type&band` | zone intelligence panel |
| `GET /predictions?crime_type&band` | risk layer (ALL = highest crime-type/band-specific value per zone) |
| `POST /predict` | `{zone_id, crime_type, window: "7d", band?}` → stored prediction with drivers |
| `GET /hotspots?crime_type&period&start&end&band` | Gi* map (24h, 7d, 30d, 90d, 6m, 1y, custom) |
| `GET /emerging-hotspots?crime_type` | hotspot states and top emerging zones |
| `GET /affinity?crime_type` | CAI layer |
| `GET /anomalies?crime_type` | surge alerts and layer |
| `GET /dashboard/summary?crime_type&station_id` | KPIs, emerging zones, alerts, trend and distributions |
| `GET /model` | model card data |
| `GET /data-quality` | quality report and dataset manifest |
| `GET /incidents` | filtered incident records (synthetic in the MVP) |

Interactive docs are served at `http://localhost:8000/docs`.

## Frontend

Next.js 16 App Router with client components. `src/lib/api.ts` has typed SWR hooks, and
responses keep their previous render while refetching. `src/lib/store.ts` (Zustand) holds the
single filter row shared by every page. `src/components/map/` is MapLibre with canvas-generated
icons, textures and labels, so it works without a glyph server. `src/components/zone/` is the
intelligence panel. The browser calls `/api/v1/*` on the Next origin, and `next.config.ts`
rewrites to `CRIMEX_API_URL`.

## Deployment (suggested)

- Frontend: Vercel (set `CRIMEX_API_URL`).
- Backend and ML: one container (Render, Railway or a cloud VM) running
  `make pipeline && uvicorn backend.main:app`. Artifacts can live on the container disk for the
  demo; move them to object storage or PostGIS for multi-instance deployments.
