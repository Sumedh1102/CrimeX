import { describe, expect, it } from "vitest";
import { AFFINITY_COLORS, RISK_COLORS, STATE_STYLE } from "./colors";
import { fmtNextWindow, fmtPct, fmtWindow, windowUnit } from "./format";
import {
  anomalyStyle,
  movementFeatures,
  probabilityBin,
  riskStyle,
  stateStyle,
  stationBoundaries,
  styleFor,
} from "./layers";
import type { RiskItem, StateItem, SurgeItem } from "./types";

const risk: RiskItem = {
  zone_id: "Z001",
  crime_type: "THEFT",
  band: "EVENING",
  final_risk: 84.2,
  risk_band: "VERY HIGH",
  crs: 55,
  crs_band: "ELEVATED",
  probability: 0.41,
  confidence: "HIGH",
  expected_count: 0.9,
  hotspot_state: "EMERGING",
  cai: 61,
  affinity_band: "High",
};

describe("risk layer styling", () => {
  it("uses the band returned by the API, never a recomputed one", () => {
    const s = riskStyle(risk, "final_risk", true);
    expect(s.fill).toBe(RISK_COLORS["VERY HIGH"]);
    expect(s.legendKey).toBe("VERY HIGH");
    expect(s.label).toBe("84");
    expect(s.texture).toBe("tex-risk-veryhigh");
    expect(s.icon).toBe("risk-veryhigh");
    const crs = riskStyle(risk, "crs", true);
    expect(crs.fill).toBe(RISK_COLORS.ELEVATED);
    expect(crs.texture).toBeNull();
    expect(crs.icon).toBeNull();
    expect(riskStyle({ ...risk, risk_band: "HIGH" }, "final_risk", false).icon).toBe("risk-high");
  });

  it("textures can be switched off", () => {
    expect(riskStyle(risk, "final_risk", false).texture).toBeNull();
  });

  it("probability uses its own percentage bins, not risk bands", () => {
    const s = riskStyle(risk, "probability", true);
    expect(s.legendKey).toBe("≥ 20%");
    expect(s.label).toBe("41%");
    expect(probabilityBin(0.015).label).toBe("< 2%");
    expect(probabilityBin(0.05).label).toBe("5–10%");
  });
});

describe("state and anomaly styling", () => {
  it("persistent hotspots share the active hue but carry texture and a distinct icon", () => {
    const base = { zone_id: "Z1", crime_type: "THEFT", hot_periods: 20, n_periods: 26,
      recent_hot_periods: 3, final_period_hot: true, current_hot_run_periods: 5, trend: "",
      trend_tau: 0, trend_p: 1, gi_z_last: 3, recent_rate: 1, prior_rate: 1 };
    const active = stateStyle({ ...base, state: "ACTIVE" } as StateItem, true);
    const persistent = stateStyle({ ...base, state: "PERSISTENT" } as StateItem, true);
    expect(active.fill).toBe(persistent.fill);
    expect(active.icon).not.toBe(persistent.icon);
    expect(persistent.texture).toBe("tex-persistent");
    expect(stateStyle({ ...base, state: "STABLE" } as StateItem, true).fill).toBeNull();
    expect(STATE_STYLE.EMERGING.icon).toBe("state-emerging");
  });

  it("anomaly alerts get the alert icon; quiet zones get no fill", () => {
    const quiet = { zone_id: "Z1", crime_type: "THEFT", surge_current_count: 0,
      surge_baseline_mean: 0.2, surge_baseline_std: 0.4, surge_z: -0.5,
      surge_deviation_pct: -100, surge_alert: false, X: 0 } as SurgeItem;
    expect(anomalyStyle(quiet).fill).toBeNull();
    const alert = { ...quiet, surge_current_count: 7, surge_z: 6.1, surge_alert: true };
    const s = anomalyStyle(alert);
    expect(s.icon).toBe("alert");
    expect(s.legendKey).toBe("alert");
  });

  it("returns no style for zones without data", () => {
    expect(styleFor("affinity", undefined, { metric: "final_risk", textures: true }).fill).toBeNull();
    expect(AFFINITY_COLORS["Very High"]).toBeDefined();
  });
});

describe("station boundaries", () => {
  it("draws edges between different stations and around the outside", () => {
    const cell = (row: number, col: number, station: string) => {
      const w = col, e = col + 1, n = -row, s = -row - 1;
      return { row, col, station_id: station, ring: [[w, s], [e, s], [e, n], [w, n], [w, s]] };
    };
    const segs = stationBoundaries([cell(0, 0, "A"), cell(0, 1, "B")]);
    // 1 shared internal edge + 6 outer edges
    expect(segs).toHaveLength(7);
  });
});

describe("formatting", () => {
  it("formats probabilities and inclusive window ends", () => {
    expect(fmtPct(0.0004)).toBe("< 0.1%");
    expect(fmtPct(0.0567)).toBe("5.7%");
    expect(fmtPct(0.41)).toBe("41%");
    expect(fmtWindow("2026-09-01T00:00:00", "2026-09-08T00:00:00")).toBe("1–7 Sep 2026");
  });
});

describe("movementFeatures", () => {
  const base = {
    crime_type: "ROBBERY",
    label: "Robbery",
    step: 7,
    period_end: "2026-09-01",
    zones: ["Z001"],
    n_zones: 1,
    lat: 19.1,
    lon: 72.85,
    peak_z: 3,
    merged: false,
    split: false,
    from_cluster_ids: [],
  };

  it("draws a path and a rotated arrow for a shifted cluster", () => {
    const fc = movementFeatures([
      { ...base, cluster_id: "A", kind: "SHIFTED", from_lat: 19.09, from_lon: 72.85, distance_km: 1.43, bearing_deg: 10, direction: "N" },
    ]);
    const path = fc.features.find((f) => f.properties?.role === "path")!;
    const marker = fc.features.find((f) => f.properties?.role === "marker")!;
    expect(path.geometry).toEqual({ type: "LineString", coordinates: [[72.85, 19.09], [72.85, 19.1]] });
    expect(marker.properties).toMatchObject({ icon: "move-arrow", rotation: 10, label: "lbl:1.4 km N" });
  });

  it("uses shapes, not only color, for other kinds and skips the baseline", () => {
    const fc = movementFeatures([
      { ...base, cluster_id: "B", kind: "BASELINE" },
      { ...base, cluster_id: "N", kind: "NEW" },
      { ...base, cluster_id: "D", kind: "DISSIPATED" },
      { ...base, cluster_id: "C", kind: "CONTINUED", from_lat: 19.1, from_lon: 72.85, distance_km: 0.2 },
    ]);
    expect(fc.features.map((f) => f.properties?.icon)).toEqual(["move-new", "move-gone", "move-hold"]);
    expect(fc.features.every((f) => f.properties?.role === "marker")).toBe(true);
  });
});

describe("window wording", () => {
  it("follows the configured window length", () => {
    expect(fmtNextWindow(7)).toBe("next 7 days");
    expect(fmtNextWindow(1)).toBe("next 24 hours");
    expect(windowUnit(1)).toBe("day");
    expect(windowUnit(7)).toBe("week");
    expect(windowUnit(3)).toBe("3-day window");
  });
});
