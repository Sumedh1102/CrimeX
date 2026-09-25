# CrimeX — AI Crime Pattern Prediction & Detection Platform

An explainable spatiotemporal crime-intelligence platform for police-station decision
support, focused on Brihan Mumbai. It finds crime-type-specific hotspots, emerging patterns,
surges, and each area's historical crime affinity. It then forecasts area-level risk for the
coming week and explains every score from its measured inputs.

The unit of every prediction is `Risk(zone, crime_type, time_window)`: aggregated 1.5 km
zones, never individuals.

> Predictions represent statistical patterns in historical reported incident data and are
> intended for analytical decision support. They are not guarantees of future criminal
> activity.

## Data: two layers, never mixed

| Layer | Content | Use |
|---|---|---|
| **Official aggregate** | Brihan Mumbai Police monthly statement (August 2026 PDF), extracted into validated JSON: 6 sections, 85 heads, 621 values, 19 flagged source discrepancies | Official views, crime taxonomy, anchoring synthetic volumes |
| **Incident level** | **SYNTHETIC / DEMONSTRATION DATA** (the PDF has no incidents, times or places): about 92k simulated incidents, 2021 to Aug 2026, with city-wide volumes matching the official counts | Grid, hotspots, affinity, risk, ML |

See [docs/data-dictionary.md](docs/data-dictionary.md) and [docs/dataset.md](docs/dataset.md).

## What it computes

- **Crime Affinity Index (CAI, 0–100):** location quotient, recency, recurrence, consistency.
- **Hotspots:** Getis-Ord Gi* for any period, plus hotspot states (Emerging, Active,
  Persistent, Declining, Sporadic, Stable) from Gi* series and a Mann-Kendall trend.
- **Crime Surge Detector:** z-score alerts on last week's counts.
- **Explainable Crime Risk Score (CRS, 0–100):** frequency, recency, trend, affinity,
  neighbour pressure, temporal similarity, anomaly. Not a probability.
- **Calibrated probability** of at least one incident per zone, crime type and 6-hour band over
  the next 7 days (XGBoost + isotonic calibration). Compared with a Random Forest and a
  historical-rate baseline on a held-out 2026 period.
- **Explanations:** each signal's contribution with its raw inputs, TreeSHAP drivers, and
  "why is this zone flagged?" statements generated from actual values.
- **Crime Pattern Fingerprint** per crime type; a data-quality monitor; model versioning on
  every prediction.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
make pipeline     # generate data, preprocess, train, predict (about 4 minutes)
make api          # http://localhost:8000/docs
cd frontend && npm install && npm run dev    # http://localhost:3000
```

Tests: `make test` (Python), and `cd frontend && npm test && npm run lint && npm run typecheck`.

## Documentation

- [Architecture](docs/architecture.md)
- [Methodology](docs/methodology.md): exact formulas, windows and rules
- [Model card](docs/model-card.md): generated from the trained bundle
- [Datasets](docs/dataset.md) and [data dictionary](docs/data-dictionary.md)
- [Official statistics reference](docs/official-statistics-reference.md): generated from the PDF extraction
- [Proposed PostGIS schema](docs/db-schema.sql)
