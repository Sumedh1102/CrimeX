"use client";

import { useMemo, useState } from "react";
import { ChartCard } from "@/components/charts/ChartCard";
import { HBars } from "@/components/charts/charts";
import { FilterBar } from "@/components/map/Controls";
import { MapCard } from "@/components/map/MapCard";
import { StateIcon } from "@/components/ui/icons";
import { Card, DataTable, ErrorNote, Loading, Segmented, StateBadge, Swatch } from "@/components/ui/primitives";
import { useHotspots, useLifecycle, useMeta, useMovement, useStates } from "@/lib/api";
import { HOTSPOT_CLASS_COLORS, LIFECYCLE_ORDER, LIFECYCLE_STYLE, STATE_BADGE, STATE_ORDER, STATE_STYLE } from "@/lib/colors";
import { fmtDate, fmtInt, fmtNum } from "@/lib/format";
import { useUI } from "@/lib/store";
import type { HotspotItem, MovementItem, StateItem } from "@/lib/types";

export default function HotspotsPage() {
  const ui = useUI();
  const { data: meta } = useMeta();
  const [lifecycleTab, setLifecycleTab] = useState(false);
  const view = lifecycleTab ? "lifecycle" : ui.layer === "states" ? "states" : "hotspots";
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
    <div className="space-y-4 p-3 sm:p-5">
      <FilterBar showBand={view === "hotspots"} showPeriod={view === "hotspots"} />
      <Segmented
        ariaLabel="Hotspot view"
        value={view}
        onChange={(v) => {
          setLifecycleTab(v === "lifecycle");
          if (v === "lifecycle") ui.set({ layer: "states", showMovement: true });
          else ui.set({ layer: v });
        }}
        options={[
          { value: "hotspots", label: "Historical hotspots (Gi*)" },
          { value: "states", label: "Hotspot states (emerging, active …)" },
          { value: "lifecycle", label: "Lifecycle & movement" },
        ]}
      />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        <MapCard
          height={560}
          layer={view === "hotspots" ? "hotspots" : "states"}
          title={view === "hotspots" ? "Historical hotspot map" : view === "lifecycle" ? "Hotspot states and movement" : "Hotspot state map"}
        />
        {view === "lifecycle" ? (
          <LifecyclePanel />
        ) : view === "hotspots" ? (
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

function LifecyclePanel() {
  const ui = useUI();
  const lc = useLifecycle(ui.crimeType);
  const [step, setStep] = useState<number | null>(null);
  const mv = useMovement(ui.crimeType, step);
  const latest = lc.data?.steps[lc.data.steps.length - 1];
  const moves = useMemo(
    () => (mv.data?.items ?? []).filter((m) => m.kind !== "BASELINE").sort((a, b) => (b.distance_km ?? -1) - (a.distance_km ?? -1)),
    [mv.data],
  );
  return (
    <div className="space-y-3">
      <ChartCard
        title="Hotspot lifecycle"
        subtitle={
          lc.data && latest
            ? `Zone × crime-type pairs by stage, origin ${fmtDate(latest.period_end)} · ${lc.data.steps.length} origins, ${lc.data.analysis.period_weeks} weeks apart`
            : undefined
        }
        table={
          lc.data && {
            columns: [
              { key: "end", header: "Origin" },
              ...LIFECYCLE_ORDER.map((s) => ({ key: s, header: LIFECYCLE_STYLE[s].label, align: "right" as const })),
            ],
            rows: lc.data.steps.map((st) => ({
              end: fmtDate(st.period_end),
              ...Object.fromEntries(LIFECYCLE_ORDER.map((s) => [s, fmtInt(st[s])])),
            })),
          }
        }
      >
        {lc.error && <ErrorNote error={lc.error} />}
        {!lc.data || !latest ? (
          <Loading />
        ) : (
          <>
            <HBars
              rows={LIFECYCLE_ORDER.filter((s) => s !== "NORMAL").map((s) => ({
                key: s,
                label: (
                  <span className="inline-flex items-center gap-1.5">
                    <Swatch color={LIFECYCLE_STYLE[s].color} />
                    {LIFECYCLE_STYLE[s].label}
                  </span>
                ),
                value: latest[s],
                color: LIFECYCLE_STYLE[s].color,
              }))}
              format={(v) => v.toFixed(0)}
            />
            {lc.data.transitions_latest.length > 0 && (
              <>
                <p className="mb-1 mt-3 text-[11px] font-semibold text-ink-2">Changes since the previous origin</p>
                <ul className="space-y-0.5 text-[11px] text-ink-2">
                  {lc.data.transitions_latest.slice(0, 8).map((t) => (
                    <li key={t.from + t.to} className="flex justify-between">
                      <span>
                        {LIFECYCLE_STYLE[t.from].label} → {LIFECYCLE_STYLE[t.to].label}
                      </span>
                      <span className="tabular text-muted">{t.count}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </ChartCard>
      <Card
        title="Hotspot movement"
        subtitle={mv.data?.period_end ? `Clusters in the period ending ${fmtDate(mv.data.period_end)} vs the previous period` : undefined}
        actions={
          mv.data && mv.data.steps.length > 1 ? (
            <select
              aria-label="Analysis step"
              value={step ?? mv.data.step}
              onChange={(e) => setStep(Number(e.target.value))}
              className="h-7 rounded-md border bg-surface px-1.5 text-[11px] text-ink"
              style={{ borderColor: "var(--border)" }}
            >
              {mv.data.steps.slice(1).map((s) => (
                <option key={s} value={s}>
                  Step {s}
                  {s === mv.data!.steps[mv.data!.steps.length - 1] ? " (latest)" : ""}
                </option>
              ))}
            </select>
          ) : undefined
        }
      >
        {mv.error && <ErrorNote error={mv.error} />}
        {!mv.data ? (
          <Loading />
        ) : (
          <>
            <p className="mb-2 text-[11px] text-ink-2">
              {(["SHIFTED", "CONTINUED", "NEW", "DISSIPATED"] as const).map((k) => `${mv.data!.summary[k] ?? 0} ${k.toLowerCase()}`).join(" · ")}
              {mv.data.mean_shift_km != null && ` · mean shift ${fmtNum(mv.data.mean_shift_km, 1)} km`}
            </p>
            <DataTable<MovementItem>
              rows={moves}
              maxHeight={260}
              rowKey={(r) => r.cluster_id + r.kind}
              empty="No hotspot clusters in this period."
              onRowClick={(r) => ui.select({ zoneId: r.zones[0], crimeType: r.crime_type, band: "AUTO" })}
              columns={[
                { key: "c", header: "Crime type", render: (r) => r.label },
                { key: "k", header: "Change", render: (r) => r.kind.toLowerCase() + (r.merged ? " (merged)" : r.split ? " (split)" : "") },
                { key: "z", header: "Zones", render: (r) => `${r.n_zones} (${r.zones.slice(0, 2).join(", ")}${r.n_zones > 2 ? "…" : ""})` },
                { key: "d", header: "Shift", render: (r) => (r.distance_km != null ? `${fmtNum(r.distance_km, 1)} km ${r.direction ?? ""}` : "–"), align: "right" },
              ]}
            />
            <p className="mt-2 text-[11px] leading-snug text-muted">{mv.data.note}</p>
          </>
        )}
      </Card>
    </div>
  );
}
