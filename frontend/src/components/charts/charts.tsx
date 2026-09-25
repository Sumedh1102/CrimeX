"use client";

import type { ReactNode } from "react";
import {
  Area,
  Bar,
  BarChart,
  type BarShapeProps,
  CartesianGrid,
  ComposedChart,
  Line,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  Rectangle,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  type TooltipContentProps,
  XAxis,
  YAxis,
} from "recharts";
import { CHROME, SERIES } from "@/lib/colors";

const AXIS_TICK = { fill: CHROME.muted, fontSize: 11 };

/** Tooltip: the value is the strong element, the label secondary; series keyed by a short line. */
function makeTooltip(format: (v: number) => string, labelFormat?: (l: string) => string) {
  return function ChartTooltip({ active, payload, label }: TooltipContentProps) {
    if (!active || !payload?.length) return null;
    return (
      <div
        className="rounded-md border bg-surface px-2.5 py-1.5 text-[11px] shadow-xl"
        style={{ borderColor: "var(--border-strong)" }}
      >
        <div className="mb-0.5 text-muted">{labelFormat ? labelFormat(String(label)) : String(label)}</div>
        {payload.map((p) => (
          <div key={String(p.dataKey)} className="flex items-center gap-2">
            <span aria-hidden className="inline-block h-[2px] w-3 rounded" style={{ background: p.color ?? SERIES.primary }} />
            <span className="tabular font-semibold text-ink">{format(Number(p.value))}</span>
            <span className="text-ink-2">{String(p.name ?? "")}</span>
          </div>
        ))}
      </div>
    );
  };
}

export function Columns({
  data,
  xKey,
  yKey,
  name,
  height = 180,
  color = SERIES.primary,
  highlight,
  format = (v) => v.toLocaleString("en-IN"),
  xFormat,
  refLine,
}: {
  data: Record<string, unknown>[];
  xKey: string;
  yKey: string;
  name: string;
  height?: number;
  color?: string;
  highlight?: (row: Record<string, unknown>, i: number) => boolean; // emphasis: others gray
  format?: (v: number) => string;
  xFormat?: (v: string) => string;
  refLine?: { y: number; label: string };
}) {
  const shape = (props: BarShapeProps) => {
    const fill = highlight ? (highlight(props.payload, props.index) ? color : SERIES.deemphasis) : color;
    const r = (props.value as number) < 0 ? [0, 0, 4, 4] : [4, 4, 0, 0];
    return <Rectangle {...props} fill={fill} radius={r as [number, number, number, number]} />;
  };
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: -12 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke={CHROME.grid} />
          <XAxis dataKey={xKey} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: CHROME.baseline }} tickFormatter={xFormat} interval="preserveStartEnd" minTickGap={8} />
          <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={44} tickFormatter={(v) => format(Number(v))} />
          <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={makeTooltip(format, xFormat)} />
          {refLine && <ReferenceLine y={refLine.y} stroke={CHROME.muted} strokeWidth={1} label={{ value: refLine.label, fill: CHROME.muted, fontSize: 10, position: "insideTopRight" }} />}
          <Bar dataKey={yKey} name={name} fill={color} maxBarSize={24} shape={shape} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TrendLine({
  data,
  xKey,
  yKey,
  name,
  height = 200,
  color = SERIES.primary,
  format = (v) => v.toLocaleString("en-IN"),
  xFormat,
  domain,
}: {
  data: Record<string, unknown>[];
  xKey: string;
  yKey: string;
  name: string;
  height?: number;
  color?: string;
  format?: (v: number) => string;
  xFormat?: (v: string) => string;
  domain?: [number, number];
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke={CHROME.grid} />
          <XAxis dataKey={xKey} tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: CHROME.baseline }} tickFormatter={xFormat} interval="preserveStartEnd" minTickGap={24} />
          <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={44} domain={domain} tickFormatter={(v) => format(Number(v))} />
          <Tooltip cursor={{ stroke: CHROME.muted, strokeWidth: 1 }} content={makeTooltip(format, xFormat)} />
          <Area dataKey={yKey} name={name} type="monotone" stroke="none" fill={color} fillOpacity={0.1} isAnimationActive={false} legendType="none" tooltipType="none" />
          <Line dataKey={yKey} name={name} type="monotone" stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: CHROME.surface, strokeWidth: 2 }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Horizontal bars in plain HTML: label, bar (<= 14px, rounded data end), value at the tip. */
export function HBars({
  rows,
  format = (v) => v.toLocaleString("en-IN"),
  max,
  color = SERIES.primary,
}: {
  rows: { key: string; label: ReactNode; value: number; color?: string; sub?: ReactNode; title?: string }[];
  format?: (v: number) => string;
  max?: number;
  color?: string;
}) {
  const m = max ?? Math.max(1e-9, ...rows.map((r) => r.value));
  return (
    <ul className="space-y-1.5">
      {rows.map((r) => (
        <li key={r.key} className="grid grid-cols-[minmax(0,40%)_1fr] items-center gap-2 text-xs" title={r.title}>
          <span className="truncate text-ink-2">{r.label}</span>
          <span className="flex items-center gap-2">
            <span className="relative h-3 flex-1">
              <span
                className="absolute inset-y-0 left-0 rounded-r"
                style={{ width: `${Math.max(0, (r.value / m) * 100)}%`, background: r.color ?? color, minWidth: r.value > 0 ? 2 : 0 }}
              />
            </span>
            <span className="tabular w-12 shrink-0 text-right text-ink">{format(r.value)}</span>
            {r.sub && <span className="w-16 shrink-0 text-right text-muted">{r.sub}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Signed horizontal bars around a centre line (diverging: warm = raises, cool = lowers). */
export function DivergingBars({
  rows,
  format,
  posLabel,
  negLabel,
}: {
  rows: { key: string; label: ReactNode; value: number; detail?: ReactNode }[];
  format: (v: number) => string;
  posLabel: string;
  negLabel: string;
}) {
  const m = Math.max(1e-9, ...rows.map((r) => Math.abs(r.value)));
  return (
    <div>
      <div className="mb-1 flex justify-between text-[10px] text-muted">
        <span>← {negLabel}</span>
        <span>{posLabel} →</span>
      </div>
      <ul className="space-y-1.5">
        {rows.map((r) => {
          const w = (Math.abs(r.value) / m) * 50;
          const pos = r.value >= 0;
          return (
            <li key={r.key} className="text-xs">
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate text-ink-2">{r.label}</span>
                <span className="tabular shrink-0 text-ink">{format(r.value)}</span>
              </div>
              <div className="relative mt-0.5 h-2.5">
                <span className="absolute inset-y-[-2px] left-1/2 w-px" style={{ background: CHROME.baseline }} />
                <span
                  className={pos ? "absolute inset-y-0 rounded-r" : "absolute inset-y-0 rounded-l"}
                  style={{
                    left: pos ? "50%" : `${50 - w}%`,
                    width: `${w}%`,
                    background: pos ? SERIES.up : SERIES.down,
                  }}
                />
              </div>
              {r.detail && <div className="mt-0.5 text-[10px] text-muted">{r.detail}</div>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const HEAT = ["#1a1a19", "#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"];

/** Sequential heatmap (one hue; darker = near zero on the dark surface). */
export function Heatmap({ rows, columns, counts }: { rows: string[]; columns: string[]; counts: number[][] }) {
  const max = Math.max(1, ...counts.flat());
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate text-[11px]" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th />
            {columns.map((c) => (
              <th key={c} scope="col" className="px-1 pb-1 text-center font-medium text-muted">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r}>
              <th scope="row" className="pr-2 text-right font-medium text-muted">
                {r}
              </th>
              {counts[i].map((v, j) => {
                const step = v === 0 ? 0 : 1 + Math.min(HEAT.length - 2, Math.floor((v / max) * (HEAT.length - 1)));
                const light = step >= 5;
                return (
                  <td
                    key={j}
                    title={`${r} · ${columns[j]}: ${v}`}
                    className="tabular h-7 rounded text-center"
                    style={{ background: HEAT[step], color: light ? "#0d0d0d" : CHROME.ink2 }}
                  >
                    {v}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function RadarProfile({
  data,
  height = 260,
  name,
}: {
  data: { axis: string; value: number }[];
  height?: number;
  name: string;
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="62%">
          <PolarGrid stroke={CHROME.grid} />
          <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
          <PolarAngleAxis dataKey="axis" tick={{ fill: CHROME.ink2, fontSize: 10 }} />
          <Tooltip content={makeTooltip((v) => v.toFixed(2))} />
          <Radar dataKey="value" name={name} stroke={SERIES.primary} strokeWidth={2} fill={SERIES.primary} fillOpacity={0.15} isAnimationActive={false} dot={{ r: 3, fill: SERIES.primary, stroke: CHROME.surface, strokeWidth: 2 }} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Contribution meters: fill = points contributed, track = maximum possible (weight x 100). */
export function Meters({
  rows,
}: {
  rows: { key: string; label: ReactNode; value: number; max: number; detail?: ReactNode }[];
}) {
  const scale = Math.max(1e-9, ...rows.map((r) => r.max));
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.key} className="text-xs">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-ink-2">{r.label}</span>
            <span className="tabular text-ink">
              {r.value.toFixed(1)} <span className="text-muted">/ {r.max.toFixed(0)} pts</span>
            </span>
          </div>
          <div className="relative mt-1 h-2.5">
            <span className="absolute inset-y-0 left-0 rounded" style={{ width: `${(r.max / scale) * 100}%`, background: "#0d366b" }} />
            <span className="absolute inset-y-0 left-0 rounded" style={{ width: `${(r.value / scale) * 100}%`, background: SERIES.primary, minWidth: r.value > 0 ? 2 : 0 }} />
          </div>
          {r.detail && <div className="mt-0.5 text-[10px] leading-snug text-muted">{r.detail}</div>}
        </li>
      ))}
    </ul>
  );
}
