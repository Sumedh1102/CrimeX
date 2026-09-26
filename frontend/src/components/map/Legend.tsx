"use client";

import type { CSSProperties, ReactNode } from "react";
import { useMemo } from "react";
import { AlertIcon, StateIcon } from "@/components/ui/icons";
import {
  AFFINITY_COLORS,
  ANOMALY_BINS,
  HOTSPOT_CLASS_COLORS,
  HOTSPOT_CLASS_ORDER,
  PROBABILITY_BINS,
  RISK_COLORS,
  STATE_ORDER,
  STATE_STYLE,
  TEXTURE_INK,
} from "@/lib/colors";
import { windowUnit } from "@/lib/format";
import { styleFor, type LayerItem } from "@/lib/layers";
import { useUI } from "@/lib/store";
import type { LayerKey, Meta, RiskBand, RiskMetric } from "@/lib/types";

function texture(ink: string, cross: boolean): string {
  const a = `repeating-linear-gradient(45deg, ${ink} 0 1.3px, transparent 1.3px 5px)`;
  const b = `repeating-linear-gradient(135deg, ${ink} 0 1.3px, transparent 1.3px 5px)`;
  return cross ? `${a}, ${b}` : a;
}

function Chip({ color, tex }: { color: string | null; tex?: string | null }) {
  const style: CSSProperties = {
    backgroundColor: color ?? "transparent",
    backgroundImage: tex ?? undefined,
    border: color ? "1px solid rgba(255,255,255,0.08)" : "1px dashed rgba(255,255,255,0.25)",
  };
  return <span aria-hidden className="inline-block h-3 w-4 shrink-0 rounded-[3px]" style={style} />;
}

/** Matches the canvas-drawn attention marker on the map (mapImages.riskMarker). */
function RiskMarker({ filled }: { filled: boolean }) {
  return (
    <svg width="13" height="13" viewBox="0 0 20 20" aria-hidden className="shrink-0">
      <circle cx="10" cy="10" r="6.5" fill="none" stroke="#0d0d0d" strokeWidth="4.5" />
      <circle cx="10" cy="10" r="6.5" fill="none" stroke="#ffffff" strokeWidth="2" />
      <circle cx="10" cy="10" r={filled ? 3 : 2.2} fill={filled ? "#ffffff" : RISK_COLORS.HIGH} />
    </svg>
  );
}

/** SVG twins of the canvas movement markers (mapImages.movementIcon). */
function MoveGlyph({ kind }: { kind: "arrow" | "hold" | "new" | "gone" }) {
  return (
    <svg width="13" height="13" viewBox="0 0 20 20" aria-hidden className="shrink-0">
      {kind === "arrow" && <path d="M10 2.5 16 16 10 13 4 16Z" fill="#ffffff" stroke="#0d0d0d" strokeWidth="1.5" strokeLinejoin="round" />}
      {kind === "hold" && <circle cx="10" cy="10" r="5.5" fill="none" stroke="#ffffff" strokeWidth="1.8" />}
      {(kind === "new" || kind === "gone") && (
        <>
          <circle cx="10" cy="10" r="7" fill="#0d0d0d" stroke="#ffffff" strokeWidth="1.4" />
          <path
            d={kind === "new" ? "M10 6.5v7M6.5 10h7" : "M7.2 7.2l5.6 5.6M12.8 7.2l-5.6 5.6"}
            stroke="#ffffff"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
        </>
      )}
    </svg>
  );
}

function MovementLegend() {
  return (
    <div className="mt-2.5 border-t pt-2" style={{ borderColor: "var(--border)" }}>
      <p className="font-semibold text-ink">Hotspot movement</p>
      <ul className="mt-1 space-y-1 text-ink-2">
        <li className="flex items-center gap-2"><MoveGlyph kind="arrow" />Shifted (dashed path, distance, direction)</li>
        <li className="flex items-center gap-2"><MoveGlyph kind="hold" />Continued in place</li>
        <li className="flex items-center gap-2"><MoveGlyph kind="new" />New cluster</li>
        <li className="flex items-center gap-2"><MoveGlyph kind="gone" />Dissipated</li>
      </ul>
      <p className="mt-1 leading-snug text-muted">Gi* hotspot clusters, previous vs latest analysis period. Descriptive, not a forecast.</p>
    </div>
  );
}

interface Entry {
  key: string;
  chip: ReactNode;
  label: string;
  sub?: string;
}

export function Legend({
  layer,
  meta,
  metric,
  textures,
  items,
  title,
}: {
  layer: LayerKey;
  meta: Meta;
  metric: RiskMetric;
  textures: boolean;
  items: Map<string, LayerItem>;
  title?: string;
}) {
  const showMovement = useUI((st) => st.showMovement);
  const counts = useMemo(() => {
    const c = new Map<string, number>();
    for (const it of items.values()) {
      const k = styleFor(layer, it, { metric, textures }).legendKey;
      c.set(k, (c.get(k) ?? 0) + 1);
    }
    return c;
  }, [items, layer, metric, textures]);

  let entries: Entry[] = [];
  let heading = title ?? "";
  let note = "";
  if (layer === "risk" && metric !== "probability") {
    heading = metric === "crs" ? "Explainable risk score (CRS)" : "Blended risk score";
    note =
      "0–100 indicator, not a probability. Bands are presentation cut points; HIGH and VERY HIGH also carry a marker and hatching.";
    entries = meta.risk_bands.map((b) => {
      const band = b.label as RiskBand;
      const tex =
        textures && band === "HIGH"
          ? texture(TEXTURE_INK.riskHigh, false)
          : textures && band === "VERY HIGH"
            ? texture(TEXTURE_INK.riskVeryHigh, true)
            : null;
      const marker = band === "VERY HIGH" ? <RiskMarker filled /> : band === "HIGH" ? <RiskMarker filled={false} /> : null;
      return {
        key: band,
        chip: (
          <span className="flex w-[34px] shrink-0 items-center gap-1">
            <Chip color={RISK_COLORS[band]} tex={tex} />
            {marker}
          </span>
        ),
        label: band,
        sub: `${b.min === 0 ? 0 : b.min}–${b.max}`,
      };
    });
  } else if (layer === "risk") {
    heading = "Calibrated probability";
    note = "P(≥1 reported incident in the band during the window).";
    entries = PROBABILITY_BINS.map((b) => ({ key: b.label, chip: <Chip color={b.color} />, label: b.label }));
  } else if (layer === "hotspots") {
    heading = "Historical hotspots (Gi*)";
    note = "Getis-Ord Gi* significance of incident counts in the selected period.";
    entries = HOTSPOT_CLASS_ORDER.map((c) => ({
      key: c,
      chip: <Chip color={HOTSPOT_CLASS_COLORS[c]} />,
      label: meta.hotspot_classes.find((x) => x.code === c)?.label ?? c,
    }));
  } else if (layer === "states") {
    heading = "Hotspot state";
    note = "From Gi* over the last 26 four-week periods and a Mann-Kendall trend.";
    entries = STATE_ORDER.map((s) => {
      const st = STATE_STYLE[s];
      return {
        key: s,
        chip: (
          <span className="flex items-center gap-1">
            <Chip color={st.color} tex={textures && st.texture ? texture(TEXTURE_INK.persistent, false) : null} />
            {s !== "STABLE" && <StateIcon state={s} color={s === "DECLINING" || s === "SPORADIC" ? "#c3c2b7" : st.color!} size={11} />}
          </span>
        ),
        label: st.label,
        sub: s === "STABLE" ? "no fill" : undefined,
      };
    });
  } else if (layer === "affinity") {
    heading = "Crime Affinity Index (CAI)";
    note = "Historical association with the crime type, 0–100 (not causal).";
    entries = meta.affinity_bands.map((b) => ({
      key: b.label,
      chip: <Chip color={AFFINITY_COLORS[b.label as keyof typeof AFFINITY_COLORS]} />,
      label: b.label,
      sub: `${b.min === 0 ? 0 : b.min}–${b.max}`,
    }));
  } else {
    heading = "Crime Surge Detector";
    note = `Last ${windowUnit(meta.forecast_window.days)} vs the previous 52 weeks (z-score).`;
    entries = [
      ...ANOMALY_BINS.map((b) => ({ key: b.label, chip: <Chip color={b.color} />, label: b.label })),
      { key: "alert", chip: <AlertIcon size={13} />, label: "Surge alert" },
    ];
  }

  return (
    <div className="text-[11px]">
      <p className="font-semibold text-ink">{heading}</p>
      <p className="sr-only">Zone counts per legend entry are shown on the right.</p>
      <ul className="mt-1.5 space-y-1">
        {entries.map((e) => (
          <li key={e.key} className="flex items-center gap-2 text-ink-2">
            {e.chip}
            <span className="flex-1">{e.label}</span>
            {e.sub && <span className="tabular text-muted">{e.sub}</span>}
            <span className="tabular w-8 text-right text-muted" title="zones">
              {counts.get(e.key) ?? 0}
            </span>
          </li>
        ))}
      </ul>
      {note && <p className="mt-2 leading-snug text-muted">{note}</p>}
      {showMovement && <MovementLegend />}
    </div>
  );
}
