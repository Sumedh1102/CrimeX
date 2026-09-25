# CrimeX — AI Crime Pattern Prediction & Detection Platform

An explainable spatiotemporal crime-intelligence platform for police-station decision
support, focused on Brihan Mumbai. The unit of every prediction is
`Risk(zone, crime_type, time_window)`: aggregated geographic zones only, never individuals.

> Predictions represent statistical patterns in historical reported incident data and are
> intended for analytical decision support. They are not guarantees of future criminal
> activity.

## Data

- **Official aggregate layer**: the Brihan Mumbai Police monthly statement (August 2026),
  extracted from `data/official/MumbaiCrime2026data.pdf` into validated JSON. City-level
  counts only; see [docs/data-dictionary.md](docs/data-dictionary.md).
- **Incident layer**: the official statement has no incident records, timestamps or
  coordinates, so the MVP uses a **SYNTHETIC / DEMONSTRATION** incident dataset whose
  city-wide volumes are anchored to the official counts. It is never real police data.

Work in progress; setup and commands are documented in `CLAUDE.md`.
