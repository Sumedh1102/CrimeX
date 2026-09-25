"use client";

import { useState } from "react";
import { Icon } from "@/components/ui/icons";
import { SyntheticBadge } from "@/components/ui/primitives";
import { useMeta } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtWindow } from "@/lib/format";
import { useUI } from "@/lib/store";

export function TopBar() {
  const { data: meta, error } = useMeta();
  const navOpen = useUI((s) => s.navOpen);
  const set = useUI((s) => s.set);
  return (
    <header
      className="flex min-h-14 shrink-0 flex-wrap items-center gap-x-3 gap-y-1.5 border-b bg-plane px-3 py-2 sm:px-5"
      style={{ borderColor: "var(--border)" }}
    >
      <button
        type="button"
        onClick={() => set({ navOpen: !navOpen })}
        aria-label="Open navigation"
        aria-expanded={navOpen}
        aria-controls="mobile-nav"
        className="-ml-1 rounded p-1.5 text-ink-2 hover:bg-surface hover:text-ink lg:hidden"
      >
        <Icon name="menu" size={18} />
      </button>
      <div className="min-w-0 flex-1 sm:flex-none">
        <h1 className="truncate text-[14px] font-semibold uppercase tracking-[0.08em] text-ink sm:text-[15px]">
          AI Crime Intelligence
        </h1>
        <p className="truncate text-[11px] text-muted">
          Brihan Mumbai · {meta?.region.name ?? "study region"}
          <span className="hidden sm:inline"> · zone-level decision support</span>
        </p>
      </div>
      <div className="flex w-full items-center gap-2 sm:ml-auto sm:w-auto sm:gap-3">
        {/* Always visible, at every width: this is demonstration data. */}
        {meta?.is_synthetic && <SyntheticBadge label={meta.data_label} />}
        {meta && (
          <div className="ml-auto text-right text-[11px] leading-tight sm:ml-0">
            <div className="text-ink-2">
              <span className="hidden md:inline">Forecast window </span>
              <span className="font-semibold text-ink">
                {fmtWindow(meta.forecast_window.start, meta.forecast_window.end)}
              </span>
            </div>
            <div className="hidden text-muted md:block">as of {fmtDate(meta.as_of)}</div>
          </div>
        )}
        {meta && (
          <details className="relative hidden sm:block">
            <summary
              className="cursor-pointer list-none rounded border px-2 py-1 text-[11px] text-ink-2 hover:bg-surface"
              style={{ borderColor: "var(--border)" }}
            >
              Model versions
            </summary>
            <div
              className="absolute right-0 z-50 mt-1 w-[340px] max-w-[calc(100vw-24px)] rounded-md border bg-surface p-3 text-[11px] shadow-xl"
              style={{ borderColor: "var(--border)" }}
            >
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                <dt className="text-muted">Model</dt>
                <dd className="break-all text-ink-2">{meta.versions.model_version}</dd>
                <dt className="text-muted">Training data</dt>
                <dd className="break-all text-ink-2">{meta.versions.training_dataset_version}</dd>
                <dt className="text-muted">Input data</dt>
                <dd className="break-all text-ink-2">{meta.versions.input_dataset_version}</dd>
                <dt className="text-muted">Features</dt>
                <dd className="break-all text-ink-2">{meta.versions.feature_version}</dd>
                <dt className="text-muted">Generated</dt>
                <dd className="text-ink-2">{fmtDateTime(meta.versions.generated_at)} UTC</dd>
              </dl>
            </div>
          </details>
        )}
        {error && <span className="text-[11px] text-muted">API unavailable</span>}
      </div>
    </header>
  );
}

const DEFAULT_LIMITATION =
  "Predictions represent statistical patterns in historical reported incident data and are intended for analytical decision support. They are not guarantees of future criminal activity.";

export function LimitationFooter() {
  const { data: meta } = useMeta();
  const [expanded, setExpanded] = useState(false);
  const synthetic = meta?.is_synthetic ?? true;
  const full = (
    <>
      {meta?.limitation_statement ?? DEFAULT_LIMITATION}
      {synthetic && (
        <span className="text-ink-2">
          {" "}
          Incident-level data shown here is synthetic demonstration data anchored to official city-level counts; it is
          not real police data, and these are not verified crime forecasts.
        </span>
      )}
    </>
  );
  return (
    <footer
      className="shrink-0 border-t bg-plane px-3 py-2 text-[11px] leading-snug text-muted sm:px-5"
      style={{ borderColor: "var(--border)" }}
    >
      {/* Phones: a short, always-visible statement with the full text one tap away. */}
      <div className="sm:hidden">
        {expanded ? (
          full
        ) : (
          <span className="text-ink-2">
            {synthetic ? "Synthetic demonstration data. " : ""}Statistical patterns for decision support, not
            guarantees or verified crime forecasts.
          </span>
        )}{" "}
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
          className="font-semibold text-ink underline decoration-dotted underline-offset-2"
        >
          {expanded ? "Less" : "More"}
        </button>
      </div>
      <div className="hidden sm:block">{full}</div>
    </footer>
  );
}
