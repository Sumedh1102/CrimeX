// Color roles. Every ramp below was validated with the dataviz validator
// (scripts/validate_palette.js) against the dark chart surface #1a1a19:
//   risk (ordinal, rust->peach)   PASS monotone L, adjacent dL ~0.105, hue spread 33 deg, low end
//                                 2.35:1 vs the map background at RISK_FILL_OPACITY; adjacent
//                                 OKLab dE 10.7-13.3 normal vision, >= 8.9 under protan/deutan/tritan
//                                 (the previous orange ramp at 0.74 opacity was dE 5.9-7.4)
//   affinity (ordinal, blue)      PASS (documented blue steps 600..200), low end 2.15:1
//   anomaly (ordinal, blue, 3)    PASS, low end 2.63:1
//   Gi* hot arm (ordinal, red, 3) PASS, low end 2.71:1; cold arm = documented blue steps
//   hotspot states violet + red   PASS all-pairs (CVD dE 19.5, normal-vision dE 22.5)
// Colors never carry meaning alone: every layer also has labels, icons and/or texture.
import type { AffinityBand, HotspotClass, HotspotState, RiskBand } from "./types";

export const CHROME = {
  plane: "#0d0d0d",
  surface: "#1a1a19",
  surface2: "#222220",
  ink: "#ffffff",
  ink2: "#c3c2b7",
  muted: "#898781",
  grid: "#2c2c2a",
  baseline: "#383835",
} as const;

export const SERIES = {
  primary: "#3987e5", // categorical slot 1 (dark)
  primaryWash: "rgba(57,135,229,0.10)",
  deemphasis: "#5f5e59",
  up: "#e66767", // diverging warm arm (raises / increase)
  down: "#3987e5", // diverging cool arm (lowers / decrease)
  neutral: "#383835", // diverging midpoint
} as const;

// OKLCH L 0.475 -> 0.90 in equal steps, hue 34 -> 66 deg (rust -> peach). In dark mode the
// ramp's anchor flips: low risk recedes into the dark map, the highest band is the brightest.
export const RISK_COLORS: Record<RiskBand, string> = {
  LOW: "#973a25",
  MODERATE: "#ce4700",
  ELEVATED: "#f16d02",
  HIGH: "#fea158",
  "VERY HIGH": "#ffd6ad",
};
// Fills are near-opaque so the bands stay apart; basemap labels are drawn above them.
export const RISK_FILL_OPACITY = 0.9;
export const RISK_ORDER: RiskBand[] = ["LOW", "MODERATE", "ELEVATED", "HIGH", "VERY HIGH"];

// Presentation bins for the calibrated probability (not risk bands).
export const PROBABILITY_BINS: { max: number; label: string; color: string }[] = [
  { max: 0.02, label: "< 2%", color: RISK_COLORS.LOW },
  { max: 0.05, label: "2–5%", color: RISK_COLORS.MODERATE },
  { max: 0.1, label: "5–10%", color: RISK_COLORS.ELEVATED },
  { max: 0.2, label: "10–20%", color: RISK_COLORS.HIGH },
  { max: 1.0000001, label: "≥ 20%", color: RISK_COLORS["VERY HIGH"] },
];

export const AFFINITY_COLORS: Record<AffinityBand, string> = {
  "Very Low": "#184f95",
  Low: "#256abf",
  Moderate: "#3987e5",
  High: "#6da7ec",
  "Very High": "#9ec5f4",
};
export const AFFINITY_ORDER: AffinityBand[] = ["Very Low", "Low", "Moderate", "High", "Very High"];

export const ANOMALY_BINS: { min: number; label: string; color: string }[] = [
  { min: 1, label: "z 1–2", color: "#1c5cab" },
  { min: 2, label: "z 2–3", color: "#3987e5" },
  { min: 3, label: "z ≥ 3", color: "#86b6ef" },
];

export const HOTSPOT_CLASS_COLORS: Record<HotspotClass, string | null> = {
  HOT_99: "#f66d67",
  HOT_95: "#ce514d",
  HOT_90: "#a03f3c",
  NOT_SIGNIFICANT: null,
  COLD_90: "#184f95",
  COLD_95: "#256abf",
  COLD_99: "#3987e5",
};
export const HOTSPOT_CLASS_ORDER: HotspotClass[] = [
  "HOT_99",
  "HOT_95",
  "HOT_90",
  "NOT_SIGNIFICANT",
  "COLD_90",
  "COLD_95",
  "COLD_99",
];

export const STATE_STYLE: Record<
  HotspotState,
  { color: string | null; icon: string | null; texture: boolean; label: string }
> = {
  EMERGING: { color: "#9085e9", icon: "state-emerging", texture: false, label: "Emerging" },
  ACTIVE: { color: "#e66767", icon: "state-active", texture: false, label: "Active" },
  PERSISTENT: { color: "#e66767", icon: "state-persistent", texture: true, label: "Persistent" },
  DECLINING: { color: "#5f5e59", icon: "state-declining", texture: false, label: "Declining" },
  SPORADIC: { color: "#3f3e3a", icon: "state-sporadic", texture: false, label: "Sporadic" },
  STABLE: { color: null, icon: null, texture: false, label: "Stable" },
};
export const STATE_ORDER: HotspotState[] = [
  "EMERGING",
  "ACTIVE",
  "PERSISTENT",
  "DECLINING",
  "SPORADIC",
  "STABLE",
];

// Badge colors for states in tables / panels (text stays in ink tokens).
export const STATE_BADGE: Record<HotspotState, string> = {
  EMERGING: "#9085e9",
  ACTIVE: "#e66767",
  PERSISTENT: "#e66767",
  DECLINING: "#898781",
  SPORADIC: "#898781",
  STABLE: "#0ca30c",
};

export const WARN = "#fab219";

// Texture strokes: tone-on-tone (a darker step of the fill's own ramp), 45 / 135 degrees.
export const TEXTURE_INK = {
  riskHigh: RISK_COLORS.MODERATE,
  riskVeryHigh: RISK_COLORS.ELEVATED,
  persistent: "#a03f3c",
} as const;
