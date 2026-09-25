# Data dictionary

CrimeX keeps two data layers strictly apart:

| Layer | What it is | Where it comes from | Used for |
|---|---|---|---|
| **A. Official aggregate** | City-level monthly/YTD counts exactly as printed | `data/official/MumbaiCrime2026data.pdf` (Brihan Mumbai Police statement, August 2026) | Official-statistics views, crime taxonomy, anchoring synthetic volumes |
| **B. Incident level** | One row per reported incident with time and place | **MVP: synthetic generator** (`source = SYNTHETIC_DEMO`). Later: a real incident feed | Everything spatial and temporal: grid, hotspots, CAI, risk, ML |

Layer A can never be presented as incidents, and layer B's synthetic rows can never be
presented as real police data. Every synthetic row, file, API payload, and UI view is
labelled **SYNTHETIC / DEMONSTRATION DATA**.

The full extracted values, consistency checks, and source notes are in the generated
[official-statistics-reference.md](official-statistics-reference.md).

## 1. What the official PDF contains

Six pages, each one table, all for **Brihan Mumbai as a whole**:

| Page | Section (`section` id) | Periods | Metrics |
|---|---|---|---|
| 1 | Comparative Statement of I.P.C. Crime (`IPC`) — 19 heads + total | Aug 2026, Jul 2026, 1 Jan–31 Aug 2026, 1 Jan–31 Aug 2025 | registered, detected, detection %, difference in registrations (2026 − 2025 YTD) |
| 2 | Comparative Statement of Crime Against Women (`CAW`) — 10 items, 24 rows incl. sub-rows and totals | same four periods | registered, detected, detection % |
| 3 | Comparative Statement of N.D.P.S. Cases (`NDPS`) — 7 drugs, possession, consumption, total | Aug 2026 | cases, persons arrested, quantity (kg / tablets / litres), value (unit not stated) |
| 4 | Cases on brothels (`BROTHELS`) — titled "zonewise" but only a Mumbai TOTAL row | Aug 2026, Jan–Aug 2026, Jan–Aug 2025 | cases, women rescued (major/minor), accused arrested |
| 5 | Cases registered by Economic Offences Wing (`EOW`) | same four periods | registered, detected, detection %, "Diff. in Reg." (as printed), property involved (Rs.) |
| 6 | Cyber Crime Headwise (`CYBER`) — 12 heads, Cheating with 13 sub-heads | Aug 2026 only | Reg., Det., PA (PA not defined in the source) |

Period keys used throughout: `CM` (current month), `PM` (previous month), `CY`
(current year to date), `PY` (previous year, same period), `CY_VS_PY` (difference).

### Discrepancies found in the source (kept as printed, flagged)

- IPC "Rape" (596/588 YTD 2026; 653/640 YTD 2025) differs from CAW "Total Rape Cases" (595/587; 652/641).
- IPC "Molestation" differs from CAW "Outraging Modesty of Women" in Jul 2026, YTD 2026 and YTD 2025 (e.g. 1677 vs 1666 for YTD 2025).
- CAW "Total Crime Against Women (excl. col. 9.1, 9.2 to 9.4)" cannot be reproduced from the listed rows; its composition is not stated.
- NDPS kilograms of individual drugs (excluding cough syrup) sum to 651.37 kg; the printed total is 652.20 kg.
- NDPS cough syrup quantity 123.20 is printed in the Kgs column but the totals carry it as litres.
- EOW "Diff. in Reg." prints 100, while 80 − 75 = 5.
- The previous-month column is headed "IPC" while the other periods are headed "IPC + BNS".

Everything else reconciles: all IPC columns sum to "Total IPC", every IPC difference and
detection % matches, NDPS cases/persons/values sum to their totals, and the cyber
sub-heads and heads sum to "Cheating" and "Total".

## 2. What it does NOT contain

| Needed for spatial-temporal ML | In the PDF? |
|---|---|
| Incident records / incident IDs | No |
| Timestamp, hour, weekday of an incident | No (only monthly and Jan–Aug totals) |
| Latitude / longitude | No |
| Police station of each incident | No |
| Zone / beat / ward breakdown | No (the brothel table is titled zonewise but has only a total) |
| Monthly time series | Only Jul 2026 and Aug 2026, plus two Jan–Aug totals |
| Place type (street, residence, transit …) | No |
| Severity | No |

**Consequence:** no geographic or temporal model can be trained from the PDF. It supports
the taxonomy, official KPIs (year-on-year change, detection rate), and the city-wide
volume and crime mix of the synthetic generator.

## 3. Official aggregate record (layer A)

Stored as JSON (`data/official/mumbai_police_statement_2026-08.json`), long format; maps
1:1 to the `official_stats` table in [db-schema.sql](db-schema.sql).

| Field | Type | Meaning |
|---|---|---|
| `section` | text | `IPC`, `CAW`, `NDPS`, `BROTHELS`, `EOW`, `CYBER` |
| `head` | text | Stable code of the printed head (see taxonomy below) |
| `period` | text | `CM`, `PM`, `CY`, `PY`, `CY_VS_PY` (dates in `periods`) |
| `metric` | text | `registered`, `detected`, `detection_pct`, `difference_registered`, `cases`, `persons_arrested`, `quantity_kg`, `quantity_tablets`, `quantity_litres`, `value`, `count`, `pa`, `property_involved_rs`, `difference_registered_as_printed` |
| `value` | number or null | Exactly as printed; `null` = blank cell (never silently zero) |
| `raw` | text | Original cell text |

Each head also records `label_official` (printed wording), `label_as_extracted`,
`label` (expanded official abbreviation, e.g. "H.B.T.Day" → "House Breaking Theft - Day"),
`parent`, `is_aggregate`, and `legal_reference` where printed.

## 4. Normalized crime taxonomy

Codes are identifiers only; the UI always shows the official label.

### Spatially modelled heads (MVP default, `configs/default.yaml → crime_types.modelled`)

| Code | Official head | Why modelled | Time constraint |
|---|---|---|---|
| `ROBBERY` | Robbery | Place-based street crime | — |
| `ROBBERY_CHAIN_SNATCHING` | Robbery Chain Snatching | Place-based street crime | — |
| `SNATCHING` | Snatching | Place-based street crime | — |
| `HBT_DAY` | H.B.T.Day (House Breaking Theft - Day) | Place-based property crime | 06:00–18:00 (by head definition) |
| `HBT_NIGHT` | H.B.T.Night. (House Breaking Theft - Night) | Place-based property crime | 18:00–06:00 (by head definition) |
| `THEFT` | Thefts. | Place-based, high volume | — |
| `MV_THEFT` | M.V.Thefts. (Motor Vehicle Thefts) | Place-based, high volume | — |
| `HURT` | Hurt | Public-place violence, high volume | — |
| `RIOTS` | Riots. | Public-order, place-based | — |

### Official-statistics only (reasons in `crime_types.not_modelled`)

`MURDER`, `ATTEMPT_TO_MURDER` (interpersonal, weakly place-dependent), `DACOITY`,
`PREPARATION_FOR_DACOITY`, `ATTEMPT_TO_ROBBERY` (very low volume), `EXTORTION` (no physical
place of occurrence), `RAPE`, `SEXUAL_OFFENCES_SEC69`, `MOLESTATION` (sensitive; large share
in non-public settings; can be enabled after review), `OTHER_IPC` (heterogeneous catch-all),
all `CAW_*`, `NDPS_*`, `BROTHEL_*`, `EOW_*` and `CYBER_*` heads (not place-of-occurrence
data). Enabling a head is a one-line config change once incident data supports it.

## 5. Field provenance

| Field | Official PDF | Needs incident-level data | Synthetic in MVP |
|---|---|---|---|
| Crime head taxonomy and labels | **Yes** | — | — |
| City-wide monthly / YTD counts per head | **Yes** (anchors synthetic volumes) | — | — |
| Detection counts and rates | **Yes** (official views only) | — | Not simulated |
| `incident_id` | No | Yes | Yes (`SYN-…`) |
| `timestamp` (date, hour) | No | Yes | Yes |
| `latitude`, `longitude` | No | Yes | Yes (inside the approximate study region) |
| `zone_id` | No | Derived from coordinates | Derived by gridding |
| `police_station_id` | No | Yes (or station boundaries) | Yes (`SYN-PS-01` … synthetic stations) |
| `severity` | No | Optional | Project-defined per head (config), not official |
| `source` | — | Yes | Always `SYNTHETIC_DEMO` |
| Hotspots, emerging/declining patterns, anomalies | No | Learned from incidents | Planted by the generator (ground truth kept separately for evaluation) |

## 6. Incident record (layer B, `crime_incidents`)

| Field | Type | Notes |
|---|---|---|
| `incident_id` | text | Unique; duplicates are removed by the quality monitor |
| `timestamp` | timestamp (local time, Asia/Kolkata implied) | Required |
| `crime_type` | text | Code from the modelled taxonomy |
| `latitude`, `longitude` | float (WGS84) | Required, must fall inside the active grid |
| `zone_id` | text | Grid cell (`Z001`…); recomputed from coordinates during preprocessing |
| `police_station_id` | text | Synthetic stations in the MVP |
| `severity` | int 1–5 | Project-defined |
| `source` | text | `SYNTHETIC_DEMO` for all MVP rows |
| `day_of_week`, `hour`, `month`, `is_weekend` | derived | Recomputed from `timestamp` |
| `band` | derived | Time band code (`NIGHT`, `MORNING`, `AFTERNOON`, `EVENING`) |

**Zone naming.** A CrimeX "zone" is a grid cell (1.5 km in the MVP). It is unrelated to
Mumbai Police DCP zones.

## 7. How synthetic volumes are anchored

For each modelled head *c*, the generator's expected city-wide daily rate is taken from
the IPC table's **registered** counts:

| Synthetic period | Daily rate | Basis |
|---|---|---|
| 2025-01-01 … 2025-08-31 | `PY / 243` | Official (Jan–Aug 2025) |
| 2026-01-01 … 2026-06-30 | `(CY − PM − CM) / 181` | Derived from official totals |
| 2026-07-01 … 2026-07-31 | `PM / 31` | Official (Jul 2026, column headed "IPC") |
| 2026-08-01 … 2026-08-31 | `CM / 31` | Official (Aug 2026) |
| 2025-09-01 … 2025-12-31 | linear between the 2025 and Jan–Jun 2026 rates | **Assumption** |
| 2021-01-01 … 2024-12-31 | `PY / 243` | **Assumption** (no official data for these years in the PDF) |

Where incidents occur, at what hour and weekday, and all hotspot, emerging, declining,
seasonal and surge patterns are **assumptions of the generator** (`synthetic.profiles` and
related settings). Analytics and models never read these settings; they must rediscover
the patterns from the incidents.
