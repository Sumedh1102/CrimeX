"use client";

import type { ReactNode } from "react";
import { STATE_STYLE } from "@/lib/colors";
import { fmtInt, fmtNum, fmtPct } from "@/lib/format";
import type { LayerItem } from "@/lib/layers";
import type {
  AffinityItem,
  HotspotItem,
  LayerKey,
  Meta,
  RiskItem,
  RiskMetric,
  StateItem,
  SurgeItem,
  ZoneProps,
} from "@/lib/types";

function Row({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="text-ink-2">{label}</span>
      <span className="tabular font-semibold text-ink">{value}</span>
    </div>
  );
}

export function MapTooltip({
  x,
  y,
  zone,
  layer,
  item,
  meta,
  metric,
  band,
  bounds,
}: {
  bounds?: { w: number; h: number };
  x: number;
  y: number;
  zone: ZoneProps;
  layer: LayerKey;
  item: LayerItem | undefined;
  meta: Meta;
  metric: RiskMetric;
  band: string;
}) {
  const crimeLabel = (c: string) => meta.crime_types.find((t) => t.code === c)?.label ?? c;
  const bandLabel = (b: string) => meta.bands.find((t) => t.code === b)?.label ?? b;
  let body: ReactNode = <p className="text-muted">No data for this zone.</p>;

  if (item && layer === "risk") {
    const r = item as RiskItem;
    body = (
      <>
        <p className="text-muted">
          {crimeLabel(r.crime_type)} · {bandLabel(r.band)}
          {band === "ALL" || r.crime_type ? "" : ""}
        </p>
        <Row label="Blended risk score" value={`${fmtNum(r.final_risk)} · ${r.risk_band}`} />
        <Row label="Explainable score (CRS)" value={`${fmtNum(r.crs)} · ${r.crs_band}`} />
        <Row label="Calibrated probability" value={fmtPct(r.probability)} />
        <Row label="Hotspot state" value={STATE_STYLE[r.hotspot_state].label} />
        <p className="pt-1 text-[10px] text-muted">
          {metric === "probability"
            ? "Probability of ≥1 reported incident in this band during the forecast window."
            : "Scores are 0–100 indicators, not probabilities."}
        </p>
      </>
    );
  } else if (item && layer === "hotspots") {
    const h = item as HotspotItem;
    body = (
      <>
        <Row label="Incidents in period" value={fmtInt(h.count)} />
        <Row label="Gi* z-score" value={fmtNum(h.gi_z, 2)} />
        <Row label="Classification" value={meta.hotspot_classes.find((c) => c.code === h.hotspot_class)?.label ?? h.hotspot_class} />
        <Row label="Density" value={`${fmtNum(h.density_per_km2)} /km²`} />
      </>
    );
  } else if (item && layer === "states") {
    const s = item as StateItem;
    body = (
      <>
        <p className="text-muted">{crimeLabel(s.crime_type)}</p>
        <Row label="Hotspot state" value={STATE_STYLE[s.state].label} />
        <Row label="Hot periods" value={`${s.hot_periods} of ${s.n_periods}`} />
        <Row label="Recent periods hot" value={`${s.recent_hot_periods} of 3`} />
        <Row label="Trend" value={s.trend.toLowerCase()} />
      </>
    );
  } else if (item && layer === "affinity") {
    const a = item as AffinityItem;
    body = (
      <>
        <p className="text-muted">{crimeLabel(a.crime_type)}</p>
        <Row label="Crime Affinity Index" value={`${fmtNum(a.cai)} · ${a.affinity_band}`} />
        <Row label="Location quotient" value={fmtNum(a.location_quotient, 2)} />
        <Row label="Incidents, last 52 weeks" value={fmtInt(a.incidents_52w)} />
      </>
    );
  } else if (item && layer === "anomalies") {
    const a = item as SurgeItem;
    body = (
      <>
        <p className="text-muted">{crimeLabel(a.crime_type)} (largest surge in zone)</p>
        <Row label="Last week" value={fmtInt(a.surge_current_count)} />
        <Row label="Typical week (52w mean)" value={fmtNum(a.surge_baseline_mean, 2)} />
        <Row label="Surge z-score" value={fmtNum(a.surge_z, 1)} />
        {a.surge_alert && <p className="pt-1 font-semibold text-ink">Surge alert</p>}
      </>
    );
  }

  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-20 w-[250px] rounded-md border bg-surface px-3 py-2 text-[11px] shadow-2xl"
      style={{
        // Flip to the other side of the cursor near the right / bottom edge of the map.
        left: bounds && x + 14 + 250 > bounds.w ? Math.max(4, x - 14 - 250) : x + 14,
        top: bounds && y + 14 + 170 > bounds.h ? Math.max(4, y - 14 - 170) : y + 14,
        borderColor: "var(--border-strong)",
      }}
    >
      <p className="mb-1 text-xs font-semibold text-ink">
        Zone {zone.zone_id}
        {zone.station_name && <span className="font-normal text-muted"> · {zone.station_name}</span>}
      </p>
      <div className="space-y-0.5">{body}</div>
    </div>
  );
}
