# Methodology

Exact statistical definitions used by CrimeX. Every number here is a configurable value in
`configs/default.yaml` (defaults shown). Code references are given so each definition can be
checked against its implementation.

## 1. Units of analysis

**Zones.** A regular grid of 1.5 km square cells (`grid.cell_size_m`) over an approximate
Mumbai study region: bounding box ∩ a coarse clip outline ∩ a 1 km global land mask. A cell is
a zone when ≥ 50% of its 5 × 5 sample points are on land and inside the outline. Default: 226
zones, numbered `Z001…` in reading order from the north-west. The region is **not** an official
municipal or police boundary. (`ml/preprocessing/grid.py`)

**Time bands.** Four 6-hour bands partitioning the day: `NIGHT` 00–06, `MORNING` 06–12,
`AFTERNOON` 12–18, `EVENING` 18–24 (`time.bands`).

**Forecast windows.** 7-day windows (`time.window_days`) anchored at the forecast origin
`time.as_of` (default 2026-09-01). Origin *k* starts window *k*; the latest origin is
`as_of`, whose window is the forecast. Everything computed "at origin *k*" uses windows
strictly before *k*; this is enforced by construction and tested by altering target windows.
(`ml/preprocessing/panel.py`, `ml/features/rolling.py`)

**Prediction unit.** `Risk(zone z, crime type c, window starting at t, band b)`. Never a
person, household or demographic group.

**Event (classification target).** *Y = 1 if at least one reported incident of crime type c
occurs in zone z during band b on any day of the window [t, t + 7 days).*
**Regression target.** The number of such incidents.

## 2. Crime Affinity Index (CAI)

Computed per (zone, crime type) over the trailing 52 weeks before the origin, all bands.
(`ml/features/engine.py`, `ml/scoring/formulas.py`)

| Part | Definition |
|---|---|
| Location quotient | `LQ = (N_zc / N_z) / (N_c / N)`; 0 when a denominator is 0 |
| A_spatial | `log(1 + min(LQ, 10)) / log(1 + 10)` |
| A_recency | `Σ_{L=1..52} n_{k−L} · exp(−λ · 7 · (L − 0.5)) / N_zc`, λ = ln 2 / 90 days: the mean of exp(−λΔt) over incidents, with Δt taken at mid-week |
| A_recurrence | share of the 13 four-week periods in the window that contain ≥ 1 incident |
| A_consistency | `clip(1 − σ / (μ + 10⁻⁶), 0, 1)` over the 13 period counts (population σ); **0 when the zone has no incident of the type** |
| CAI | `100 · (0.45 A_spatial + 0.20 A_recency + 0.20 A_recurrence + 0.15 A_consistency)` |

Worked example (pinned by a test): components (0.92, 0.83, 0.88, 0.76) → CAI 87.0.

Affinity bands (presentation only): 0–20 Very Low, >20–40 Low, >40–60 Moderate, >60–80 High,
>80–100 Very High. Bands use inclusive upper bounds on the score rounded to one decimal.

## 3. Explainable Crime Risk Score (CRS)

At origin *k*, for (z, c, b). All components lie in [0, 1]. Band-level components use counts
in band *b*; zone-crime components use all bands.

| | Component | Definition |
|---|---|---|
| F | Frequency | `C_cur` = incidents of c in z during band b over the last 8 weeks. `F_raw = C_cur / (mean over zones of C_cur + 1)`. F = strict empirical CDF of F_raw against a reference distribution fitted on **training origins only**, per (c, b) (2,001-point quantile grid). No activity → 0. |
| R | Recency | d = days from the last incident of c in z (any band) to the origin. `R = exp(−ln 2 · d / h_c)`; no prior incident → 0. The half-life h_c is chosen per crime type from {3, 7, 14, 30, 60, 120} days to maximise validation CRS PR-AUC. |
| T | Trend | recent = incidents of c in z over the last 4 weeks; baseline = incidents in the 52 weeks before those × 4/52. `ratio = (recent − baseline) / (baseline + 1)`; `T = sigmoid(3 · (ratio − 0.5))`. |
| A | Affinity | `CAI / 100` |
| S | Neighbour pressure | `w_zj = 1 / (distance_km + 0.1)` for zones j ≠ z within 2 cells (Chebyshev). `S_raw = (Σ w_zj C_cur,j / Σ w_zj) / (mean over zones of C_cur + 1)`, percentile-normalised like F. |
| P | Temporal similarity | h = the zone's band profile for c over 52 weeks, smoothed toward the city-wide profile with 10 pseudo-incidents: `h_b = (n_b + 10 s_b) / (n + 10)`. `P = cos(h, e_b) = h_b / ‖h‖₂`, where e_b is the one-hot vector of the requested band. |
| X | Anomaly (CSD) | current = incidents of c in z last week; μ, σ = mean and std of the 52 weeks before. `z = (current − μ) / (σ + 0.5)`; `X = min(1, max(0, z) / 3)`. |

`CRS = 100 · (0.20 F + 0.15 R + 0.15 T + 0.20 A + 0.10 S + 0.10 P + 0.10 X)`.
Worked example (pinned by a test): F..X = (0.80, 0.90, 0.75, 0.87, 0.65, 0.92, 0.55) → 79.35.
Each component's contribution `100 · w · value` is stored, and the contributions sum exactly
to the CRS.

**The CRS is a composite indicator, not a probability.** Risk bands (presentation only):
0–20 LOW, >20–40 MODERATE, >40–60 ELEVATED, >60–80 HIGH, >80–100 VERY HIGH.

### Deviations from the handbook, and why

- **F uses a cross-sectional baseline** (the average zone for the same crime type, band and
  window) rather than the zone's own history. The zone's own history is already used by T and
  X, and this keeps the three components from being affine transforms of each other.
- **T and X are computed at zone-crime level** (all bands), because band-level weekly counts
  are too sparse for stable ratios and z-scores. F, S and P stay band-specific.
- **A_consistency is 0 without incidents.** The literal formula gives 1 for an all-zero
  series, which would award affinity to zones with no history of the crime.
- **X uses ε = 0.5.** ε only prevents division by zero; ε = 1 damped genuine surges below the
  alert threshold in testing.
- **P is computed over the four time bands.** A 24-hour profile would make the cosine reward
  spread within the band rather than concentration in it.

## 4. Calibrated probability and blended score

- `probability`: an XGBoost classifier's output mapped through an isotonic calibration fitted
  on the validation period. It is the only number presented as a probability, always with the
  event definition above.
- `final_risk` (blended score) = `100 · (0.6 · probability + 0.4 · CRS / 100)`. A score, not a
  probability.
- `expected_count`: an XGBoost Poisson regressor's prediction for the window and band.
- `confidence` (evidence strength): LOW if the zone had fewer than 3 incidents of the crime type
  in the last 52 weeks, or the held-out calibration gap near this probability exceeds 0.05;
  HIGH if at least 12 incidents and a gap ≤ 0.02; MEDIUM otherwise. The gap is
  |observed − predicted| in the test-period reliability bin (20 quantile bins) containing the
  probability.

## 5. Hotspot Detection Engine (Getis-Ord Gi*)

For zone counts x over a chosen period (24 h, 7 d, 30 d, 90 d, 6 m, 1 y before the origin, or a
custom range), with binary queen-contiguity weights including the zone itself:

`G*_i = (Σ_j w_ij x_j − x̄ Σ_j w_ij) / (S · sqrt((n Σ_j w_ij² − (Σ_j w_ij)²) / (n − 1)))`,
with x̄ and S the mean and population standard deviation of x. Two-sided normal p-values.
Classes: Hot/Cold spot at 99% (|z| ≥ 2.576), 95% (≥ 1.96) and 90% (≥ 1.645); otherwise Not
significant. Optional Benjamini-Hochberg FDR (`hotspots.fdr_correction`, off by default).
(`ml/analytics/gistar.py`, `ml/analytics/hotspots.py`)

## 6. Emerging Hotspot Detection (hotspot states)

For each crime type, Gi* is computed for each of the last 26 four-week periods before the
origin. A zone is *hot* in a period when z ≥ 1.96. A Mann-Kendall test (tie-corrected,
continuity-corrected) on the zone's Gi* series gives the trend (significant at p < 0.05).
Rules, applied in order (`ml/analytics/hotspot_states.py`):

| State | Rule |
|---|---|
| PERSISTENT | hot in ≥ 80% of periods and no significant downward trend |
| DECLINING | hot in ≥ 50% of the first 13 periods, and (significant downward trend or not hot in any of the last 3) |
| EMERGING | hot in ≥ 2 of the last 3 periods, hot in ≤ 15% of the earlier periods, and the recent incident rate > 1.5 × the earlier rate |
| ACTIVE | hot in the final period |
| SPORADIC | hot in ≥ 2 periods, not the final one |
| STABLE | otherwise |

The planned lifecycle (NORMAL → EMERGING → ACTIVE → PERSISTENT → DECLINING → RESOLVED) will
track these states over successive origins.

## 7. Crime Surge Detector (CSD)

A separate layer from the forecasting model. Per (zone, crime type) the z-score of last week's
count vs the previous 52 weeks (section 3, X). A **surge alert** is raised when z ≥ 3 and the
count ≥ 3. The capped z feeds the CRS as X. (`ml/analytics/anomaly.py`)

## 8. Crime Pattern Fingerprint (CPF)

Per crime type over the trailing 52 weeks, each dimension in [0, 1]
(`ml/analytics/fingerprint.py`): spatial concentration (Gini of zone counts), time
concentration (1 − normalised hour entropy), weekend concentration (weekend share ÷ (2/7) ÷
2), repeat location (incident-weighted mean A_recurrence), neighbour spillover (global Moran's
I, queen weights, clipped at 0), recent trend (T for the city-wide 4 weeks vs 52-week rate),
hotspot persistence (share of hot zone-periods belonging to PERSISTENT zones), temporal
similarity (cosine of the last 8 weeks' hour profile to the 52-week profile). Labels: LOW < 1/3
≤ MEDIUM < 2/3 ≤ HIGH.

## 9. Forecasting model

- **Features** (55, `ml/features/registry.py`): band-level lags (1–4 weeks, same week last
  year) and rolling counts (8, 13, 26, 52 weeks); zone-crime lags and rolling counts; days since
  the last incident; zone totals; neighbour-weighted counts; city-wide rates and trend; the CRS
  components F, S, T, P, X, the anomaly z, CAI and its four parts, the LQ; calendar (week of year
  sin/cos, month); one-hot crime type and band; zone position. All use windows before the
  origin only.
- **Splits**: train 2021–2024, validation 2025, test 2026-01-01 → as_of, by window start, with a
  boundary embargo. The first 56 weeks of the data are feature history only.
- **Models**: XGBoost classifier (deployed) and Poisson regressor; Random Forest (400k-row
  training sample) and a historical-rate baseline `P = 1 − exp(−rate)` (rate = band count per
  week over 52 weeks) for comparison; a logistic regression on the seven CRS components as a
  data-driven check on the hand-set weights (reported, not applied).
- **Calibration**: isotonic regression on validation predictions.
- **Explainability**: TreeSHAP (`pred_contribs`) on the uncalibrated classifier (log-odds);
  isotonic calibration is monotone, so directions carry over. The "why flagged" statements are
  templates filled with the measured inputs of components whose value exceeds a display
  threshold (`ml/explainability/narrative.py`).

### Metrics (`ml/evaluation/metrics.py`)

PR-AUC (average precision), ROC-AUC, Brier score, log loss, expected calibration error (10
equal-width bins), reliability table (quantile bins), and precision / recall / F1 at the
threshold maximising validation F1. For counts: MAE, RMSE, Poisson deviance. **Top-K capture**:
for each (window, crime type, band), take the K = ⌈10% of zones⌉ highest-ranked zones; capture =
incidents in those zones ÷ all incidents, pooled over groups. **PAI** = capture ÷ (K / number of
zones). Scores that are not probabilities (CRS, blended) get ranking metrics only.

## 10. Limitations

- The incident layer is synthetic; its spatial, hourly and weekday patterns are generator
  assumptions (see [dataset.md](dataset.md)). Metrics describe the pipeline, not real-world
  accuracy.
- Reported crime reflects reporting and recording practices; a model trained on it can
  reproduce and amplify those biases, especially through attention feedback loops.
- Rare crime heads have base rates below 1% per zone, band and week; their probabilities are
  small and uncertain.
- The study region and station outlines are approximations for demonstration.
- Scores describe associations in historical reported data, never causes or certainties.
