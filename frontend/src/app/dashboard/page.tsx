"use client";

import { useMemo } from "react";
import { ChartCard } from "@/components/charts/ChartCard";
import { Columns, HBars, TrendLine } from "@/components/charts/charts";
import { FilterBar } from "@/components/map/Controls";
import { MapCard } from "@/components/map/MapCard";
import { AlertIcon, StateIcon } from "@/components/ui/icons";
import { Card, ErrorNote, Kpi, Loading, RiskBadge, Swatch } from "@/components/ui/primitives";
import { useDashboard, useMeta } from "@/lib/api";
import { RISK_COLORS, STATE_BADGE, STATE_STYLE } from "@/lib/colors";
import { fmtDate, fmtInt, fmtNextWindow, fmtNum, fmtSignedPct, fmtWeek } from "@/lib/format";
import { useUI } from "@/lib/store";

export default function DashboardPage() {
  const ui = useUI();
  const { data: meta } = useMeta();
  const { data: d, error } = useDashboard(ui.crimeType, ui.stationId);

  const trend = useMemo(() => {
    if (!d) return [];
    return d.trend.map((row) => {
      let total = 0;
      for (const [k, v] of Object.entries(row)) if (k !== "week_start") total += Number(v);
      return { week_start: row.week_start, total };
    });
  }, [d]);

  const select = (zoneId: string, crimeType: string, band?: string | null) =>
    ui.select({ zoneId, crimeType, band: band ?? "AUTO" });

  return (
    <div className="space-y-4 p-3 sm:p-5">
      <FilterBar />
      {error && <ErrorNote error={error} />}
      <div className="grid grid-cols-2 gap-2 sm:gap-3 xl:grid-cols-4">
        <Kpi
          label="Active hotspots"
          value={d ? fmtInt(d.kpis.active_hotspots) : "–"}
          hint={d?.kpi_definitions.active_hotspots}
          icon={<StateIcon state="ACTIVE" color={STATE_BADGE.ACTIVE} size={12} />}
        />
        <Kpi
          label="Emerging hotspots"
          value={d ? fmtInt(d.kpis.emerging_hotspots) : "–"}
          hint={d?.kpi_definitions.emerging_hotspots}
          icon={<StateIcon state="EMERGING" color={STATE_BADGE.EMERGING} size={12} />}
        />
        <Kpi
          label="Current anomalies"
          value={d ? fmtInt(d.kpis.current_anomalies) : "–"}
          hint={d?.kpi_definitions.current_anomalies}
          icon={<AlertIcon size={12} />}
        />
        <Kpi
          label="Predicted high-risk zones"
          value={d ? `${fmtInt(d.kpis.high_risk_zones)} / ${fmtInt(d.kpis.zones)}` : "–"}
          hint={d?.kpi_definitions.high_risk_zones}
          icon={<Swatch color={RISK_COLORS.HIGH} />}
        />
      </div>

      <div className="grid grid-cols-1 gap-3 2xl:grid-cols-[minmax(0,1fr)_360px] xl:grid-cols-[minmax(0,1fr)_320px]">
        <MapCard height={560} />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:flex xl:flex-col">
          <Card title="Top emerging zones" subtitle="Recent vs earlier incident rate per four-week period">
            {!d ? (
              <Loading />
            ) : d.top_emerging.length === 0 ? (
              <p className="text-xs text-muted">No emerging hotspots for this selection.</p>
            ) : (
              <ul className="-mx-1 space-y-0.5">
                {d.top_emerging.slice(0, 7).map((e) => (
                  <li key={e.zone_id + e.crime_type}>
                    <button
                      onClick={() => select(e.zone_id, e.crime_type, e.band)}
                      className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-xs hover:bg-surface-2"
                    >
                      <StateIcon state="EMERGING" color={STATE_BADGE.EMERGING} size={11} />
                      <span className="w-11 font-semibold text-ink">{e.zone_id}</span>
                      <span className="min-w-0 flex-1 truncate text-ink-2">{e.label}</span>
                      <span className="tabular text-muted" title="incidents per period: recent vs earlier">
                        {fmtNum(e.recent_rate, 1)} vs {fmtNum(e.prior_rate, 1)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Top crime types" subtitle="Last 4 weeks vs the 4 weeks before">
            {!d ? (
              <Loading />
            ) : (
              <ul className="space-y-1 text-xs">
                {d.top_crime_types.slice(0, 7).map((t) => (
                  <li key={t.crime_type} className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-ink-2">{t.label}</span>
                    <span className="tabular w-12 text-right font-semibold text-ink">{fmtInt(t.last_4w)}</span>
                    <span className="tabular w-14 text-right text-muted">{fmtSignedPct(t.change_pct)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Current alerts" subtitle="Crime Surge Detector, last complete week">
            {!d ? (
              <Loading />
            ) : d.alerts.length === 0 ? (
              <p className="text-xs text-muted">No surge alerts.</p>
            ) : (
              <ul className="-mx-1 space-y-0.5">
                {d.alerts.slice(0, 6).map((a) => (
                  <li key={a.zone_id + a.crime_type}>
                    <button
                      onClick={() => select(a.zone_id, a.crime_type)}
                      className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-xs hover:bg-surface-2"
                    >
                      <AlertIcon size={12} />
                      <span className="w-11 font-semibold text-ink">{a.zone_id}</span>
                      <span className="min-w-0 flex-1 truncate text-ink-2">{a.label}</span>
                      <span className="tabular text-muted">
                        {a.current_count} vs {fmtNum(a.baseline_mean, 1)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {d && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          <ChartCard
            title="Weekly incidents"
            subtitle={`Last 52 weeks to ${fmtDate(d.as_of)} · ${ui.crimeType === "ALL" ? "all modelled crime types" : meta?.crime_types.find((c) => c.code === ui.crimeType)?.label}`}
            table={{
              columns: [
                { key: "w", header: "Week of" },
                { key: "n", header: "Incidents", align: "right" },
              ],
              rows: trend.map((t) => ({ w: fmtDate(t.week_start), n: fmtInt(t.total) })),
            }}
          >
            <TrendLine data={trend} xKey="week_start" yKey="total" name="incidents" xFormat={fmtWeek} />
          </ChartCard>
          <ChartCard
            title="Crime-type distribution"
            subtitle="Incidents in the last 52 weeks"
            table={{
              columns: [
                { key: "t", header: "Crime type" },
                { key: "n", header: "Incidents", align: "right" },
              ],
              rows: d.distribution.map((r) => ({ t: r.label, n: fmtInt(r.count) })),
            }}
          >
            <HBars rows={d.distribution.map((r) => ({ key: r.crime_type, label: r.label, value: r.count }))} />
          </ChartCard>
          <ChartCard
            title="Hotspot lifecycle"
            subtitle="Zone × crime-type pairs by hotspot state"
            table={{
              columns: [
                { key: "s", header: "State" },
                { key: "n", header: "Pairs", align: "right" },
              ],
              rows: d.lifecycle.map((r) => ({ s: STATE_STYLE[r.state].label, n: fmtInt(r.count) })),
            }}
          >
            <HBars
              rows={d.lifecycle.map((r) => ({
                key: r.state,
                label: (
                  <span className="inline-flex items-center gap-1.5">
                    <StateIcon state={r.state} color={STATE_BADGE[r.state]} size={11} />
                    {STATE_STYLE[r.state].label}
                  </span>
                ),
                value: r.count,
              }))}
            />
          </ChartCard>
          <ChartCard
            title="Hourly distribution"
            subtitle="Incidents by hour of day, last 52 weeks"
            table={{
              columns: [
                { key: "h", header: "Hour" },
                { key: "n", header: "Incidents", align: "right" },
              ],
              rows: d.hourly.map((r) => ({ h: `${String(r.hour).padStart(2, "0")}:00`, n: fmtInt(r.count) })),
            }}
          >
            <Columns data={d.hourly} xKey="hour" yKey="count" name="incidents" xFormat={(h) => `${String(h).padStart(2, "0")}h`} />
          </ChartCard>
          <ChartCard
            title="Weekday distribution"
            subtitle="Incidents by day of week, last 52 weeks"
            table={{
              columns: [
                { key: "d", header: "Day" },
                { key: "n", header: "Incidents", align: "right" },
              ],
              rows: d.weekday.map((r) => ({ d: r.day, n: fmtInt(r.count) })),
            }}
          >
            <Columns data={d.weekday} xKey="day" yKey="count" name="incidents" />
          </ChartCard>
          <Card title="Reading the scores" subtitle="Three numbers, never conflated">
            <ul className="space-y-2 text-xs leading-snug text-ink-2">
              <li>
                <span className="font-semibold text-ink">Calibrated probability</span>: chance of at least one reported
                incident of the crime type in the zone during the time band of the {fmtNextWindow(d.window.days)}. The only probability.
              </li>
              <li>
                <span className="font-semibold text-ink">Explainable risk score (CRS)</span>: 0–100 weighted sum of seven
                normalised signals (frequency, recency, trend, affinity, neighbours, time similarity, anomaly).
              </li>
              <li>
                <span className="font-semibold text-ink">Blended risk score</span>: 0.6 × probability + 0.4 × CRS, on
                0–100. Bands{" "}
                <RiskBadge band="LOW" /> … <RiskBadge band="VERY HIGH" /> are presentation cut points.
              </li>
              <li>
                <span className="font-semibold text-ink">Crime Affinity Index</span>: historical association of a zone
                with a crime type. Statistical, not causal.
              </li>
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
