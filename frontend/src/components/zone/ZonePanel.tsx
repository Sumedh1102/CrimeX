"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ChartCard } from "@/components/charts/ChartCard";
import { Columns, DivergingBars, HBars, Meters, TrendLine } from "@/components/charts/charts";
import { AlertIcon, Icon, StateIcon } from "@/components/ui/icons";
import {
  ConfidencePill,
  Dl,
  ErrorNote,
  Loading,
  RiskBadge,
  Select,
  StateBadge,
  Swatch,
} from "@/components/ui/primitives";
import { useMeta, useZoneDetail } from "@/lib/api";
import { AFFINITY_COLORS, RISK_COLORS, SERIES, STATE_BADGE } from "@/lib/colors";
import { fmtDate, fmtDateTime, fmtInt, fmtNum, fmtPct, fmtWeek, fmtWindow } from "@/lib/format";
import { useUI, type Selection } from "@/lib/store";
import { useResolvedSelection } from "@/lib/useResolvedSelection";
import type { ZoneDetail } from "@/lib/types";

export function ZonePanelHost() {
  const selected = useUI((s) => s.selected);
  const clear = useUI((s) => s.clearSelection);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && clear();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clear]);
  return (
    <AnimatePresence>
      {selected && (
        <motion.aside
          key="zone-panel"
          aria-label={`Zone ${selected.zoneId} details`}
          initial={{ x: 480, opacity: 0.6 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 480, opacity: 0 }}
          transition={{ type: "tween", duration: 0.18 }}
          className="fixed bottom-0 right-0 top-0 z-40 flex w-[480px] max-w-full flex-col border-l bg-plane shadow-2xl"
          style={{ borderColor: "var(--border-strong)" }}
        >
          <ZonePanel key={`${selected.zoneId}|${selected.crimeType}|${selected.band}`} selection={selected} onClose={clear} />
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function ZonePanel({ selection, onClose }: { selection: Selection; onClose: () => void }) {
  const { data: meta } = useMeta();
  const resolved = useResolvedSelection(selection);
  // Panel-local overrides; the host remounts this component for every new selection.
  const [crimeType, setCrimeType] = useState<string | null>(null);
  const [band, setBand] = useState<string | null>(null);
  const ct = crimeType ?? resolved.crimeType;
  const bd = band ?? resolved.band;
  const { data: d, error, isLoading } = useZoneDetail(selection.zoneId, ct, bd);

  return (
    <>
      <header className="flex items-start gap-3 border-b px-4 py-3" style={{ borderColor: "var(--border)" }}>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] uppercase tracking-wide text-muted">Zone intelligence</p>
          <h2 className="text-lg font-semibold text-ink">Zone {selection.zoneId}</h2>
          <p className="text-xs text-muted">
            {d?.zone.station_name ?? "…"} · {d ? `${d.zone.area_km2} km² land` : ""}{" "}
            {d && `· ${d.zone.centroid[1].toFixed(4)}, ${d.zone.centroid[0].toFixed(4)}`}
          </p>
        </div>
        <button onClick={onClose} className="rounded p-1 text-muted hover:bg-surface hover:text-ink" aria-label="Close panel">
          <Icon name="close" />
        </button>
      </header>
      {meta && ct && bd && (
        <div className="flex gap-3 border-b px-4 py-2.5" style={{ borderColor: "var(--border)" }}>
          <Select label="Crime type" value={ct} onChange={setCrimeType} options={meta.crime_types.map((c) => ({ value: c.code, label: c.label }))} className="flex-1" />
          <Select label="Time band" value={bd} onChange={setBand} options={meta.bands.map((b) => ({ value: b.code, label: b.label }))} className="flex-1" />
        </div>
      )}
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {error && <ErrorNote error={error} />}
        {!d && !error && <Loading label={isLoading || !ct ? "Loading zone" : "Loading"} />}
        {d && <PanelBody d={d} />}
      </div>
    </>
  );
}

function Section({ title, children, hint }: { title: string; children: ReactNode; hint?: string }) {
  return (
    <section className="rounded-lg border bg-surface px-3 py-3" style={{ borderColor: "var(--border)" }}>
      <h3 className="text-[12px] font-semibold text-ink">{title}</h3>
      {hint && <p className="mt-0.5 text-[11px] leading-snug text-muted">{hint}</p>}
      <div className="mt-2.5">{children}</div>
    </section>
  );
}

function ScoreTile({ label, value, children }: { label: string; value: ReactNode; children?: ReactNode }) {
  return (
    <div className="rounded-lg border bg-surface px-3 py-2.5" style={{ borderColor: "var(--border)" }}>
      <p className="text-[11px] text-ink-2">{label}</p>
      <div className="mt-1 text-2xl font-semibold leading-none text-ink">{value}</div>
      <div className="mt-1.5 space-y-1">{children}</div>
    </div>
  );
}

function PanelBody({ d }: { d: ZoneDetail }) {
  const p = d.prediction;
  const hs = d.hotspot_state;
  const timeline = d.history.crs_timeline;
  const peak = useMemo(() => [...d.bands].sort((a, b) => b.final_risk - a.final_risk)[0], [d.bands]);
  return (
    <>
      <p className="text-[11px] text-muted">
        Forecast window {fmtWindow(d.window.start, d.window.end)} · {d.crime_label} · {d.band_label}
      </p>

      <div className="grid grid-cols-2 gap-2">
        <ScoreTile label="Blended risk score" value={<>{fmtNum(p.final_risk)}<span className="text-sm font-normal text-muted">/100</span></>}>
          <RiskBadge band={p.risk_band} />
          <p className="text-[10px] leading-snug text-muted">
            {p.blend_ml_weight} × probability + {(1 - p.blend_ml_weight).toFixed(1)} × CRS/100. Not a probability.
          </p>
        </ScoreTile>
        <ScoreTile label="Explainable risk score (CRS)" value={<>{fmtNum(p.crs)}<span className="text-sm font-normal text-muted">/100</span></>}>
          <RiskBadge band={p.crs_band} />
          <p className="text-[10px] leading-snug text-muted">Weighted sum of the seven signals below. Not a probability.</p>
        </ScoreTile>
        <div className="col-span-2 rounded-lg border bg-surface px-3 py-2.5" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-[11px] text-ink-2">Calibrated event probability</p>
              <div className="mt-1 text-2xl font-semibold leading-none text-ink">{fmtPct(p.probability)}</div>
            </div>
            <div className="text-right">
              <ConfidencePill level={p.confidence} />
              <p className="mt-1 text-[10px] text-muted">
                Expected incidents: <span className="tabular text-ink-2">{fmtNum(p.expected_count, 2)}</span>
              </p>
            </div>
          </div>
          <p className="mt-2 text-[11px] leading-snug text-ink-2">
            <span className="text-muted">Event: </span>
            {p.event_definition}.
          </p>
          <p className="mt-1 text-[10px] leading-snug text-muted">
            Confidence reflects evidence strength: {fmtInt(p.support_incidents_52w)} incidents of this type here in the
            last 52 weeks; held-out calibration gap near this probability {fmtPct(p.calibration_gap)}.
          </p>
        </div>
      </div>

      <Section title="Why is this zone flagged?" hint="Generated from the measured inputs of each signal, highest contribution first.">
        {p.reasons.length === 0 ? (
          <p className="text-xs text-muted">No signal is notably elevated for this crime type and band.</p>
        ) : (
          <ol className="space-y-2">
            {p.reasons.map((r, i) => (
              <li key={r.component + i} className="flex gap-2 text-xs leading-snug text-ink-2">
                <span className="tabular mt-px w-4 shrink-0 text-muted">{i + 1}.</span>
                <span className="flex-1">{r.text}</span>
                {r.contribution_points !== null && (
                  <span className="tabular shrink-0 text-muted" title="CRS points from this signal">
                    +{r.contribution_points.toFixed(1)}
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="Contributing signals" hint="Points each signal adds to the CRS (track = its maximum, weight × 100).">
        <Meters
          rows={p.components.map((c) => ({
            key: c.code,
            label: `${c.code} · ${c.name}`,
            value: c.contribution,
            max: c.weight * 100,
            detail: (
              <>
                value {c.value.toFixed(2)} ·{" "}
                {Object.entries(c.raw)
                  .map(([k, v]) => `${k.replaceAll("_", " ")} ${v === null ? "–" : Number.isInteger(v) ? v : Number(v).toFixed(2)}`)
                  .join(" · ")}
              </>
            ),
          }))}
        />
      </Section>

      <Section
        title="Model drivers (SHAP)"
        hint="TreeSHAP contributions of named model inputs to the classifier's log-odds (before calibration, which preserves direction)."
      >
        <DivergingBars
          posLabel="raises probability"
          negLabel="lowers"
          format={(v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}`}
          rows={p.shap.top.map((s) => ({
            key: s.feature,
            label: s.label,
            value: s.shap_log_odds,
            detail: `input value ${Number.isInteger(s.value) ? s.value : s.value.toFixed(3)} · ${s.group}`,
          }))}
        />
      </Section>

      <ChartCard
        title="Time bands, next 7 days"
        subtitle={`Blended risk per band · highest: ${peak.label}`}
        table={{
          columns: [
            { key: "band", header: "Band" },
            { key: "risk", header: "Blended", align: "right" },
            { key: "crs", header: "CRS", align: "right" },
            { key: "p", header: "Probability", align: "right" },
          ],
          rows: d.bands.map((b) => ({ band: b.label, risk: fmtNum(b.final_risk), crs: fmtNum(b.crs), p: fmtPct(b.probability) })),
        }}
      >
        <Columns
          data={d.bands.map((b) => ({ band: b.label.split(" ")[0], value: b.final_risk }))}
          xKey="band"
          yKey="value"
          name="blended risk"
          height={140}
          color={RISK_COLORS[p.risk_band]}
          highlight={(_, i) => d.bands[i].band === d.band}
          format={(v) => v.toFixed(0)}
        />
      </ChartCard>

      <Section title="Hotspot state" hint={hs.description}>
        <div className="flex items-center justify-between">
          <StateBadge state={hs.state} />
          <span className="text-[11px] text-muted">
            hot in {hs.hot_periods} of {hs.n_periods} periods · trend {hs.trend.toLowerCase()}
          </span>
        </div>
        {hs.current_hot_run_periods > 0 && (
          <p className="mt-1 text-[11px] text-ink-2">
            Current hotspot run: {hs.current_hot_run_periods} period(s) (~{hs.current_hot_run_periods * hs.period_weeks} weeks).
          </p>
        )}
        <div className="mt-2">
          <Columns
            data={hs.gi_z_series.map((z, i) => ({ period: `P${i + 1}`, z }))}
            xKey="period"
            yKey="z"
            name="Gi* z"
            height={120}
            color={STATE_BADGE[hs.state] === "#0ca30c" ? SERIES.primary : "#e66767"}
            highlight={(row) => Number(row.z) >= 1.96}
            format={(v) => v.toFixed(1)}
            refLine={{ y: 1.96, label: "95% hot" }}
          />
          <p className="mt-1 text-[10px] text-muted">
            Gi* z-score per four-week period (oldest → latest); highlighted periods are significant hotspots.
          </p>
        </div>
      </Section>

      <Section title="Crime Surge Detector" hint="Last week compared with the previous 52 weeks for this crime type in the zone.">
        <div className="flex items-center gap-3">
          {d.surge.is_alert && <AlertIcon size={16} />}
          <Dl
            items={[
              ["Last week", fmtInt(d.surge.current_count)],
              ["Typical week", `${fmtNum(d.surge.baseline_mean, 2)} ± ${fmtNum(d.surge.baseline_std, 2)}`],
              ["z-score", fmtNum(d.surge.z_score, 2)],
              ["Status", d.surge.is_alert ? "Surge alert" : "No alert"],
            ]}
          />
        </div>
      </Section>

      <ChartCard
        title="Crime affinity profile"
        subtitle="CAI by crime type (historical association, not causation)"
        table={{
          columns: [
            { key: "t", header: "Crime type" },
            { key: "cai", header: "CAI", align: "right" },
            { key: "lq", header: "LQ", align: "right" },
            { key: "n", header: "Incidents 52w", align: "right" },
          ],
          rows: d.affinity_profile.map((a) => ({ t: a.label, cai: fmtNum(a.cai), lq: fmtNum(a.location_quotient, 2), n: fmtInt(a.incidents_52w) })),
        }}
      >
        <HBars
          rows={d.affinity_profile.map((a) => ({
            key: a.crime_type,
            label: (
              <span className="inline-flex items-center gap-1.5">
                <Swatch color={AFFINITY_COLORS[a.affinity_band]} />
                {a.label}
              </span>
            ),
            value: a.cai,
            sub: a.affinity_band,
          }))}
          max={100}
          format={(v) => v.toFixed(0)}
        />
      </ChartCard>

      <ChartCard
        title="Risk across crime types"
        subtitle="Highest blended score per crime type (its peak band)"
        table={{
          columns: [
            { key: "t", header: "Crime type" },
            { key: "b", header: "Band" },
            { key: "r", header: "Blended", align: "right" },
            { key: "p", header: "Probability", align: "right" },
          ],
          rows: d.risk_profile.map((r) => ({ t: r.label, b: r.band, r: fmtNum(r.final_risk), p: fmtPct(r.probability) })),
        }}
      >
        <HBars
          rows={d.risk_profile.map((r) => ({
            key: r.crime_type,
            label: r.label,
            value: r.final_risk,
            color: RISK_COLORS[r.risk_band],
            sub: r.risk_band,
          }))}
          max={100}
          format={(v) => v.toFixed(0)}
        />
      </ChartCard>

      <ChartCard
        title="Weekly incidents, last 52 weeks"
        subtitle={`${d.crime_label}, all bands`}
        table={{
          columns: [
            { key: "w", header: "Week of" },
            { key: "n", header: "Incidents", align: "right" },
          ],
          rows: d.history.weekly.map((w) => ({ w: fmtDate(w.week_start), n: w.count })),
        }}
      >
        <Columns data={d.history.weekly} xKey="week_start" yKey="count" name="incidents" height={130} xFormat={fmtWeek} />
      </ChartCard>

      <ChartCard
        title="Risk explanation timeline"
        subtitle="CRS for this band over recent windows"
        table={{
          columns: [
            { key: "w", header: "Window start" },
            { key: "crs", header: "CRS", align: "right" },
            ...["F", "R", "T", "A", "S", "P", "X"].map((c) => ({ key: c, header: c, align: "right" as const })),
            { key: "obs", header: "Observed", align: "right" },
          ],
          rows: timeline.map((t) => ({
            w: fmtDate(t.window_start),
            crs: fmtNum(t.crs),
            ...Object.fromEntries(["F", "R", "T", "A", "S", "P", "X"].map((c) => [c, Number(t[c]).toFixed(2)])),
            obs: t.observed_count < 0 ? "forecast" : t.observed_count,
          })),
        }}
      >
        <TrendLine data={timeline} xKey="window_start" yKey="crs" name="CRS" height={140} xFormat={fmtWeek} domain={[0, 100]} format={(v) => v.toFixed(0)} />
      </ChartCard>

      <Section title="Recent incidents" hint={`${d.data_label}: simulated records, not real police incidents.`}>
        {d.recent_incidents.length === 0 ? (
          <p className="text-xs text-muted">None recorded.</p>
        ) : (
          <ul className="space-y-1 text-[11px]">
            {d.recent_incidents.map((i) => (
              <li key={i.incident_id} className="flex justify-between gap-2 text-ink-2">
                <span className="font-mono text-muted">{i.incident_id}</span>
                <span className="tabular">{fmtDateTime(i.timestamp)}</span>
                <span className="w-20 text-right text-muted">{i.band.toLowerCase()}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Provenance">
        <Dl
          items={[
            ["Prediction", <span key="p" className="font-mono">{p.prediction_id}</span>],
            ["Model", d.versions.model_version],
            ["Training data", d.versions.training_dataset_version],
            ["Features", d.versions.feature_version],
            ["Generated", `${fmtDateTime(d.versions.generated_at)} UTC`],
            ["Data", d.data_label],
          ]}
        />
        <p className="mt-2 text-[11px] leading-snug text-muted">{d.limitation_statement}</p>
      </Section>
      <p className="pb-2 text-center text-[10px] text-muted">
        <StateIcon state={hs.state} color={STATE_BADGE[hs.state]} size={10} /> Press Esc to close
      </p>
    </>
  );
}
