"use client";

import { useMemo } from "react";
import { FilterBar } from "@/components/map/Controls";
import { MapCard } from "@/components/map/MapCard";
import { StateIcon } from "@/components/ui/icons";
import { Card, DataTable, ErrorNote, Loading, Segmented, StateBadge, Swatch } from "@/components/ui/primitives";
import { useHotspots, useMeta, useStates } from "@/lib/api";
import { HOTSPOT_CLASS_COLORS, STATE_BADGE, STATE_ORDER, STATE_STYLE } from "@/lib/colors";
import { fmtDate, fmtInt, fmtNum } from "@/lib/format";
import { useUI } from "@/lib/store";
import type { HotspotItem, StateItem } from "@/lib/types";

export default function HotspotsPage() {
  const ui = useUI();
  const { data: meta } = useMeta();
  const view = ui.layer === "states" ? "states" : "hotspots";
  const hot = useHotspots(ui.crimeType, ui.period, ui.band, ui.customStart, ui.customEnd);
  const states = useStates(ui.crimeType);
  const label = (c: string) => meta?.crime_types.find((t) => t.code === c)?.label ?? c;
  const summary = states.data?.summary;

  const significant = useMemo(
    () => (hot.data?.items ?? []).filter((i) => i.hotspot_class.startsWith("HOT")).sort((a, b) => b.gi_z - a.gi_z),
    [hot.data],
  );
  const notable = useMemo(
    () =>
      (states.data?.items ?? [])
        .filter((i) => i.state !== "STABLE")
        .sort((a, b) => STATE_ORDER.indexOf(a.state) - STATE_ORDER.indexOf(b.state) || b.hot_periods - a.hot_periods),
    [states.data],
  );

  return (
    <div className="space-y-4 p-5">
      <FilterBar showBand={view === "hotspots"} showPeriod={view === "hotspots"} />
      <Segmented
        ariaLabel="Hotspot view"
        value={view}
        onChange={(v) => ui.set({ layer: v })}
        options={[
          { value: "hotspots", label: "Historical hotspots (Gi*)" },
          { value: "states", label: "Hotspot states (emerging, active …)" },
        ]}
      />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        <MapCard height={560} layer={view} title={view === "hotspots" ? "Historical hotspot map" : "Hotspot state map"} />
        {view === "hotspots" ? (
          <Card
            title="Significant hotspots"
            subtitle={hot.data ? `${fmtDate(hot.data.start)} – ${fmtDate(hot.data.end)} · ${fmtInt(hot.data.summary.total_incidents)} incidents` : undefined}
          >
            {hot.error && <ErrorNote error={hot.error} />}
            {!hot.data ? (
              <Loading label={ui.period === "custom" ? "Choose a custom range" : "Loading"} />
            ) : (
              <>
                <DataTable<HotspotItem>
                  rows={significant}
                  maxHeight={470}
                  rowKey={(r) => r.zone_id}
                  empty="No statistically significant hotspots in this period."
                  onRowClick={(r) => ui.select({ zoneId: r.zone_id, crimeType: ui.crimeType === "ALL" ? "AUTO" : ui.crimeType, band: ui.band === "ALL" ? "AUTO" : ui.band })}
                  columns={[
                    { key: "z", header: "Zone", render: (r) => <span className="font-semibold text-ink">{r.zone_id}</span> },
                    {
                      key: "c",
                      header: "Class",
                      render: (r) => (
                        <span className="inline-flex items-center gap-1.5">
                          <Swatch color={HOTSPOT_CLASS_COLORS[r.hotspot_class]} />
                          {meta?.hotspot_classes.find((c) => c.code === r.hotspot_class)?.label.replace("Hot spot ", "Hot ").replace(" confidence", "")}
                        </span>
                      ),
                    },
                    { key: "n", header: "Incidents", render: (r) => fmtInt(r.count), align: "right" },
                    { key: "gi", header: "Gi* z", render: (r) => fmtNum(r.gi_z, 2), align: "right" },
                    { key: "d", header: "per km²", render: (r) => fmtNum(r.density_per_km2), align: "right" },
                  ]}
                />
                <p className="mt-3 text-[11px] leading-snug text-muted">{hot.data.method}.</p>
              </>
            )}
          </Card>
        ) : (
          <Card
            title="Hotspot states"
            subtitle={
              states.data
                ? `As of ${fmtDate(states.data.as_of)} · ${states.data.analysis.n_periods} periods of ${states.data.analysis.period_weeks} weeks`
                : undefined
            }
          >
            {states.error && <ErrorNote error={states.error} />}
            {!states.data ? (
              <Loading />
            ) : (
              <>
                <div className="mb-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-2">
                  {STATE_ORDER.map((s) => (
                    <span key={s} className="inline-flex items-center gap-1">
                      <StateIcon state={s} color={STATE_BADGE[s]} size={10} />
                      {STATE_STYLE[s].label} <span className="tabular text-muted">{summary?.[s] ?? 0}</span>
                    </span>
                  ))}
                </div>
                <DataTable<StateItem>
                  rows={notable}
                  maxHeight={440}
                  rowKey={(r) => r.zone_id + r.crime_type}
                  onRowClick={(r) => ui.select({ zoneId: r.zone_id, crimeType: r.crime_type, band: "AUTO" })}
                  columns={[
                    { key: "z", header: "Zone", render: (r) => <span className="font-semibold text-ink">{r.zone_id}</span> },
                    { key: "c", header: "Crime type", render: (r) => label(r.crime_type) },
                    { key: "s", header: "State", render: (r) => <StateBadge state={r.state} /> },
                    { key: "h", header: "Hot periods", render: (r) => `${r.hot_periods}/${r.n_periods}`, align: "right" },
                    { key: "t", header: "Trend", render: (r) => r.trend.toLowerCase() },
                  ]}
                />
              </>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
