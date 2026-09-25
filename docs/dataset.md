# Datasets

CrimeX uses two strictly separated layers. See [data-dictionary.md](data-dictionary.md) for
field-level definitions and provenance.

## Layer A: official aggregate statistics

- **Source:** `data/official/MumbaiCrime2026data.pdf`, the Brihan Mumbai Police statement for
  August 2026 (six sections: IPC crime, crime against women, NDPS, brothels, EOW, cyber crime).
- **Extraction:** `python scripts/extract_official_stats.py` → validated JSON at
  `data/official/mumbai_police_statement_2026-08.json`, with source SHA-256, printed labels,
  `null` for blank cells, 173 consistency checks and 19 flagged source discrepancies.
  `python scripts/build_official_reference.py` regenerates
  [official-statistics-reference.md](official-statistics-reference.md).
- **Use:** official-statistics views, the crime taxonomy, and the city-wide daily volumes of
  the synthetic generator. **Never** used as incident rows or model training data; it has no
  time or place detail.

## Layer B: incident data (MVP: synthetic)

**SYNTHETIC / DEMONSTRATION DATA.** No row is a real police incident. Every row carries
`source = SYNTHETIC_DEMO`, IDs start with `SYN-`, the output directory contains a README
saying so, and the API and UI display the label.

### Generation (`python scripts/generate_synthetic_data.py`, `ml/data/synthetic.py`)

Deterministic for a given seed (`synthetic.seed`), period 2021-01-01 to 2026-08-31, nine
modelled heads.

1. **City-wide volume (anchored).** Expected daily count per head from the official IPC
   registered counts: Jan–Aug 2025 (PY), Jan–Jun 2026 (CY − PM − CM), Jul 2026 (PM),
   Aug 2026 (CM). *Assumptions:* 2021–2024 held at the 2025 rate; Sep–Dec 2025 interpolated
   linearly; no intra-year seasonality (the source has none). Weekday weights are normalised to
   mean 1 so they redistribute, not add, volume.
2. **Where (assumed).** Smooth random activity and five latent place-type fields
   (commercial, residential, transit hub, industrial, entertainment) with per-head
   propensities; activity is damped inside an approximate forest/park polygon (Sanjay Gandhi
   National Park, Aarey). 6% of each head's volume is spread uniformly as background noise.
3. **Planted patterns (assumed; ground truth saved separately):**
   - 12 **persistent** hotspots (one per head plus three extra), 4 **seasonal** hotspots active
     for 6–10 weeks each year, 6 **emerging** hotspots ramping up over 4–10 weeks from 8–22
     weeks before the end, and 5 **declining** hotspots decaying with a 6–16 week half-life from
     dates in 2023–2025.
   - Each hotspot takes a share of its head's volume at a centre zone (2.5–5%, raised up to 2×
     for rare heads), with 25% of that spilling into each neighbouring zone, and has its own
     time-of-day signature.
   - 30 **surges** (short additive spikes, 5–12 days, at least 0.6 incidents/day or 6–10 × the
     zone's rate), 4 of them in the final forecast week.
4. **When (assumed).** Hour-of-day profiles per head (mixtures of circular Gaussians). H.B.T.
   Day is restricted to 06:00–18:00 and H.B.T. Night to 18:00–06:00, following the official
   head definitions.
5. **Record defects (injected).** 0.4% missing timestamps, 0.6% missing locations, 0.2% invalid
   coordinates (null island or swapped lat/lon), 0.2% unknown crime types, 0.3% duplicate
   records, so the data-quality monitor has real work. The monitor recovers each count exactly
   (tested).

Outputs in `data/raw/synthetic/`: `incidents_synthetic.csv`, `police_stations_synthetic.csv`
(12 stations `SYN-PS-01…` placed by k-means on activity), `zone_station_synthetic.csv`,
`ground_truth.json` and `ground_truth_components.parquet` (planted patterns; **evaluation
only**; analytics and models never read them), `generation_summary.json` (official vs
generated counts per anchor period).

### Preprocessing (`python scripts/preprocess_data.py`)

Quality checks (duplicates, missing and unparseable timestamps, missing locations, invalid
coordinates or points outside the grid, unknown crime types, timestamps at or after the
origin), zone assignment from coordinates, derived calendar fields and time band. Outputs in
`data/processed/`: `incidents.parquet`, `zones.parquet` and `zones.geojson`, `stations.parquet`,
`quality_report.json`, and `dataset_manifest.json` with the content-hashed
`dataset_version` (e.g. `Dataset-2026-09-01-005b2007`).

## Replacing synthetic data with real incidents

1. Export incidents as CSV with at least `incident_id, timestamp, crime_type, latitude,
   longitude` (optional `police_station_id, severity, source`), using the codes in
   `crime_types.modelled`.
2. Put it at `data/raw/synthetic/incidents_synthetic.csv` (or change `RAW_INCIDENTS` in
   `ml/preprocessing/pipeline.py`) and set a real `source` value.
3. Set `time.as_of` and the split dates in `configs/default.yaml`, then run
   `make preprocess train infer`. The synthetic label disappears automatically once no row has
   `source = SYNTHETIC_DEMO`.
4. Re-validate before any operational use: the metrics in the current model card do not
   transfer.
