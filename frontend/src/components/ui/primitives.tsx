"use client";

import clsx from "clsx";
import type { ReactNode } from "react";
import { RISK_COLORS, STATE_BADGE, STATE_STYLE, WARN } from "@/lib/colors";
import type { Confidence, HotspotState, RiskBand } from "@/lib/types";
import { StateIcon } from "./icons";

export function Card({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section
      className={clsx("rounded-lg border bg-surface", className)}
      style={{ borderColor: "var(--border)" }}
    >
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 px-4 pt-3.5">
          <div className="min-w-0">
            {title && <h2 className="text-[13px] font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={clsx("px-4 pb-4 pt-3", bodyClassName)}>{children}</div>
    </section>
  );
}

/** A colored swatch beside ink text: identity comes from the mark, not the text color. */
export function Swatch({ color, className }: { color: string | null; className?: string }) {
  return (
    <span
      aria-hidden
      className={clsx("inline-block h-2.5 w-2.5 shrink-0 rounded-[3px]", className)}
      style={{
        background: color ?? "transparent",
        border: color ? undefined : "1px solid var(--border-strong)",
      }}
    />
  );
}

export function RiskBadge({ band, value }: { band: RiskBand; value?: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-ink-2">
      <Swatch color={RISK_COLORS[band]} />
      {value !== undefined && <span className="tabular font-semibold text-ink">{value.toFixed(1)}</span>}
      <span>{band}</span>
    </span>
  );
}

export function StateBadge({ state }: { state: HotspotState }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-ink-2">
      <StateIcon state={state} color={STATE_BADGE[state]} size={12} />
      <span>{STATE_STYLE[state].label}</span>
    </span>
  );
}

const CONF_BARS: Record<Confidence, number> = { LOW: 1, MEDIUM: 2, HIGH: 3 };

/** Evidence strength shown as signal bars + label (not a status color). */
export function ConfidencePill({ level }: { level: Confidence }) {
  const n = CONF_BARS[level];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-2" title="Evidence strength">
      <span aria-hidden className="flex items-end gap-[2px]">
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            className="w-[3px] rounded-sm"
            style={{ height: 4 + i * 3, background: i <= n ? "#c3c2b7" : "#383835" }}
          />
        ))}
      </span>
      {level.charAt(0) + level.slice(1).toLowerCase()} confidence
    </span>
  );
}

export function SyntheticBadge({ label }: { label: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-semibold tracking-wide text-ink"
      style={{ borderColor: "rgba(250,178,25,0.45)", background: "rgba(250,178,25,0.08)" }}
    >
      <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden>
        <path d="M8 1.5 15 14H1L8 1.5Z" fill="none" stroke={WARN} strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M8 6v4" stroke={WARN} strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="8" cy="12" r="0.9" fill={WARN} />
      </svg>
      {label}
    </span>
  );
}

export function Select<T extends string>({
  label,
  value,
  onChange,
  options,
  className,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  className?: string;
}) {
  return (
    <label className={clsx("flex flex-col gap-1", className)}>
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="h-8 rounded-md border bg-surface px-2 text-[13px] text-ink outline-none hover:bg-surface-2"
        style={{ borderColor: "var(--border)" }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-surface">
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
  size = "md",
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; title?: string }[];
  ariaLabel: string;
  size?: "sm" | "md";
}) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="inline-flex flex-wrap rounded-md border bg-plane p-0.5"
      style={{ borderColor: "var(--border)" }}
    >
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={clsx(
            "rounded-[5px] font-medium transition-colors",
            size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
            value === o.value ? "bg-surface-3 text-ink" : "text-muted hover:text-ink-2",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Kpi({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: number | string;
  hint?: string;
  icon?: ReactNode;
}) {
  return (
    <div
      className="rounded-lg border bg-surface px-4 py-3"
      style={{ borderColor: "var(--border)" }}
      title={hint}
    >
      <div className="flex items-center gap-2 text-xs text-ink-2">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-1.5 text-[26px] font-semibold leading-none text-ink">{value}</div>
      {hint && <p className="mt-2 line-clamp-2 text-[11px] leading-snug text-muted">{hint}</p>}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="py-8 text-center text-xs text-muted">{label}…</div>;
}

export function ErrorNote({ error }: { error: Error }) {
  return (
    <div className="rounded-md border px-3 py-2 text-xs text-ink-2" style={{ borderColor: "rgba(208,59,59,0.5)" }}>
      <span className="font-semibold text-ink">Could not load data.</span> {error.message}
      {error.message.includes("make pipeline") ? "" : " Is the API running on port 8000?"}
    </div>
  );
}

export function Dl({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd className="min-w-0 break-words text-ink-2">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function DataTable<T>({
  columns,
  rows,
  onRowClick,
  maxHeight,
  empty = "No rows",
  rowKey,
}: {
  columns: { key: string; header: string; render: (row: T) => ReactNode; align?: "left" | "right" }[];
  rows: T[];
  onRowClick?: (row: T) => void;
  maxHeight?: number;
  empty?: string;
  rowKey: (row: T, i: number) => string;
}) {
  return (
    <div className="overflow-auto" style={{ maxHeight }}>
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 z-10 bg-surface">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={clsx(
                  "border-b px-2 py-1.5 font-medium text-muted",
                  c.align === "right" ? "text-right" : "text-left",
                )}
                style={{ borderColor: "var(--border)" }}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-2 py-6 text-center text-muted">
                {empty}
              </td>
            </tr>
          )}
          {rows.map((r, i) => (
            <tr
              key={rowKey(r, i)}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              onKeyDown={
                onRowClick
                  ? (e) => {
                      if (e.key === "Enter") onRowClick(r);
                    }
                  : undefined
              }
              tabIndex={onRowClick ? 0 : undefined}
              className={clsx("border-b", onRowClick && "cursor-pointer hover:bg-surface-2")}
              style={{ borderColor: "var(--border)" }}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={clsx("px-2 py-1.5 text-ink-2", c.align === "right" && "tabular text-right")}
                >
                  {c.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
