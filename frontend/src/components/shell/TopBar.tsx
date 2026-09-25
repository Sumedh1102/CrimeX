"use client";

import { SyntheticBadge } from "@/components/ui/primitives";
import { useMeta } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtWindow } from "@/lib/format";

export function TopBar() {
  const { data: meta, error } = useMeta();
  return (
    <header
      className="flex h-14 shrink-0 items-center gap-4 border-b bg-plane px-5"
      style={{ borderColor: "var(--border)" }}
    >
      <div className="min-w-0">
        <h1 className="text-[15px] font-semibold uppercase tracking-[0.08em] text-ink">
          AI Crime Intelligence
        </h1>
        <p className="truncate text-[11px] text-muted">
          Brihan Mumbai · {meta?.region.name ?? "study region"} · zone-level decision support
        </p>
      </div>
      <div className="ml-auto flex items-center gap-3">
        {meta?.is_synthetic && <SyntheticBadge label={meta.data_label} />}
        {meta && (
          <div className="hidden text-right text-[11px] leading-tight lg:block">
            <div className="text-ink-2">
              Forecast window{" "}
              <span className="font-semibold text-ink">
                {fmtWindow(meta.forecast_window.start, meta.forecast_window.end)}
              </span>
            </div>
            <div className="text-muted">as of {fmtDate(meta.as_of)}</div>
          </div>
        )}
        {meta && (
          <details className="relative">
            <summary
              className="cursor-pointer list-none rounded border px-2 py-1 text-[11px] text-ink-2 hover:bg-surface"
              style={{ borderColor: "var(--border)" }}
            >
              Model versions
            </summary>
            <div
              className="absolute right-0 z-50 mt-1 w-[340px] rounded-md border bg-surface p-3 text-[11px] shadow-xl"
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

export function LimitationFooter() {
  const { data: meta } = useMeta();
  return (
    <footer
      className="shrink-0 border-t bg-plane px-5 py-2 text-[11px] leading-snug text-muted"
      style={{ borderColor: "var(--border)" }}
    >
      {meta?.limitation_statement ??
        "Predictions represent statistical patterns in historical reported incident data and are intended for analytical decision support. They are not guarantees of future criminal activity."}
      {meta?.is_synthetic && (
        <span className="text-ink-2">
          {" "}
          Incident-level data shown here is synthetic demonstration data anchored to official
          city-level counts; it is not real police data.
        </span>
      )}
    </footer>
  );
}
