"use client";

import { useState, type ReactNode } from "react";
import { Icon } from "@/components/ui/icons";
import { Card, DataTable } from "@/components/ui/primitives";

export interface TableSpec {
  columns: { key: string; header: string; align?: "left" | "right" }[];
  rows: Record<string, ReactNode>[];
}

/** Chart container with a table-view twin (the accessible equivalent of every chart). */
export function ChartCard({
  title,
  subtitle,
  table,
  children,
  className,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  table?: TableSpec;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <Card
      title={title}
      subtitle={subtitle}
      className={className}
      actions={
        <>
          {actions}
          {table && (
            <button
              type="button"
              onClick={() => setAsTable((v) => !v)}
              aria-pressed={asTable}
              title={asTable ? "Show chart" : "Show table"}
              className="rounded p-1 text-muted hover:bg-surface-2 hover:text-ink"
            >
              <Icon name={asTable ? "chart" : "table"} size={15} />
            </button>
          )}
        </>
      }
    >
      {asTable && table ? (
        <DataTable<Record<string, ReactNode>>
          maxHeight={260}
          rowKey={(_, i) => String(i)}
          rows={table.rows}
          columns={table.columns.map((c) => ({ key: c.key, header: c.header, align: c.align, render: (r) => r[c.key] }))}
        />
      ) : (
        children
      )}
    </Card>
  );
}
