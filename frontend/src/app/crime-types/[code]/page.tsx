"use client";

import Link from "next/link";
import { use } from "react";
import { ChartCard } from "@/components/charts/ChartCard";
import { Columns, Heatmap, RadarProfile, TrendLine } from "@/components/charts/charts";
import { Card, DataTable, Dl, ErrorNote, Loading, RiskBadge, StateBadge } from "@/components/ui/primitives";
import { useCrimeTypeProfile } from "@/lib/api";
import { fmtDate, fmtInt, fmtNum, fmtPct, fmtWeek, titleCase } from "@/lib/format";
import { useUI } from "@/lib/store";

const DIM_LABELS: Record<string, string> = {
  spatial_concentration: "Spatial concentration",
  time_concentration: "Time concentration",
  weekend_concentration: "Weekend concentration",
  repeat_location: "Repeat location",
  neighbor_spillover: "Neighbour spillover",
  recent_trend: "Recent trend",
  hotspot_persistence: "Hotspot persistence",
  temporal_similarity: "Temporal similarity",
};

type OfficialPeriod = { period: { label: string; start: string; end: string }; registered: number | null; detected: number | null };

export default function CrimeTypePage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  const { data: p, error } = useCrimeTypeProfile(code);
  const ui = useUI();
  if (error) return <div className="p-5"><ErrorNote error={error} /></div>;
  if (!p) return <Loading />;
  const fp = p.fingerprint;
  const official = (["CM", "PM", "CY", "PY"] as const).map((k) => [k, p.official.values[k] as OfficialPeriod] as const);
  return (
    <div className="space-y-4 p-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <Link href="/crime-types" className="text-[11px] text-muted hover:text-ink-2">← Crime types</Link>
          <h2 className="text-xl font-semibold text-ink">{p.label}</h2>
          <p className="text-xs text-muted">Official head “{p.label_official}” · project severity {p.severity ?? "–"}/5</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
        <Card title="Official counts (Brihan Mumbai, city level)" subtitle={p.official.note}>
          <DataTable
            rows={official.map(([k, v]) => ({ k, ...v }))}
            rowKey={(r) => r.k}
            columns={[
              { key: "p", header: "Period", render: (r) => `${r.period.label} (${fmtDate(r.period.start)} – ${fmtDate(r.period.end)})` },
              { key: "r", header: "Registered", render: (r) => fmtInt(r.registered), align: "right" },
              { key: "d", header: "Detected", render: (r) => fmtInt(r.detected), align: "right" },
            ]}
          />
          <p className="mt-2 text-[11px] text-muted">
            Year-to-date change in registrations: {fmtInt(p.official.values.difference_registered_ytd as number)}.
          </p>
        </Card>
        <Card title="Incident data" subtitle={`${p.incident_data.data_label}: simulated, anchored to the official counts`}>
          <Dl
            items={[
              ["Last 4 weeks", fmtInt(p.incident_data.last_4w)],
              ["Last 52 weeks", fmtInt(p.incident_data.last_52w)],
              ["All synthetic history", fmtInt(p.incident_data.total)],
              ["Peak hours", fp.details.peak_hours.map((h) => `${String(h).padStart(2, "0")}:00`).join(", ") || "–"],
              ["Weekend share", `${fmtPct(fp.details.weekend_share)} (×${fmtNum(fp.details.weekend_lift, 2)} vs chance)`],
              ["Recent trend", `${titleCase(fp.details.trend_direction)} (${fp.details.recent_4w} in 4 weeks vs ${fmtNum(fp.details.baseline_4w)} typical)`],
            ]}
          />
        </Card>
        <ChartCard
          title="Crime Pattern Fingerprint"
          subtitle={`Learned from ${fmtInt(fp.incidents)} incidents, ${fmtDate(fp.window.start)} – ${fmtDate(fp.window.end)}`}
          table={{
            columns: [
              { key: "d", header: "Dimension" },
              { key: "v", header: "Value", align: "right" },
              { key: "l", header: "Level" },
            ],
            rows: fp.dimensions.map((d) => ({ d: DIM_LABELS[d.name] ?? d.name, v: d.value.toFixed(2), l: d.label })),
          }}
        >
          <RadarProfile name="fingerprint" data={fp.dimensions.map((d) => ({ axis: DIM_LABELS[d.name] ?? d.name, value: d.value }))} height={250} />
          <ul className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
            {fp.dimensions.map((d) => (
              <li key={d.name} className="flex justify-between gap-2">
                <span className="text-ink-2">{DIM_LABELS[d.name]}</span>
                <span className="font-semibold text-ink">{d.label}</span>
              </li>
            ))}
          </ul>
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <ChartCard
          title="Weekly incidents, last 104 weeks"
          table={{ columns: [{ key: "w", header: "Week of" }, { key: "n", header: "Incidents", align: "right" }], rows: p.weekly_104w.map((w) => ({ w: fmtDate(w.week_start), n: w.count })) }}
        >
          <TrendLine data={p.weekly_104w} xKey="week_start" yKey="count" name="incidents" xFormat={fmtWeek} />
        </ChartCard>
        <ChartCard
          title="Crime-pattern calendar"
          subtitle="Incidents by weekday and time band, last 52 weeks (computed from the data)"
          table={{
            columns: [{ key: "d", header: "Day" }, ...p.time_profile.calendar.columns.map((c) => ({ key: c, header: c, align: "right" as const }))],
            rows: p.time_profile.calendar.rows.map((r, i) => ({ d: r, ...Object.fromEntries(p.time_profile.calendar.columns.map((c, j) => [c, p.time_profile.calendar.counts[i][j]])) })),
          }}
        >
          <Heatmap rows={p.time_profile.calendar.rows} columns={p.time_profile.calendar.columns.map(titleCase)} counts={p.time_profile.calendar.counts} />
        </ChartCard>
        <ChartCard
          title="Hour of day"
          table={{ columns: [{ key: "h", header: "Hour" }, { key: "n", header: "Incidents", align: "right" }], rows: p.time_profile.hourly.map((n, h) => ({ h: `${h}:00`, n })) }}
        >
          <Columns data={p.time_profile.hourly.map((n, h) => ({ h, n }))} xKey="h" yKey="n" name="incidents" xFormat={(h) => `${String(h).padStart(2, "0")}h`} />
        </ChartCard>
        <Card title="Hotspot states" subtitle="Zones by state for this crime type">
          <div className="flex flex-wrap gap-4 text-xs">
            {Object.entries(p.states_summary).map(([s, n]) => (
              <span key={s} className="inline-flex items-center gap-1.5">
                <StateBadge state={s as never} /> <span className="tabular text-muted">{n}</span>
              </span>
            ))}
          </div>
          {p.emerging.length > 0 && (
            <>
              <p className="mt-3 text-[11px] font-semibold text-ink">Emerging zones</p>
              <ul className="mt-1 space-y-0.5 text-xs">
                {p.emerging.map((e) => (
                  <li key={e.zone_id}>
                    <button className="text-ink-2 hover:text-ink" onClick={() => ui.select({ zoneId: e.zone_id, crimeType: code, band: e.band ?? "AUTO" })}>
                      {e.zone_id} · {fmtNum(e.recent_rate, 1)} vs {fmtNum(e.prior_rate, 1)} per period
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <Card title="Highest affinity zones" subtitle="Crime Affinity Index (historical association)">
          <DataTable
            rows={p.top_zones_affinity}
            rowKey={(r) => r.zone_id}
            onRowClick={(r) => ui.select({ zoneId: r.zone_id, crimeType: code, band: "AUTO" })}
            columns={[
              { key: "z", header: "Zone", render: (r) => <span className="font-semibold text-ink">{r.zone_id}</span> },
              { key: "cai", header: "CAI", render: (r) => fmtNum(r.cai), align: "right" },
              { key: "b", header: "Band", render: (r) => r.affinity_band },
              { key: "lq", header: "LQ", render: (r) => fmtNum(r.location_quotient, 2), align: "right" },
              { key: "n", header: "Incidents 52w", render: (r) => fmtInt(r.incidents_52w), align: "right" },
              { key: "s", header: "State", render: (r) => <StateBadge state={r.state} /> },
            ]}
          />
        </Card>
        <Card title="Highest predicted risk" subtitle="Blended score for the forecast window (peak band)">
          <DataTable
            rows={p.top_zones_risk}
            rowKey={(r) => r.zone_id}
            onRowClick={(r) => ui.select({ zoneId: r.zone_id, crimeType: code, band: r.band })}
            columns={[
              { key: "z", header: "Zone", render: (r) => <span className="font-semibold text-ink">{r.zone_id}</span> },
              { key: "b", header: "Band", render: (r) => titleCase(r.band) },
              { key: "r", header: "Blended", render: (r) => <RiskBadge band={r.risk_band} value={r.final_risk} /> },
              { key: "p", header: "Probability", render: (r) => fmtPct(r.probability), align: "right" },
              { key: "s", header: "State", render: (r) => <StateBadge state={r.hotspot_state} /> },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
