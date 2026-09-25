"use client";

import clsx from "clsx";
import { Segmented, Select } from "@/components/ui/primitives";
import { useMeta, useStations } from "@/lib/api";
import { useUI } from "@/lib/store";
import type { LayerKey, RiskMetric } from "@/lib/types";

export const LAYER_OPTIONS: { value: LayerKey; label: string; title: string }[] = [
  { value: "risk", label: "Predicted risk", title: "Forecast window risk (blended, CRS or probability)" },
  { value: "hotspots", label: "Historical hotspots", title: "Getis-Ord Gi* for the selected period" },
  { value: "states", label: "Hotspot states", title: "Emerging / active / persistent / declining" },
  { value: "affinity", label: "Crime affinity", title: "Crime Affinity Index (CAI)" },
  { value: "anomalies", label: "Anomalies", title: "Crime Surge Detector" },
];

const PERIODS = [
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "6m", label: "Last 6 months" },
  { value: "1y", label: "Last year" },
  { value: "custom", label: "Custom range" },
];

/** One filter row above everything it scopes. */
export function FilterBar({ showPeriod = true, showBand = true }: { showPeriod?: boolean; showBand?: boolean }) {
  const ui = useUI();
  const { data: meta } = useMeta();
  const { data: stations } = useStations();
  if (!meta) return null;
  return (
    <div className="grid grid-cols-2 items-end gap-2 sm:flex sm:flex-wrap sm:gap-3">
      <Select
        className="min-w-0"
        label="Station"
        value={ui.stationId ?? "ALL"}
        onChange={(v) => ui.set({ stationId: v === "ALL" ? null : v })}
        options={[
          { value: "ALL", label: "All stations (city)" },
          ...(stations?.items ?? []).map((s) => ({ value: s.station_id, label: `${s.name} (${s.zones} zones)` })),
        ]}
      />
      <Select
        className="min-w-0"
        label="Crime type"
        value={ui.crimeType}
        onChange={(v) => ui.set({ crimeType: v })}
        options={[
          { value: "ALL", label: "All modelled crime types" },
          ...meta.crime_types.map((c) => ({ value: c.code, label: c.label })),
        ]}
      />
      {showBand && (
        <Select
          className="min-w-0"
          label="Time band (next 7 days)"
          value={ui.band}
          onChange={(v) => ui.set({ band: v })}
          options={[{ value: "ALL", label: "All bands" }, ...meta.bands.map((b) => ({ value: b.code, label: b.label }))]}
        />
      )}
      {showPeriod && (
        <Select
          className="min-w-0"
          label="History period"
          value={ui.period}
          onChange={(v) => ui.set({ period: v })}
          options={PERIODS}
        />
      )}
      {showPeriod && ui.period === "custom" && (
        <div className="col-span-2 flex items-end gap-2">
          {(["customStart", "customEnd"] as const).map((k) => (
            <label key={k} className="flex flex-col gap-1">
              <span className="text-[11px] font-medium uppercase tracking-wide text-muted">
                {k === "customStart" ? "From" : "To"}
              </span>
              <input
                type="date"
                min={meta.data_range.start.slice(0, 10)}
                max={meta.as_of}
                value={ui[k] ?? ""}
                onChange={(e) => ui.set({ [k]: e.target.value || null })}
                className="h-8 rounded-md border bg-surface px-2 text-[13px] text-ink"
                style={{ borderColor: "var(--border)", colorScheme: "dark" }}
              />
            </label>
          ))}
        </div>
      )}
      <p className="col-span-2 text-[11px] leading-snug text-muted sm:ml-auto sm:max-w-[340px] sm:text-right">
        {ui.crimeType === "ALL" || ui.band === "ALL"
          ? "With “All”, each zone shows its highest crime-type/band-specific value (never a sum)."
          : "Risk(zone, crime type, time window) for the next 7 days."}
      </p>
    </div>
  );
}

export function LayerControls({ compact = false }: { compact?: boolean }) {
  const ui = useUI();
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented
        ariaLabel="Map layer"
        value={ui.layer}
        onChange={(v) => ui.set({ layer: v })}
        options={LAYER_OPTIONS}
        size={compact ? "sm" : "md"}
      />
      {ui.layer === "risk" && (
        <Segmented<RiskMetric>
          ariaLabel="Risk metric"
          value={ui.riskMetric}
          onChange={(v) => ui.set({ riskMetric: v })}
          options={[
            { value: "final_risk", label: "Blended", title: "100 × (0.6 × probability + 0.4 × CRS/100)" },
            { value: "crs", label: "CRS", title: "Explainable Crime Risk Score" },
            { value: "probability", label: "Probability", title: "Calibrated probability" },
          ]}
          size="sm"
        />
      )}
      <Toggle label="Stations" on={ui.showStations} onClick={() => ui.set({ showStations: !ui.showStations })} />
      <Toggle label="Textures" on={ui.textures} onClick={() => ui.set({ textures: !ui.textures })} />
    </div>
  );
}

function Toggle({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onClick}
      className={clsx(
        "flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px]",
        on ? "text-ink" : "text-muted",
      )}
      style={{ borderColor: "var(--border)" }}
    >
      <span
        aria-hidden
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: on ? "#3987e5" : "#383835" }}
      />
      {label}
    </button>
  );
}
