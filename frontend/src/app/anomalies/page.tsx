"use client";

import { FilterBar } from "@/components/map/Controls";
import { MapCard } from "@/components/map/MapCard";
import { AlertIcon } from "@/components/ui/icons";
import { Card, DataTable, ErrorNote, Loading } from "@/components/ui/primitives";
import { useAnomalies, useMeta } from "@/lib/api";
import { fmtDate, fmtInt, fmtNum, fmtSignedPct } from "@/lib/format";
import { useUI } from "@/lib/store";
import type { SurgeItem } from "@/lib/types";

export default function AnomaliesPage() {
  const ui = useUI();
  const { data: meta } = useMeta();
  const { data, error } = useAnomalies(ui.crimeType);
  const label = (c: string) => meta?.crime_types.find((t) => t.code === c)?.label ?? c;
  return (
    <div className="space-y-4 p-5">
      <FilterBar showBand={false} showPeriod={false} />
      {error && <ErrorNote error={error} />}
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_440px]">
        <MapCard height={560} layer="anomalies" title="Surge map" />
        <Card
          title="Current surge alerts"
          subtitle={data ? `Detection week ${fmtDate(data.detection_window.start)} – ${fmtDate(data.as_of)} (all crime types)` : undefined}
        >
          {!data ? (
            <Loading />
          ) : (
            <>
              <DataTable<SurgeItem>
                rows={data.alerts}
                rowKey={(r) => r.zone_id + r.crime_type}
                empty="No surge alerts in the last complete week."
                onRowClick={(r) => ui.select({ zoneId: r.zone_id, crimeType: r.crime_type, band: "AUTO" })}
                columns={[
                  { key: "i", header: "", render: () => <AlertIcon size={12} /> },
                  { key: "z", header: "Zone", render: (r) => <span className="font-semibold text-ink">{r.zone_id}</span> },
                  { key: "c", header: "Crime type", render: (r) => label(r.crime_type) },
                  { key: "n", header: "Last week", render: (r) => fmtInt(r.surge_current_count), align: "right" },
                  { key: "m", header: "Typical", render: (r) => fmtNum(r.surge_baseline_mean, 2), align: "right" },
                  { key: "dev", header: "Change", render: (r) => fmtSignedPct(r.surge_deviation_pct), align: "right" },
                  { key: "zs", header: "z", render: (r) => fmtNum(r.surge_z, 1), align: "right" },
                ]}
              />
              <p className="mt-3 text-[11px] leading-snug text-muted">
                Method: {data.method}. The surge detector is a separate layer from the forecasting model; its capped z-score
                feeds the explainable risk score as signal X.
              </p>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
