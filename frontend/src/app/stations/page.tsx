"use client";

import { ChartCard } from "@/components/charts/ChartCard";
import { HBars } from "@/components/charts/charts";
import { MapCard } from "@/components/map/MapCard";
import { AlertIcon, Icon } from "@/components/ui/icons";
import {
  Card,
  ConfidencePill,
  DataTable,
  ErrorNote,
  Kpi,
  Loading,
  RiskBadge,
  Select,
  StateBadge,
  SyntheticBadge,
} from "@/components/ui/primitives";
import { stationReportUrl, useMeta, useStationDetail, useStationsOverview } from "@/lib/api";
import { LIFECYCLE_ORDER, LIFECYCLE_STYLE, RISK_COLORS } from "@/lib/colors";
import { fmtInt, fmtNextWindow, fmtNum, fmtPct, fmtWindow } from "@/lib/format";
import { useUI } from "@/lib/store";
import type { StationDetail, StationOverviewItem } from "@/lib/types";

type Attention = StationDetail["top_attention"][number];

export default function StationsPage() {
  const ui = useUI();
  const { data: meta } = useMeta();
  const overview = useStationsOverview();
  const stationId = ui.stationId ?? overview.data?.items[0]?.station_id ?? null;
  const { data: d, error } = useStationDetail(stationId, ui.band);

  return (
    <div className="space-y-4 p-3 sm:p-5">
      <div className="grid grid-cols-2 items-end gap-2 sm:flex sm:flex-wrap sm:gap-3">
        <Select
          className="min-w-0"
          label="Station"
          value={stationId ?? ""}
          onChange={(v) => ui.set({ stationId: v })}
          options={(overview.data?.items ?? []).map((s) => ({
            value: s.station_id,
            label: `${s.name} · ${s.high_risk_zones} high-risk zone${s.high_risk_zones === 1 ? "" : "s"}`,
          }))}
        />
        {meta && (
          <Select
            className="min-w-0"
            label={`Time band (${fmtNextWindow(meta.forecast_window.days)})`}
            value={ui.band}
            onChange={(v) => ui.set({ band: v })}
            options={[{ value: "ALL", label: "All bands" }, ...meta.bands.map((b) => ({ value: b.code, label: b.label }))]}
          />
        )}
        {stationId && (
          <a
            href={stationReportUrl(stationId)}
            target="_blank"
            rel="noopener noreferrer"
            className="col-span-2 inline-flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-[12px] text-ink-2 hover:bg-surface-2 hover:text-ink sm:ml-auto"
            style={{ borderColor: "var(--border)" }}
          >
            <Icon name="official" size={14} />
            Printable station brief
          </a>
        )}
      </div>
      {(error || overview.error) && <ErrorNote error={(error ?? overview.error)!} />}
      {!d ? (
        <Loading label="Loading station" />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
            <SyntheticBadge label={d.data_label} />
            <span>
              {d.station.name} · {d.station.zones.length} zones · forecast window {fmtWindow(d.window.start, d.window.end)}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
            <Kpi label="Zones" value={d.kpis.zones} />
            <Kpi label="High-risk zones" value={d.kpis.high_risk_zones} hint={d.kpi_definitions.high_risk_zones} />
            <Kpi label="Active hotspots" value={d.kpis.active_hotspots} hint={d.kpi_definitions.active_hotspots} />
            <Kpi label="Emerging hotspots" value={d.kpis.emerging_hotspots} hint={d.kpi_definitions.emerging_hotspots} />
            <Kpi label="Surge alerts" value={d.kpis.current_anomalies} icon={<AlertIcon size={12} />} hint={d.kpi_definitions.current_anomalies} />
            <Kpi label="Incidents, last 4 weeks" value={fmtInt(d.kpis.incidents_4w)} />
          </div>
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_460px]">
            <MapCard height={520} title="Station area (other zones dimmed)" />
            <Card title="Attention priorities" subtitle="Highest blended risk in the station area (zone × crime type × band)">
              <DataTable<Attention>
                rows={d.top_attention}
                maxHeight={460}
                rowKey={(r) => r.zone_id + r.crime_type + r.band}
                onRowClick={(r) => ui.select({ zoneId: r.zone_id, crimeType: r.crime_type, band: r.band })}
                columns={[
                  { key: "z", header: "Zone", render: (r) => <span className="font-semibold text-ink">{r.zone_id}</span> },
                  { key: "c", header: "Crime type", render: (r) => r.label },
                  { key: "b", header: "Band", render: (r) => r.band.toLowerCase() },
                  { key: "r", header: "Risk", render: (r) => <RiskBadge band={r.risk_band} value={r.final_risk} /> },
                  {
                    key: "p",
                    header: "Probability",
                    render: (r) => (
                      <span className="inline-flex items-center gap-1.5">
                        {fmtPct(r.probability)} <ConfidencePill level={r.confidence} />
                      </span>
                    ),
                    align: "right",
                  },
                  { key: "s", header: "State", render: (r) => <StateBadge state={r.hotspot_state} /> },
                ]}
              />
            </Card>
          </div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            <ChartCard
              title="Crime mix"
              subtitle="Incidents in the station area, last 52 weeks"
              table={{
                columns: [
                  { key: "t", header: "Crime type" },
                  { key: "y", header: "52 weeks", align: "right" },
                  { key: "m", header: "4 weeks", align: "right" },
                ],
                rows: d.crime_mix.map((c) => ({ t: c.label, y: fmtInt(c.incidents_52w), m: fmtInt(c.incidents_4w) })),
              }}
            >
              <HBars rows={d.crime_mix.map((c) => ({ key: c.crime_type, label: c.label, value: c.incidents_52w }))} />
            </ChartCard>
            <ChartCard
              title="Hotspot lifecycle"
              subtitle="Zone × crime-type pairs by current stage"
              table={{
                columns: [
                  { key: "s", header: "Stage" },
                  { key: "n", header: "Pairs", align: "right" },
                ],
                rows: LIFECYCLE_ORDER.map((s) => ({ s: LIFECYCLE_STYLE[s].label, n: fmtInt(d.lifecycle[s] ?? 0) })),
              }}
            >
              <HBars
                rows={LIFECYCLE_ORDER.filter((s) => s !== "NORMAL").map((s) => ({
                  key: s,
                  label: LIFECYCLE_STYLE[s].label,
                  value: d.lifecycle[s] ?? 0,
                  color: LIFECYCLE_STYLE[s].color,
                }))}
                format={(v) => v.toFixed(0)}
              />
            </ChartCard>
            <Card title="Surge alerts" subtitle="Crime Surge Detector, latest window">
              {d.alerts.length === 0 ? (
                <p className="py-4 text-center text-xs text-muted">No surge alerts in this station area.</p>
              ) : (
                <ul className="space-y-1.5 text-xs text-ink-2">
                  {d.alerts.map((a) => (
                    <li key={a.zone_id + a.crime_type} className="flex items-center gap-2">
                      <AlertIcon size={12} />
                      <span className="font-semibold text-ink">{a.zone_id}</span>
                      <span className="flex-1">{a.label}</span>
                      <span className="tabular text-muted">
                        {a.current_count} vs {fmtNum(a.baseline_mean, 1)} (z {fmtNum(a.z_score, 1)})
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
          <StationComparison items={overview.data?.items ?? []} selected={d.station.station_id} />
          <p className="text-[11px] leading-snug text-muted">
            {d.boundary_note} {d.limitation_statement}
          </p>
        </>
      )}
    </div>
  );
}

function StationComparison({ items, selected }: { items: StationOverviewItem[]; selected: string }) {
  const ui = useUI();
  return (
    <ChartCard
      title="All stations"
      subtitle="Zones in HIGH or VERY HIGH blended risk for at least one crime type and band"
      table={{
        columns: [
          { key: "n", header: "Station" },
          { key: "z", header: "Zones", align: "right" },
          { key: "h", header: "High-risk zones", align: "right" },
          { key: "p", header: "Peak risk", align: "right" },
          { key: "e", header: "Emerging", align: "right" },
          { key: "a", header: "Surge alerts", align: "right" },
        ],
        rows: items.map((s) => ({
          n: s.name,
          z: s.zones,
          h: s.high_risk_zones,
          p: fmtNum(s.peak_final_risk, 0),
          e: s.emerging_hotspots,
          a: s.surge_alerts,
        })),
      }}
    >
      <HBars
        rows={items.map((s) => ({
          key: s.station_id,
          label: (
            <button
              type="button"
              onClick={() => ui.set({ stationId: s.station_id })}
              className={s.station_id === selected ? "font-semibold text-ink" : "hover:text-ink"}
            >
              {s.name}
            </button>
          ),
          value: s.high_risk_zones,
          color: s.station_id === selected ? RISK_COLORS.HIGH : undefined,
          sub: `of ${s.zones}`,
        }))}
        format={(v) => v.toFixed(0)}
      />
    </ChartCard>
  );
}
