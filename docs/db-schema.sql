-- CrimeX proposed PostgreSQL + PostGIS schema.
--
-- Status: design. The MVP persists pipeline outputs as versioned Parquet/JSON artifacts
-- (see docs/architecture.md); these tables are the target once feedback, users and
-- station boundaries need transactional writes. Column names match the artifact fields.

CREATE EXTENSION IF NOT EXISTS postgis;

-- ------------------------------------------------------------------ reference data

CREATE TABLE police_stations (
    id              TEXT PRIMARY KEY,            -- e.g. SYN-PS-01 (synthetic in the MVP)
    name            TEXT NOT NULL,
    is_synthetic    BOOLEAN NOT NULL,
    location        GEOMETRY(Point, 4326),
    boundary        GEOMETRY(MultiPolygon, 4326) -- real jurisdiction when available
);

CREATE TABLE zones (
    id              TEXT PRIMARY KEY,            -- Z001 ... (grid cell)
    grid_version    TEXT NOT NULL,               -- config fingerprint of region + grid
    row_idx         INT NOT NULL,
    col_idx         INT NOT NULL,
    station_id      TEXT REFERENCES police_stations(id),
    centroid        GEOMETRY(Point, 4326) NOT NULL,
    boundary        GEOMETRY(Polygon, 4326) NOT NULL,
    land_fraction   REAL NOT NULL
);
CREATE INDEX zones_boundary_gix ON zones USING GIST (boundary);

CREATE TABLE zone_neighbors (
    zone_id         TEXT REFERENCES zones(id),
    neighbor_id     TEXT REFERENCES zones(id),
    distance_km     REAL NOT NULL,
    PRIMARY KEY (zone_id, neighbor_id)
);

CREATE TABLE crime_types (
    code            TEXT PRIMARY KEY,            -- ROBBERY_CHAIN_SNATCHING ...
    section         TEXT NOT NULL,               -- IPC, CAW, NDPS, BROTHELS, EOW, CYBER
    label_official  TEXT NOT NULL,               -- as printed in the official statement
    label           TEXT NOT NULL,               -- expanded official abbreviation
    parent_code     TEXT REFERENCES crime_types(code),
    spatially_modelled BOOLEAN NOT NULL,
    not_modelled_reason TEXT,
    severity        SMALLINT                     -- project-defined, not official
);

-- ------------------------------------------------------------- layer A: official

CREATE TABLE official_reports (
    id              SERIAL PRIMARY KEY,
    source_file     TEXT NOT NULL,
    source_sha256   TEXT NOT NULL UNIQUE,
    statement_month DATE NOT NULL,
    extractor_version TEXT NOT NULL,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE official_periods (
    report_id       INT REFERENCES official_reports(id),
    period_key      TEXT NOT NULL,               -- CM, PM, CY, PY
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    law_label       TEXT,                        -- 'IPC + BNS' / 'IPC' as printed
    PRIMARY KEY (report_id, period_key)
);

CREATE TABLE official_stats (
    report_id       INT REFERENCES official_reports(id),
    section         TEXT NOT NULL,
    head_code       TEXT NOT NULL,
    period_key      TEXT NOT NULL,               -- CM, PM, CY, PY, CY_VS_PY
    metric          TEXT NOT NULL,
    value           NUMERIC,                     -- NULL = blank cell in the source
    raw_text        TEXT NOT NULL,
    PRIMARY KEY (report_id, section, head_code, period_key, metric)
);

CREATE TABLE official_checks (
    report_id       INT REFERENCES official_reports(id),
    check_id        TEXT NOT NULL,
    description     TEXT NOT NULL,
    expected        NUMERIC,
    observed        NUMERIC,
    status          TEXT NOT NULL CHECK (status IN ('pass', 'discrepancy')),
    PRIMARY KEY (report_id, check_id)
);

-- ------------------------------------------------------------ layer B: incidents

CREATE TABLE crime_incidents (
    id              BIGSERIAL PRIMARY KEY,
    incident_id     TEXT NOT NULL UNIQUE,
    crime_type      TEXT NOT NULL REFERENCES crime_types(code),
    station_id      TEXT REFERENCES police_stations(id),
    zone_id         TEXT REFERENCES zones(id),
    occurred_at     TIMESTAMP NOT NULL,          -- local time
    band            TEXT NOT NULL,
    location        GEOMETRY(Point, 4326) NOT NULL,
    severity        SMALLINT,
    source          TEXT NOT NULL,               -- 'SYNTHETIC_DEMO' in the MVP
    dataset_version TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX crime_incidents_zone_time ON crime_incidents (zone_id, crime_type, occurred_at);
CREATE INDEX crime_incidents_location_gix ON crime_incidents USING GIST (location);

CREATE TABLE data_quality_reports (
    id              SERIAL PRIMARY KEY,
    dataset_version TEXT NOT NULL,
    generated_at    TIMESTAMPTZ NOT NULL,
    rows_in         INT NOT NULL,
    rows_out        INT NOT NULL,
    issues          JSONB NOT NULL               -- {check: {count, rate}}
);

-- ------------------------------------------------------------ models and outputs

CREATE TABLE model_versions (
    model_version   TEXT PRIMARY KEY,
    training_dataset_version TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    trained_at      TIMESTAMPTZ NOT NULL,
    train_period    DATERANGE NOT NULL,
    validation_period DATERANGE NOT NULL,
    test_period     DATERANGE NOT NULL,
    params          JSONB NOT NULL,
    metrics         JSONB NOT NULL
);

CREATE TABLE predictions (
    id              BIGSERIAL PRIMARY KEY,
    zone_id         TEXT NOT NULL REFERENCES zones(id),
    crime_type      TEXT NOT NULL REFERENCES crime_types(code),
    window_start    TIMESTAMP NOT NULL,
    window_end      TIMESTAMP NOT NULL,
    band            TEXT NOT NULL,               -- time-of-day band within the window
    risk_score      REAL NOT NULL,               -- blended score 0-100 (NOT a probability)
    crs             REAL NOT NULL,               -- explainable risk score 0-100
    probability     REAL NOT NULL,               -- calibrated P(>=1 incident in window/band)
    predicted_count REAL NOT NULL,
    confidence      TEXT NOT NULL,
    risk_band       TEXT NOT NULL,
    hotspot_state   TEXT,
    model_version   TEXT NOT NULL REFERENCES model_versions(model_version),
    training_dataset_version TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    generated_at    TIMESTAMPTZ NOT NULL,
    UNIQUE (zone_id, crime_type, window_start, band, model_version)
);

CREATE TABLE prediction_explanations (
    prediction_id   BIGINT REFERENCES predictions(id),
    kind            TEXT NOT NULL CHECK (kind IN ('crs_component', 'shap')),
    name            TEXT NOT NULL,
    raw_value       REAL,
    normalized_value REAL,
    contribution    REAL NOT NULL,
    PRIMARY KEY (prediction_id, kind, name)
);

CREATE TABLE crime_affinity (
    zone_id         TEXT REFERENCES zones(id),
    crime_type      TEXT REFERENCES crime_types(code),
    as_of           DATE NOT NULL,
    cai             REAL NOT NULL,
    a_spatial       REAL NOT NULL,
    a_recency       REAL NOT NULL,
    a_recurrence    REAL NOT NULL,
    a_consistency   REAL NOT NULL,
    location_quotient REAL NOT NULL,
    feature_version TEXT NOT NULL,
    PRIMARY KEY (zone_id, crime_type, as_of, feature_version)
);

CREATE TABLE hotspot_states (
    zone_id         TEXT REFERENCES zones(id),
    crime_type      TEXT REFERENCES crime_types(code),
    as_of           DATE NOT NULL,
    state           TEXT NOT NULL,               -- EMERGING, ACTIVE, PERSISTENT, DECLINING, SPORADIC, STABLE
    hot_fraction    REAL NOT NULL,
    trend_tau       REAL,
    trend_p         REAL,
    PRIMARY KEY (zone_id, crime_type, as_of)
);

CREATE TABLE anomalies (
    id              BIGSERIAL PRIMARY KEY,
    zone_id         TEXT REFERENCES zones(id),
    crime_type      TEXT REFERENCES crime_types(code),
    week_start      DATE NOT NULL,
    observed        INT NOT NULL,
    baseline_mean   REAL NOT NULL,
    baseline_std    REAL NOT NULL,
    z_score         REAL NOT NULL
);

-- ----------------------------------------------------------- users and feedback

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('ADMIN', 'STATION_OFFICER', 'ANALYST', 'SUPERVISOR', 'VIEWER')),
    station_id      TEXT REFERENCES police_stations(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feedback (
    id              BIGSERIAL PRIMARY KEY,
    prediction_id   BIGINT NOT NULL REFERENCES predictions(id),
    user_id         INT NOT NULL REFERENCES users(id),
    feedback_type   TEXT NOT NULL CHECK (feedback_type IN
                      ('CONFIRMED_PATTERN', 'NOT_RELEVANT', 'LOCAL_EVENT', 'DATA_ISSUE', 'OTHER')),
    comment         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
