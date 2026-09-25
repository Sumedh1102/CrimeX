"use client";

import Link from "next/link";
import { Card, ErrorNote, Loading } from "@/components/ui/primitives";
import { useCrimeTypes } from "@/lib/api";

export default function CrimeTypesPage() {
  const { data, error } = useCrimeTypes();
  return (
    <div className="space-y-4 p-5">
      {error && <ErrorNote error={error} />}
      <Card
        title="Spatially modelled crime heads"
        subtitle="Official IPC heads from the Brihan Mumbai statement that are place-based with enough volume to model per zone"
      >
        {!data ? (
          <Loading />
        ) : (
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {data.modelled.map((c) => (
              <Link
                key={c.code}
                href={`/crime-types/${c.code}`}
                className="rounded-md border px-3 py-2.5 hover:bg-surface-2"
                style={{ borderColor: "var(--border)" }}
              >
                <p className="text-sm font-semibold text-ink">{c.label}</p>
                <p className="text-[11px] text-muted">
                  Official head: “{c.label_official}” · {c.section}
                  {c.allowed_hours ? ` · hours ${c.allowed_hours[0]}:00–${c.allowed_hours[1]}:00 by definition` : ""}
                </p>
              </Link>
            ))}
          </div>
        )}
      </Card>
      <Card title="Official-statistics only" subtitle="Heads kept out of spatial modelling, with the reason">
        {!data ? (
          <Loading />
        ) : (
          <ul className="divide-y text-xs" style={{ borderColor: "var(--border)" }}>
            {data.not_modelled.map((c) => (
              <li key={c.code} className="flex flex-col gap-0.5 py-2 md:flex-row md:gap-4" style={{ borderColor: "var(--border)" }}>
                <span className="w-60 shrink-0 font-medium text-ink">{c.label}</span>
                <span className="text-ink-2">{c.reason}</span>
              </li>
            ))}
            <li className="py-2 text-muted">
              Crime Against Women, NDPS, brothel, EOW and cyber-crime sections are shown under Official statistics.
            </li>
          </ul>
        )}
      </Card>
    </div>
  );
}
