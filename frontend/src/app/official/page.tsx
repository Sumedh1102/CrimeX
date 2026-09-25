"use client";

import { useState } from "react";
import { ChartCard } from "@/components/charts/ChartCard";
import { DivergingBars } from "@/components/charts/charts";
import { Card, DataTable, ErrorNote, Loading, Segmented } from "@/components/ui/primitives";
import { useOfficial } from "@/lib/api";
import { fmtDate, fmtInt } from "@/lib/format";
import type { OfficialHead } from "@/lib/types";

const v = (h: OfficialHead, period: string, metric: string) => h.values[period]?.[metric] ?? null;
const cell = (x: number | null) => (x === null ? <span className="text-muted">blank</span> : fmtInt(x));

export default function OfficialPage() {
  const { data, error } = useOfficial();
  const [section, setSection] = useState("IPC");
  if (error) return <div className="p-5"><ErrorNote error={error} /></div>;
  if (!data) return <Loading />;
  const sec = data.sections.find((s) => s.id === section)!;
  const per = data.periods;
  const ipc = data.sections.find((s) => s.id === "IPC")!;
  const yoy = ipc.heads
    .filter((h) => !h.is_aggregate && h.code !== "OTHER_IPC")
    .map((h) => ({ h, cy: v(h, "CY", "registered"), py: v(h, "PY", "registered") }))
    .filter((r) => r.cy !== null && r.py && r.py > 0)
    .map((r) => ({ key: r.h.code, label: r.h.label, value: ((r.cy! - r.py!) / r.py!) * 100, detail: `${fmtInt(r.py)} → ${fmtInt(r.cy)}${r.h.spatially_modelled ? " · modelled" : ""}` }))
    .sort((a, b) => b.value - a.value);

  const regDetCols = (withDiff: boolean) => [
    { key: "sr", header: "Sr", render: (h: OfficialHead) => h.sr ?? "" },
    { key: "l", header: "Head (as printed)", render: (h: OfficialHead) => <span className={h.is_aggregate ? "font-semibold text-ink" : h.parent ? "pl-3" : ""}>{h.label_official}</span> },
    { key: "cm", header: `${per.CM.label} R / D`, render: (h: OfficialHead) => <>{cell(v(h, "CM", "registered"))} / {cell(v(h, "CM", "detected"))}</>, align: "right" as const },
    { key: "pm", header: `${per.PM.label} R / D`, render: (h: OfficialHead) => <>{cell(v(h, "PM", "registered"))} / {cell(v(h, "PM", "detected"))}</>, align: "right" as const },
    { key: "cy", header: "Jan–Aug 2026 R / D (%)", render: (h: OfficialHead) => <>{cell(v(h, "CY", "registered"))} / {cell(v(h, "CY", "detected"))} ({v(h, "CY", "detection_pct") ?? "–"})</>, align: "right" as const },
    { key: "py", header: "Jan–Aug 2025 R / D (%)", render: (h: OfficialHead) => <>{cell(v(h, "PY", "registered"))} / {cell(v(h, "PY", "detected"))} ({v(h, "PY", "detection_pct") ?? "–"})</>, align: "right" as const },
    ...(withDiff ? [{ key: "diff", header: "Diff (reg)", render: (h: OfficialHead) => cell(v(h, "CY_VS_PY", "difference_registered")), align: "right" as const }] : []),
  ];

  const columns =
    section === "IPC" || section === "CAW"
      ? regDetCols(section === "IPC")
      : section === "NDPS"
        ? [
            { key: "l", header: "Drug", render: (h: OfficialHead) => <span className={h.is_aggregate ? "font-semibold text-ink" : ""}>{h.label_official}</span> },
            ...["cases", "persons_arrested", "quantity_kg", "quantity_tablets", "quantity_litres", "value"].map((m) => ({
              key: m,
              header: m.replace("quantity_", "qty ").replace("_", " "),
              render: (h: OfficialHead) => { const x = v(h, "CM", m); return x === null ? <span className="text-muted">blank</span> : x.toLocaleString("en-IN"); },
              align: "right" as const,
            })),
          ]
        : section === "BROTHELS"
          ? [
              { key: "l", header: "Measure", render: (h: OfficialHead) => h.label },
              ...["CM", "CY", "PY"].map((p) => ({ key: p, header: per[p].label, render: (h: OfficialHead) => cell(v(h, p, "count")), align: "right" as const })),
            ]
          : section === "EOW"
            ? [
                { key: "l", header: "Measure", render: (h: OfficialHead) => h.label },
                ...Object.entries({ "CM|registered": "Aug R", "CM|detected": "Aug D", "PM|registered": "Jul R", "CY|registered": "Jan–Aug 26 R", "CY|detected": "Jan–Aug 26 D", "PY|registered": "Jan–Aug 25 R", "CY_VS_PY|difference_registered_as_printed": "Diff. in Reg. (printed)", "CY|property_involved_rs": "Property (Rs.)" }).map(([k, label]) => {
                  const [p, m] = k.split("|");
                  return { key: k, header: label, render: (h: OfficialHead) => { const x = v(h, p, m); return x === null ? "–" : x.toLocaleString("en-IN"); }, align: "right" as const };
                }),
              ]
            : [
                { key: "sr", header: "Sr", render: (h: OfficialHead) => h.sr ?? "" },
                { key: "l", header: "Head (as printed)", render: (h: OfficialHead) => <span className={h.parent ? "pl-3" : h.is_aggregate ? "font-semibold text-ink" : ""}>{h.label_official}</span> },
                ...["registered", "detected", "pa"].map((m) => ({ key: m, header: m === "pa" ? "PA" : m, render: (h: OfficialHead) => cell(v(h, "CM", m)), align: "right" as const })),
              ];

  return (
    <div className="space-y-4 p-5">
      <Card
        title="Official statistics: Brihan Mumbai monthly statement"
        subtitle={`${data.report.source_file} · statement month ${data.report.statement_month} · ${data.note}`}
      >
        <div className="grid grid-cols-1 gap-4 text-xs lg:grid-cols-3">
          <div className="space-y-1 text-ink-2">
            {Object.entries(per).map(([k, p]) => (
              <p key={k}>
                <span className="font-semibold text-ink">{p.label}</span>: {fmtDate(p.start)} – {fmtDate(p.end)}
                {p.law_label_as_printed ? ` (headed “${p.law_label_as_printed}”)` : ""}
              </p>
            ))}
          </div>
          <div className="text-ink-2">
            <p className="font-semibold text-ink">Consistency checks</p>
            <p>
              {data.checks_summary.passed} of {data.checks_summary.total} arithmetic checks pass;{" "}
              {data.checks_summary.discrepancies} discrepancies in the source are flagged below and kept as printed.
            </p>
          </div>
          <div className="text-ink-2">
            <p className="font-semibold text-ink">What this data cannot do</p>
            <p>City-level aggregates only: no incidents, timestamps, coordinates or station breakdown, so no spatial model is trained on it.</p>
          </div>
        </div>
      </Card>

      <Segmented
        ariaLabel="Section"
        value={section}
        onChange={setSection}
        options={data.sections.map((s) => ({ value: s.id, label: `${s.id === "CAW" ? "Crime against women" : s.id === "IPC" ? "IPC crime" : s.id === "CYBER" ? "Cyber crime" : s.id === "BROTHELS" ? "Brothels" : s.id} (p.${s.page})` }))}
      />
      <Card title={sec.title} subtitle="Values exactly as printed. R = registered, D = detected; “blank” = empty cell in the source.">
        <DataTable rows={sec.heads} rowKey={(h) => h.code} maxHeight={560} columns={columns} />
      </Card>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <ChartCard
          title="Year-to-date change in registrations by IPC head"
          subtitle="Jan–Aug 2026 vs Jan–Aug 2025 (Other IPC and totals excluded)"
          table={{
            columns: [{ key: "h", header: "Head" }, { key: "c", header: "Change", align: "right" }, { key: "d", header: "2025 → 2026" }],
            rows: yoy.map((r) => ({ h: r.label, c: `${r.value > 0 ? "+" : ""}${r.value.toFixed(0)}%`, d: r.detail })),
          }}
        >
          <DivergingBars rows={yoy} format={(x) => `${x > 0 ? "+" : ""}${x.toFixed(0)}%`} posLabel="increase" negLabel="decrease" />
        </ChartCard>
        <Card title="Discrepancies found in the source" subtitle="Computed vs printed; nothing was corrected">
          <DataTable
            rows={data.discrepancies}
            rowKey={(d) => d.id}
            maxHeight={420}
            columns={[
              { key: "d", header: "Check", render: (d) => d.description },
              { key: "e", header: "Computed", render: (d) => d.expected?.toLocaleString("en-IN") ?? "–", align: "right" },
              { key: "o", header: "Printed", render: (d) => d.observed?.toLocaleString("en-IN") ?? "–", align: "right" },
            ]}
          />
          <ul className="mt-3 space-y-1 text-[11px] leading-snug text-muted">
            {data.source_notes.map((n) => (
              <li key={n.id}>• {n.description}</li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
