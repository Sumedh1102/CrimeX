"use client";

import { Card, DataTable, Dl, ErrorNote, Loading, SyntheticBadge } from "@/components/ui/primitives";
import { useDataQuality } from "@/lib/api";
import { fmtDateTime, fmtInt } from "@/lib/format";

export default function DataQualityPage() {
  const { data, error } = useDataQuality();
  if (error) return <div className="p-5"><ErrorNote error={error} /></div>;
  if (!data) return <Loading />;
  const r = data.report;
  const ds = data.dataset;
  return (
    <div className="space-y-4 p-5">
      <Card title="Data quality monitor" subtitle={data.note} actions={ds.is_synthetic ? <SyntheticBadge label={ds.data_label} /> : null}>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            ["Records received", fmtInt(r.rows_in)],
            ["Records accepted", fmtInt(r.rows_out)],
            ["Records rejected", fmtInt(r.rows_rejected)],
            ["Acceptance rate", `${((100 * r.rows_out) / Math.max(1, r.rows_in)).toFixed(2)}%`],
          ].map(([k, v]) => (
            <div key={k} className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)" }}>
              <p className="text-[11px] text-ink-2">{k}</p>
              <p className="mt-1 text-xl font-semibold text-ink">{v}</p>
            </div>
          ))}
        </div>
      </Card>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card title="Checks" subtitle="Each rejected record is attributed to its first failing check">
          <DataTable
            rows={r.checks}
            rowKey={(c) => c.id}
            columns={[
              { key: "l", header: "Check", render: (c) => c.label },
              { key: "n", header: "Records with issue", render: (c) => fmtInt(c.rows_with_issue), align: "right" },
              { key: "p", header: "Rate", render: (c) => `${(c.rate * 100).toFixed(2)}%`, align: "right" },
              { key: "a", header: "Action", render: (c) => c.action },
            ]}
          />
        </Card>
        <Card title="Dataset">
          <Dl
            items={[
              ["Version", ds.dataset_version],
              ["Created", `${fmtDateTime(ds.created_at)} UTC`],
              ["Sources", ds.sources.join(", ")],
              ["Records", fmtInt(ds.rows)],
              ["Period", `${fmtDateTime(ds.timestamp_range.min)} → ${fmtDateTime(ds.timestamp_range.max)}`],
              ["Zones", `${ds.n_zones} × ${ds.cell_size_m / 1000} km cells`],
              ["Crime types", ds.crime_types.join(", ")],
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
