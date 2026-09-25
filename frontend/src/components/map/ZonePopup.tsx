"use client";

import type { CSSProperties } from "react";
import { Meters } from "@/components/charts/charts";
import { Icon } from "@/components/ui/icons";
import { ConfidencePill, RiskBadge, StateBadge } from "@/components/ui/primitives";
import { useMeta, useZoneDetail } from "@/lib/api";
import { WARN } from "@/lib/colors";
import { fmtNum, fmtPct, fmtWindow } from "@/lib/format";
import type { LayerItem } from "@/lib/layers";
import { nearestLocality } from "@/lib/localities";
import { useUI } from "@/lib/store";
import type { ZoneProps } from "@/lib/types";
import { useResolvedSelection } from "@/lib/useResolvedSelection";

const POPUP_W = 312;
const SHEET_BREAKPOINT = 560; // narrower maps show the popup as a bottom sheet

/**
 * Compact summary for a clicked zone or hotspot marker: its name, predicted risk for the
 * forecast window, the top contributing signals, and a way into the full zone panel.
 * Every number comes from the zone-detail API.
 */
export function ZonePopup({
  zone,
  point,
  bounds,
  item,
  onClose,
}: {
  zone: ZoneProps;
  point: { x: number; y: number };
  bounds: { w: number; h: number };
  item: (LayerItem & { crime_type?: string; band?: string }) | undefined;
  onClose: () => void;
}) {
  const ui = useUI();
  const { data: meta } = useMeta();
  // The popup describes what the map shows: the filtered crime type / band, or (for "All")
  // the zone's own highest-risk pair from the same API layer.
  const crimeType = ui.crimeType !== "ALL" ? ui.crimeType : (item?.crime_type ?? "AUTO");
  const band = ui.band !== "ALL" ? ui.band : item?.band && item.band !== "ALL" ? item.band : "AUTO";
  const resolved = useResolvedSelection({ zoneId: zone.zone_id, crimeType, band });
  const { data: d, error } = useZoneDetail(zone.zone_id, resolved.crimeType, resolved.band);

  const near = d ? nearestLocality(d.zone.centroid[0], d.zone.centroid[1]) : null;
  const p = d?.prediction;
  const top = p ? [...p.components].sort((a, b) => b.contribution - a.contribution).slice(0, 4) : [];

  const sheet = bounds.w < SHEET_BREAKPOINT;
  const style: CSSProperties = sheet
    ? { left: 8, right: 8, bottom: 8, maxHeight: "72%" }
    : (() => {
        const right = point.x + 18 + POPUP_W <= bounds.w - 8;
        const left = right ? point.x + 18 : Math.max(8, point.x - 18 - POPUP_W);
        const top = Math.min(Math.max(8, point.y - 60), Math.max(8, bounds.h - 420));
        return { left, top, width: POPUP_W, maxHeight: bounds.h - 16 };
      })();

  return (
    <div
      role="dialog"
      aria-label={`Zone ${zone.zone_id} summary`}
      className="absolute z-30 flex flex-col overflow-hidden rounded-lg border bg-surface text-[11px] shadow-2xl"
      style={{ ...style, borderColor: "var(--border-strong)" }}
      onClick={(e) => e.stopPropagation()}
    >
      <header className="flex items-start gap-2 border-b px-3 py-2" style={{ borderColor: "var(--border)" }}>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold text-ink">
            Zone {zone.zone_id}
            {near && <span className="font-normal text-ink-2"> · near {near.name}</span>}
          </p>
          <p className="truncate text-muted">
            {zone.station_name ?? "No station"} (synthetic jurisdiction)
            {near && " · locality name approximate"}
          </p>
        </div>
        <button onClick={onClose} className="rounded p-0.5 text-muted hover:bg-surface-2 hover:text-ink" aria-label="Close zone summary">
          <Icon name="close" />
        </button>
      </header>

      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 py-2.5">
        {error && <p className="text-ink-2">Could not load this zone: {error.message}</p>}
        {!d && !error && <p className="py-4 text-center text-muted">Loading zone…</p>}
        {d && p && (
          <>
            <div className="rounded-md bg-plane/60 px-2 py-1.5">
              <p className="text-muted">Forecast period</p>
              <p className="font-semibold text-ink">
                {fmtWindow(d.window.start, d.window.end)} · {d.band_label}
              </p>
              <p className="text-ink-2">{d.crime_label}</p>
            </div>

            <div className="flex items-end justify-between gap-3">
              <div>
                <p className="text-muted">Predicted risk (blended)</p>
                <p className="text-[22px] font-semibold leading-none text-ink">
                  {fmtNum(p.final_risk)}
                  <span className="text-xs font-normal text-muted">/100</span>
                </p>
                <div className="mt-1">
                  <RiskBadge band={p.risk_band} />
                </div>
              </div>
              <dl className="grid grid-cols-[auto_auto] gap-x-2 gap-y-0.5 text-right">
                <dt className="text-muted">CRS</dt>
                <dd className="tabular text-ink">{fmtNum(p.crs)}</dd>
                <dt className="text-muted">Probability</dt>
                <dd className="tabular text-ink">{fmtPct(p.probability)}</dd>
                <dd className="col-span-2 pt-0.5">
                  <ConfidencePill level={p.confidence} />
                </dd>
              </dl>
            </div>
            <p className="text-[10px] leading-snug text-muted">
              Scores are 0–100 indicators, not probabilities. The probability is for this event:{" "}
              {p.event_definition}.
            </p>

            <section>
              <p className="mb-1.5 font-semibold text-ink">Top contributing signals</p>
              <Meters
                rows={top.map((c) => ({ key: c.code, label: `${c.code} · ${c.name}`, value: c.contribution, max: c.weight * 100 }))}
              />
              {p.reasons[0] && <p className="mt-2 leading-snug text-ink-2">{p.reasons[0].text}</p>}
            </section>

            <div className="flex items-center justify-between">
              <span className="text-muted">Hotspot state</span>
              <StateBadge state={d.hotspot_state.state} />
            </div>
          </>
        )}
      </div>

      <footer className="space-y-2 border-t px-3 py-2" style={{ borderColor: "var(--border)" }}>
        <p className="flex gap-1.5 leading-snug text-ink-2">
          <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden className="mt-px shrink-0">
            <path d="M8 1.5 15 14H1L8 1.5Z" fill="none" stroke={WARN} strokeWidth="1.6" strokeLinejoin="round" />
            <path d="M8 6v4" stroke={WARN} strokeWidth="1.6" strokeLinecap="round" />
            <circle cx="8" cy="12" r="0.9" fill={WARN} />
          </svg>
          <span>
            <span className="font-semibold text-ink">{meta?.data_label ?? "Synthetic demonstration data"}.</span> A
            statistical pattern for planning, not a verified crime forecast.
          </span>
        </p>
        <button
          type="button"
          disabled={!d}
          onClick={() => {
            if (!d) return;
            ui.select({ zoneId: zone.zone_id, crimeType: d.crime_type, band: d.band });
            onClose();
          }}
          className="w-full rounded-md border px-2 py-1.5 text-xs font-medium text-ink hover:bg-surface-2 disabled:opacity-50"
          style={{ borderColor: "var(--border-strong)" }}
        >
          Open full zone intelligence
        </button>
      </footer>
    </div>
  );
}
