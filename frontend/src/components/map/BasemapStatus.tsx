"use client";

import { useState } from "react";
import { BASEMAP_OPTIONS, type BasemapChoice } from "@/lib/basemap";
import { useUI } from "@/lib/store";

export type BasemapState =
  | { phase: "probing" }
  | { phase: "live"; provider: string; failures: string[] }
  | { phase: "offline"; provider: string; reason: string; failures: string[] };

/** Basemap picker plus a plain statement of what the map is currently drawn on. */
export function BasemapStatus({ state, onRetry }: { state: BasemapState; onRetry: () => void }) {
  const basemap = useUI((s) => s.basemap);
  const set = useUI((s) => s.set);
  const [open, setOpen] = useState(false);
  if (state.phase === "probing") return null;
  const offline = state.phase === "offline";
  const chose = offline && state.reason === "selected";
  const details = state.failures.length ? state.failures.join("\n") : undefined;

  return (
    <div
      className="pointer-events-auto max-w-full rounded-md border bg-plane/90 text-[11px] text-ink-2 backdrop-blur-sm"
      style={{ borderColor: "var(--border)" }}
    >
      <div className="flex items-center gap-2 px-2 py-1">
        {offline && !chose ? (
          <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden className="shrink-0">
            <path d="M2 5.5a9 9 0 0 1 12 0M4.3 8.2a5.6 5.6 0 0 1 7.4 0M6.6 10.9a2.3 2.3 0 0 1 2.8 0" fill="none" stroke="#c3c2b7" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M2 2l12 12" stroke="#c3c2b7" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden className="shrink-0">
            <path d="M1.5 3.5 5.5 2l5 1.5 4-1.5v10.5l-4 1.5-5-1.5-4 1.5z M5.5 2v10.5 M10.5 3.5V14" fill="none" stroke="#c3c2b7" strokeWidth="1.3" strokeLinejoin="round" />
          </svg>
        )}
        <span className="min-w-0 truncate" title={details}>
          {offline && !chose ? (
            <>
              <span className="font-semibold text-ink">Street map unavailable</span>
              <span className="hidden sm:inline"> · offline reference map</span>
            </>
          ) : (
            <>
              <span className="hidden sm:inline">Basemap: </span>
              <span className="text-ink">{state.provider}</span>
            </>
          )}
        </span>
        {offline && !chose && (
          <button
            type="button"
            onClick={onRetry}
            className="shrink-0 rounded border px-1.5 py-0.5 text-[10px] text-ink hover:bg-surface-2"
            style={{ borderColor: "var(--border-strong)" }}
          >
            Retry
          </button>
        )}
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label="Basemap options"
          className="shrink-0 rounded px-1 text-muted hover:bg-surface-2 hover:text-ink"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
            <path d={open ? "M2 6.5 5 3.5l3 3" : "M2 3.5 5 6.5l3-3"} fill="none" stroke="currentColor" strokeWidth="1.4" />
          </svg>
        </button>
      </div>
      {open && (
        <div className="border-t px-2 pb-2 pt-1.5" style={{ borderColor: "var(--border)" }}>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-wide text-muted">Basemap</span>
            <select
              value={basemap}
              onChange={(e) => set({ basemap: e.target.value as BasemapChoice })}
              className="h-7 rounded border bg-surface px-1.5 text-[11px] text-ink"
              style={{ borderColor: "var(--border)" }}
            >
              {BASEMAP_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          {offline && !chose && (
            <p className="mt-1.5 max-w-[260px] leading-snug text-muted">
              No tile server answered ({state.reason}). Showing the bundled OpenStreetMap coastline, creeks and lakes
              with approximate locality names. Zones, scores and every layer work as normal.
            </p>
          )}
          {details && (
            <details className="mt-1 text-[10px] text-muted">
              <summary className="cursor-pointer">Provider checks</summary>
              <pre className="mt-1 max-w-[260px] whitespace-pre-wrap break-words font-sans">{details}</pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
