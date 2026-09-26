// Types mirroring the FastAPI v1 responses (backend/app/services/analytics.py).

export type RiskBand = "LOW" | "MODERATE" | "ELEVATED" | "HIGH" | "VERY HIGH";
export type AffinityBand = "Very Low" | "Low" | "Moderate" | "High" | "Very High";
export type HotspotState =
  | "EMERGING"
  | "ACTIVE"
  | "PERSISTENT"
  | "DECLINING"
  | "SPORADIC"
  | "STABLE";
export type Confidence = "LOW" | "MEDIUM" | "HIGH";
export type HotspotClass =
  | "HOT_99"
  | "HOT_95"
  | "HOT_90"
  | "NOT_SIGNIFICANT"
  | "COLD_90"
  | "COLD_95"
  | "COLD_99";
export type LayerKey = "risk" | "hotspots" | "states" | "affinity" | "anomalies";
export type RiskMetric = "final_risk" | "crs" | "probability";

export interface Versions {
  model_version: string;
  training_dataset_version: string;
  input_dataset_version: string;
  feature_version: string;
  generated_at: string;
}

export interface ForecastWindow {
  start: string;
  end: string;
  days: number;
  label: string;
}

export interface TimeBand {
  code: string;
  label: string;
  start_hour: number;
  end_hour: number;
}

export interface CrimeTypeMeta {
  code: string;
  label: string;
  label_official: string;
  severity: number | null;
}

export interface BandRange {
  label: string;
  min: number;
  max: number;
}

export interface Meta {
  platform: string;
  title: string;
  data_label: string;
  is_synthetic: boolean;
  limitation_statement: string;
  as_of: string;
  forecast_window: ForecastWindow;
  event_definition: string;
  score_definitions: Record<string, string>;
  bands: TimeBand[];
  crime_types: CrimeTypeMeta[];
  risk_bands: BandRange[];
  affinity_bands: BandRange[];
  hotspot_states: { code: HotspotState; description: string }[];
  hotspot_classes: { code: HotspotClass; label: string }[];
  periods: string[];
  versions: Versions;
  data_range: { start: string; end: string };
  region: {
    name: string;
    description: string;
    bbox: [number, number, number, number];
    center: [number, number];
    cell_size_m: number;
    n_zones: number;
  };
  n_stations: number;
  crs_weights: Record<string, number>;
  cai_weights: Record<string, number>;
  blend_ml_weight: number;
}

export interface ZoneProps {
  zone_id: string;
  row: number;
  col: number;
  station_id: string | null;
  station_name: string | null;
  land_fraction: number;
}

export interface ZoneFeature {
  type: "Feature";
  id: number;
  properties: ZoneProps;
  geometry: { type: "Polygon"; coordinates: number[][][] };
}

export interface ZonesGeoJSON {
  type: "FeatureCollection";
  features: ZoneFeature[];
}

export interface RiskItem {
  zone_id: string;
  crime_type: string;
  band: string;
  final_risk: number;
  risk_band: RiskBand;
  crs: number;
  crs_band: RiskBand;
  probability: number;
  confidence: Confidence;
  expected_count: number;
  hotspot_state: HotspotState;
  cai: number;
  affinity_band: AffinityBand;
}

export interface RiskLayer {
  crime_type: string;
  band: string;
  aggregation: string | null;
  window: ForecastWindow;
  items: RiskItem[];
  summary: Partial<Record<RiskBand, number>>;
  versions: Versions;
}

export interface HotspotItem {
  zone_id: string;
  count: number;
  density_per_km2: number;
  gi_z: number;
  gi_p: number;
  hotspot_class: HotspotClass;
}

export interface HotspotsResponse {
  crime_type: string;
  band: string;
  period: string;
  start: string;
  end: string;
  method: string;
  items: HotspotItem[];
  summary: { total_incidents: number; classes: Partial<Record<HotspotClass, number>> };
}

export interface StateItem {
  zone_id: string;
  crime_type: string;
  state: HotspotState;
  hot_periods: number;
  n_periods: number;
  recent_hot_periods: number;
  final_period_hot: boolean;
  current_hot_run_periods: number;
  trend: string;
  trend_tau: number;
  trend_p: number;
  gi_z_last: number;
  recent_rate: number;
  prior_rate: number;
}

export interface EmergingItem {
  zone_id: string;
  station_id: string | null;
  crime_type: string;
  label: string;
  recent_rate: number;
  prior_rate: number;
  hot_periods: number;
  recent_hot_periods: number;
  final_risk: number | null;
  risk_band: RiskBand | null;
  band: string | null;
  trend: string;
}

export interface StatesResponse {
  crime_type: string;
  as_of: string;
  analysis: { period_weeks: number; n_periods: number; hot_z: number };
  items: StateItem[];
  summary: Partial<Record<HotspotState, number>>;
  top_emerging: EmergingItem[];
}

export interface AffinityItem {
  zone_id: string;
  crime_type: string;
  cai: number;
  affinity_band: AffinityBand;
  a_spatial: number;
  a_recency: number;
  a_recurrence: number;
  a_consistency: number;
  location_quotient: number;
  incidents_52w: number;
}

export interface AffinityResponse {
  crime_type: string;
  as_of: string;
  window_weeks: number;
  weights: Record<string, number>;
  aggregation: string | null;
  items: AffinityItem[];
}

export interface SurgeItem {
  zone_id: string;
  crime_type: string;
  surge_current_count: number;
  surge_baseline_mean: number;
  surge_baseline_std: number;
  surge_z: number;
  surge_deviation_pct: number | null;
  surge_alert: boolean;
  X: number;
  label?: string;
  station_id?: string | null;
}

export interface AnomaliesResponse {
  crime_type: string;
  as_of: string;
  detection_window: { start: string; end: string };
  method: string;
  alerts: SurgeItem[];
  items: SurgeItem[];
}

export interface ShapItem {
  feature: string;
  label: string;
  group: string;
  value: number;
  shap_log_odds: number;
  direction: "raises" | "lowers";
}

export interface Reason {
  component: string;
  text: string;
  contribution_points: number | null;
}

export interface ComponentDetail {
  code: string;
  name: string;
  description: string;
  value: number;
  weight: number;
  contribution: number;
  raw: Record<string, number | null>;
}

export interface ZoneDetail {
  zone: {
    zone_id: string;
    row: number;
    col: number;
    centroid: [number, number];
    station_id: string | null;
    station_name: string | null;
    land_fraction: number;
    area_km2: number;
  };
  crime_type: string;
  crime_label: string;
  band: string;
  band_label: string;
  window: ForecastWindow;
  prediction: {
    prediction_id: string;
    event_definition: string;
    probability: number;
    probability_raw: number;
    confidence: Confidence;
    calibration_gap: number;
    support_incidents_52w: number;
    expected_count: number;
    crs: number;
    crs_band: RiskBand;
    final_risk: number;
    risk_band: RiskBand;
    blend_ml_weight: number;
    components: ComponentDetail[];
    reasons: Reason[];
    shap: { bias_log_odds: number; top: ShapItem[] };
  };
  bands: {
    band: string;
    label: string;
    final_risk: number;
    risk_band: RiskBand;
    probability: number;
    crs: number;
    crs_band: RiskBand;
    expected_count: number;
  }[];
  risk_profile: {
    crime_type: string;
    label: string;
    band: string;
    final_risk: number;
    risk_band: RiskBand;
    probability: number;
    crs: number;
  }[];
  affinity_profile: {
    crime_type: string;
    label: string;
    cai: number;
    affinity_band: AffinityBand;
    a_spatial: number;
    a_recency: number;
    a_recurrence: number;
    a_consistency: number;
    location_quotient: number;
    incidents_52w: number;
    state: HotspotState;
  }[];
  hotspot_state: {
    state: HotspotState;
    hot_periods: number;
    n_periods: number;
    hot_fraction: number;
    recent_hot_periods: number;
    final_period_hot: boolean;
    current_hot_run_periods: number;
    trend: string;
    trend_tau: number;
    trend_p: number;
    gi_z_last: number;
    gi_z_series: number[];
    count_series: number[];
    recent_rate: number;
    prior_rate: number;
    period_weeks: number;
    description: string;
  };
  surge: {
    current_count: number;
    baseline_mean: number;
    baseline_std: number;
    z_score: number;
    deviation_pct: number | null;
    is_alert: boolean;
  };
  history: {
    weekly: ({ week_start: string; count: number } & Record<string, number | string>)[];
    hourly_52w: number[];
    crs_timeline: ({
      window_start: string;
      crs: number;
      observed_count: number;
    } & Record<string, number | string>)[];
  };
  recent_incidents: {
    incident_id: string;
    timestamp: string;
    band: string;
    severity: number;
    source: string;
  }[];
  versions: Versions;
  data_label: string;
  limitation_statement: string;
}

export interface Dashboard {
  filters: { crime_type: string; station_id: string | null };
  as_of: string;
  window: ForecastWindow;
  kpis: {
    active_hotspots: number;
    emerging_hotspots: number;
    current_anomalies: number;
    high_risk_zones: number;
    zones: number;
  };
  kpi_definitions: Record<string, string>;
  top_emerging: EmergingItem[];
  top_crime_types: {
    crime_type: string;
    label: string;
    last_52w: number;
    last_4w: number;
    prev_4w: number;
    change_pct: number | null;
  }[];
  alerts: {
    zone_id: string;
    crime_type: string;
    label: string;
    current_count: number;
    baseline_mean: number;
    z_score: number;
    deviation_pct: number | null;
    station_id: string | null;
  }[];
  trend: ({ week_start: string } & Record<string, number | string>)[];
  distribution: { crime_type: string; label: string; count: number }[];
  hourly: { hour: number; count: number }[];
  weekday: { day: string; count: number }[];
  lifecycle: { state: HotspotState; count: number }[];
  data_label: string;
  versions: Versions;
}

export interface Station {
  station_id: string;
  name: string;
  latitude: number;
  longitude: number;
  is_synthetic: boolean;
  zones: number;
}

export interface FingerprintDim {
  name: string;
  value: number;
  label: "LOW" | "MEDIUM" | "HIGH";
}

export interface CrimeTypeProfile {
  crime_type: string;
  label: string;
  label_official: string;
  severity: number | null;
  official: {
    data_nature: string;
    note: string;
    values: Record<
      string,
      | { period: { label: string; start: string; end: string }; registered: number | null; detected: number | null }
      | number
      | null
    >;
  };
  incident_data: { data_label: string; last_52w: number; last_4w: number; total: number };
  weekly_104w: { week_start: string; count: number }[];
  time_profile: {
    hourly: number[];
    bands: { band: string; label: string; count: number }[];
    weekday: number[];
    calendar: { rows: string[]; columns: string[]; counts: number[][] };
  };
  fingerprint: {
    crime_type: string;
    window: { start: string; end: string };
    incidents: number;
    dimensions: FingerprintDim[];
    details: {
      weekend_share: number;
      weekend_lift: number;
      morans_i: number;
      recent_4w: number;
      baseline_4w: number;
      trend_direction: string;
      peak_hours: number[];
    };
  };
  top_zones_affinity: {
    zone_id: string;
    cai: number;
    affinity_band: AffinityBand;
    location_quotient: number;
    incidents_52w: number;
    state: HotspotState;
    station_id: string | null;
  }[];
  top_zones_risk: {
    zone_id: string;
    band: string;
    final_risk: number;
    risk_band: RiskBand;
    probability: number;
    crs: number;
    hotspot_state: HotspotState;
    station_id: string | null;
  }[];
  states_summary: Partial<Record<HotspotState, number>>;
  emerging: EmergingItem[];
  anomalies: { zone_id: string; surge_current_count: number; surge_baseline_mean: number; surge_z: number }[];
  versions: Versions;
}

export interface OfficialHead {
  code: string;
  sr: string | null;
  label_official: string;
  label: string;
  parent: string | null;
  is_aggregate: boolean;
  legal_reference: string | null;
  spatially_modelled: boolean;
  values: Record<string, Record<string, number | null>>;
}

export interface OfficialSummary {
  data_nature: string;
  note: string;
  report: Record<string, string>;
  periods: Record<string, { label: string; start: string; end: string; law_label_as_printed: string | null }>;
  sections: { id: string; title: string; page: number; heads: OfficialHead[] }[];
  checks_summary: { total: number; passed: number; discrepancies: number };
  discrepancies: {
    id: string;
    section: string;
    description: string;
    expected: number | null;
    observed: number | null;
  }[];
  source_notes: { id: string; description: string }[];
  extraction_notes: string[];
}

export interface CrimeTypesResponse {
  modelled: (CrimeTypeMeta & { section: string; allowed_hours: [number, number] | null })[];
  not_modelled: { code: string; label: string; label_official: string; reason: string }[];
}

export interface ProbabilityMetrics {
  pr_auc: number;
  roc_auc: number;
  brier?: number;
  log_loss?: number;
  ece?: number;
  threshold?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  base_rate?: number;
  kind: "probability" | "score";
  top_k: {
    k_zones: number;
    k_fraction: number;
    capture_rate: number;
    oracle_capture_rate: number;
    pai: number;
    per_crime_type: Record<string, number>;
  };
}

export interface ModelCard {
  metadata: {
    model_version: string;
    trained_at: string;
    training_dataset_version: string;
    data_label: string;
    is_synthetic_data: boolean;
    feature_version: string;
    crime_types: string[];
    bands: string[];
    window_days: number;
    target: { classification: string; regression: string };
    splits: Record<string, unknown>;
    xgboost_params: Record<string, unknown>;
    random_forest_params: Record<string, unknown>;
    recency_half_life_tuning: Record<string, Record<string, number>>;
    decision_thresholds: Record<string, number>;
    crs_weights_configured: Record<string, number>;
    crs_weights_suggested_by_logistic_fit: Record<string, number>;
    model_selection: { deployed: string; validation_pr_auc: Record<string, number>; note: string };
    feature_importance_gain: { feature: string; label: string; gain_share: number }[];
    mean_abs_shap_test_sample: { feature: string; label: string; mean_abs_shap: number }[];
    top_k_fraction: number;
    training_seconds: number;
  };
  metrics: {
    validation: Record<string, ProbabilityMetrics>;
    test: Record<string, ProbabilityMetrics>;
    test_counts: Record<string, { mae: number; rmse: number; poisson_deviance: number }>;
    test_per_crime_type: Record<
      string,
      {
        rows: number;
        base_rate: number;
        xgboost_calibrated: ProbabilityMetrics;
        crs_explainable: { pr_auc: number; roc_auc: number };
      }
    >;
    reliability: Record<
      string,
      { mean_predicted: number; observed_rate: number; n: number; p_min: number; p_max: number }[]
    >;
  };
  limitation_statement: string;
}

export interface DataQuality {
  dataset: {
    dataset_version: string;
    created_at: string;
    as_of: string;
    sources: string[];
    is_synthetic: boolean;
    data_label: string;
    rows: number;
    timestamp_range: { min: string; max: string };
    n_zones: number;
    crime_types: string[];
    cell_size_m: number;
  };
  report: {
    rows_in: number;
    rows_out: number;
    rows_rejected: number;
    checks: {
      id: string;
      label: string;
      rows_rejected: number;
      rate: number;
      rows_with_issue: number;
      action: string;
    }[];
    sources: Record<string, number>;
    crime_type_counts: Record<string, number>;
  };
  note: string;
}

// ---------------------------------------------------------------- lifecycle / movement

export type LifecycleStage = "NORMAL" | "EMERGING" | "ACTIVE" | "PERSISTENT" | "DECLINING" | "RESOLVED";

export interface AnalysisSettings {
  period_weeks: number;
  period_windows: number | null;
  n_periods: number;
  hot_z: number;
  steps: number;
}

export interface LifecycleStep {
  step: number;
  period_start: string;
  period_end: string;
}

export interface LifecycleOverview {
  crime_type: string;
  as_of: string;
  analysis: AnalysisSettings;
  stages: { stage: LifecycleStage; description: string }[];
  steps: (LifecycleStep & Record<LifecycleStage, number>)[];
  transitions_latest: { from: LifecycleStage; to: LifecycleStage; count: number }[];
  items: { zone_id: string; crime_type: string; stage: LifecycleStage; state: HotspotState }[];
  aggregation: string | null;
  data_label: string;
  versions: Versions;
}

export interface ZoneLifecycle {
  zone_id: string;
  crime_type: string;
  label: string;
  analysis: AnalysisSettings;
  current_stage: LifecycleStage | null;
  previous_stage: LifecycleStage | null;
  steps_in_stage: number;
  stage_description: string | null;
  timeline: (LifecycleStep & {
    state: HotspotState;
    stage: LifecycleStage;
    gi_z_last: number;
    final_period_hot: boolean;
  })[];
  data_label: string;
  versions: Versions;
}

export type MovementKind = "BASELINE" | "NEW" | "CONTINUED" | "SHIFTED" | "DISSIPATED";

export interface MovementItem {
  crime_type: string;
  label: string;
  step: number;
  period_end: string;
  cluster_id: string;
  zones: string[];
  n_zones: number;
  lat: number;
  lon: number;
  peak_z: number;
  merged: boolean;
  split: boolean;
  kind: MovementKind;
  from_cluster_ids: string[];
  from_lat?: number | null;
  from_lon?: number | null;
  distance_km?: number | null;
  bearing_deg?: number | null;
  direction?: string | null;
}

export interface MovementResponse {
  crime_type: string;
  step: number;
  steps: number[];
  period_end: string | null;
  analysis: AnalysisSettings & { movement_max_km: number };
  summary: Partial<Record<MovementKind, number>>;
  mean_shift_km: number | null;
  items: MovementItem[];
  note: string;
  data_label: string;
  versions: Versions;
}

// ---------------------------------------------------------------- pattern matching

export interface PatternAnalog {
  context_start: string;
  outcome_start: string;
  context_counts: number[];
  outcome_count: number;
  similarity: number;
}

export interface ZonePatterns {
  zone_id: string;
  crime_type: string;
  label: string;
  current_start: string;
  current_counts: number[];
  analogs: PatternAnalog[];
  n_analogs: number;
  analog_mean_outcome: number | null;
  analog_share_any: number | null;
  history_mean: number | null;
  history_share_any: number | null;
  mean_similarity: number | null;
  lookback_windows: number;
  window_days: number;
  method: string;
  note: string;
  data_label: string;
  versions: Versions;
}

// ---------------------------------------------------------------- stations

export interface StationOverviewItem {
  station_id: string;
  name: string;
  zones: number;
  high_risk_zones: number;
  peak_final_risk: number;
  surge_alerts: number;
  emerging_hotspots: number;
}

export interface StationsOverview {
  items: StationOverviewItem[];
  window: ForecastWindow;
  data_label: string;
  versions: Versions;
}

export interface StationDetail {
  station: {
    station_id: string;
    name: string;
    latitude: number;
    longitude: number;
    is_synthetic: boolean;
    zones: string[];
  };
  band: string;
  as_of: string;
  window: ForecastWindow;
  kpis: {
    zones: number;
    high_risk_zones: number;
    active_hotspots: number;
    emerging_hotspots: number;
    current_anomalies: number;
    incidents_4w: number;
  };
  kpi_definitions: Record<string, string>;
  top_attention: {
    zone_id: string;
    crime_type: string;
    label: string;
    band: string;
    final_risk: number;
    risk_band: RiskBand;
    probability: number;
    confidence: Confidence;
    crs: number;
    cai: number;
    hotspot_state: HotspotState;
  }[];
  zones: { zone_id: string; crime_type: string; label: string; band: string; final_risk: number; risk_band: RiskBand }[];
  crime_mix: { crime_type: string; label: string; incidents_52w: number; incidents_4w: number }[];
  lifecycle: Record<LifecycleStage, number>;
  alerts: { zone_id: string; crime_type: string; label: string; current_count: number; baseline_mean: number; z_score: number }[];
  boundary_note: string;
  data_label: string;
  limitation_statement: string;
  versions: Versions;
}
