// Pure presentation mapping from API items to map styling. No scores are computed
// here: every number shown comes from the API; this only picks colors, textures,
// icons and short labels for display.
import {
  AFFINITY_COLORS,
  ANOMALY_BINS,
  HOTSPOT_CLASS_COLORS,
  PROBABILITY_BINS,
  RISK_COLORS,
  STATE_STYLE,
} from "./colors";
import { fmtNum, fmtPct } from "./format";
import type {
  AffinityItem,
  HotspotItem,
  LayerKey,
  MovementItem,
  RiskItem,
  RiskMetric,
  StateItem,
  SurgeItem,
} from "./types";

export interface ZoneStyle {
  fill: string | null; // null = no fill
  texture: string | null; // registered pattern image id
  icon: string | null; // registered icon image id
  label: string | null; // short value label drawn on the map at high zoom
  legendKey: string; // which legend entry this zone belongs to
}

export const NO_STYLE: ZoneStyle = { fill: null, texture: null, icon: null, label: null, legendKey: "none" };

export function probabilityBin(p: number) {
  return PROBABILITY_BINS.find((b) => p < b.max) ?? PROBABILITY_BINS[PROBABILITY_BINS.length - 1];
}

export function riskStyle(item: RiskItem, metric: RiskMetric, textures: boolean): ZoneStyle {
  if (metric === "probability") {
    const bin = probabilityBin(item.probability);
    return { fill: bin.color, texture: null, icon: null, label: fmtPct(item.probability), legendKey: bin.label };
  }
  const band = metric === "crs" ? item.crs_band : item.risk_band;
  const value = metric === "crs" ? item.crs : item.final_risk;
  let texture: string | null = null;
  if (textures && band === "HIGH") texture = "tex-risk-high";
  if (textures && band === "VERY HIGH") texture = "tex-risk-veryhigh";
  // Attention markers: a non-colour cue that also gives the top bands a tap target.
  const icon = band === "VERY HIGH" ? "risk-veryhigh" : band === "HIGH" ? "risk-high" : null;
  return { fill: RISK_COLORS[band], texture, icon, label: fmtNum(value, 0), legendKey: band };
}

export function hotspotStyle(item: HotspotItem): ZoneStyle {
  const fill = HOTSPOT_CLASS_COLORS[item.hotspot_class];
  return {
    fill,
    texture: null,
    icon: null,
    label: item.count > 0 ? String(item.count) : null,
    legendKey: item.hotspot_class,
  };
}

export function stateStyle(item: StateItem, textures: boolean): ZoneStyle {
  const s = STATE_STYLE[item.state];
  return {
    fill: s.color,
    texture: textures && s.texture ? "tex-persistent" : null,
    icon: s.icon,
    label: null,
    legendKey: item.state,
  };
}

export function affinityStyle(item: AffinityItem): ZoneStyle {
  return {
    fill: AFFINITY_COLORS[item.affinity_band],
    texture: null,
    icon: null,
    label: fmtNum(item.cai, 0),
    legendKey: item.affinity_band,
  };
}

export function anomalyBin(z: number) {
  let bin: (typeof ANOMALY_BINS)[number] | null = null;
  for (const b of ANOMALY_BINS) if (z >= b.min) bin = b;
  return bin;
}

export function anomalyStyle(item: SurgeItem): ZoneStyle {
  const bin = anomalyBin(item.surge_z);
  if (!bin && !item.surge_alert) return { ...NO_STYLE, legendKey: "none" };
  return {
    fill: bin?.color ?? null,
    texture: null,
    icon: item.surge_alert ? "alert" : null,
    label: bin ? `z${fmtNum(item.surge_z, 1)}` : null,
    legendKey: item.surge_alert ? "alert" : bin!.label,
  };
}

export type LayerItem = RiskItem | HotspotItem | StateItem | AffinityItem | SurgeItem;

export function styleFor(
  layer: LayerKey,
  item: LayerItem | undefined,
  opts: { metric: RiskMetric; textures: boolean },
): ZoneStyle {
  if (!item) return NO_STYLE;
  switch (layer) {
    case "risk":
      return riskStyle(item as RiskItem, opts.metric, opts.textures);
    case "hotspots":
      return hotspotStyle(item as HotspotItem);
    case "states":
      return stateStyle(item as StateItem, opts.textures);
    case "affinity":
      return affinityStyle(item as AffinityItem);
    case "anomalies":
      return anomalyStyle(item as SurgeItem);
  }
}

/** Zones whose station differs from a neighbour's: returns boundary line segments. */
export function stationBoundaries(
  zones: { row: number; col: number; station_id: string | null; ring: number[][] }[],
): number[][][] {
  const key = (r: number, c: number) => `${r}:${c}`;
  const byCell = new Map(zones.map((z) => [key(z.row, z.col), z]));
  const segs: number[][][] = [];
  for (const z of zones) {
    // ring = [[w,s],[e,s],[e,n],[w,n],[w,s]]; rows grow southwards
    const [sw, se, ne, nw] = z.ring;
    const east = byCell.get(key(z.row, z.col + 1));
    const south = byCell.get(key(z.row + 1, z.col));
    const west = byCell.get(key(z.row, z.col - 1));
    const north = byCell.get(key(z.row - 1, z.col));
    if (!east || east.station_id !== z.station_id) segs.push([se, ne]);
    if (!south || south.station_id !== z.station_id) segs.push([sw, se]);
    if (!west) segs.push([nw, sw]);
    if (!north) segs.push([ne, nw]);
  }
  return segs;
}

/**
 * Map features for hotspot movement: a line from the earlier cluster centroid to the
 * current one (SHIFTED / CONTINUED) and a marker at the current (or, for DISSIPATED, the
 * last) centroid. Marker shape carries the kind; the arrow is rotated to the bearing.
 */
export function movementFeatures(items: MovementItem[]): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  for (const m of items) {
    if (m.kind === "BASELINE") continue;
    const moved = m.kind === "SHIFTED" && m.from_lat != null && m.from_lon != null;
    if (moved) {
      features.push({
        type: "Feature",
        properties: { cluster_id: m.cluster_id, kind: m.kind, role: "path" },
        geometry: { type: "LineString", coordinates: [[m.from_lon!, m.from_lat!], [m.lon, m.lat]] },
      });
    }
    const icon = moved ? "move-arrow" : m.kind === "NEW" ? "move-new" : m.kind === "DISSIPATED" ? "move-gone" : "move-hold";
    const label = moved
      ? `${fmtNum(m.distance_km ?? 0, 1)} km ${m.direction ?? ""}`.trim()
      : m.kind === "NEW"
        ? "new"
        : m.kind === "DISSIPATED"
          ? "dissipated"
          : "";
    features.push({
      type: "Feature",
      properties: {
        cluster_id: m.cluster_id,
        kind: m.kind,
        role: "marker",
        icon,
        rotation: moved ? (m.bearing_deg ?? 0) : 0,
        label: label ? `lbl:${label}` : "",
      },
      geometry: { type: "Point", coordinates: [m.lon, m.lat] },
    });
  }
  return { type: "FeatureCollection", features };
}
