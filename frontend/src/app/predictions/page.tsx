"use client";

import { useMemo } from "react";
import { FilterBar } from "@/components/map/Controls";
import {
  Card,
  ConfidencePill,
  DataTable,
  ErrorNote,
  Loading,
  RiskBadge,
  StateBadge,
  Swatch,
} from "@/components/ui/primitives";
import { useMeta, useRiskLayer, useZones } from "@/lib/api";
import { RISK_COLORS, RISK_ORDER } from "@/lib/colors";
import { fmtNum, fmtPct, fmtWindow } from "@/lib/format";
import { useUI } from "@/lib/store";
import type { RiskItem } from "@/lib/types";

export default function PredictionsPage() {
  const ui = useUI();
  const { data: meta } = useMeta();
  const { data: zones } = useZones();
  const { data, error } = useRiskLayer(ui.crimeType, ui.band);
  const station = useMemo(
    () => new Map(zones?.features.map((f) => [f.properties.zone_id, f.properties.station_name ?? "–"]) ?? []),
    [zones],
  );
  const rows = useMemo(() => {
    let items = data?.items ?? [];
    if (ui.stationId && zones) {
      const inStation = new Set(zones.features.filter((f) => f.properties.station_id === ui.stationId).map((f) => f.properties.zone_id));
      items = items.filter((i) => inStation.has(i.zone_id));
    }
    return [...items].sort((a, b) => b.final_risk - a.final_risk);
  }, [data, ui.stationId, zones]);
  const label = (c: string) => meta?.crime_types.find((t) => t.code === c)?.label ?? c;
  const bandLabel = (b: string) => meta?.bands.find((t) => t.code === b)?.label ?? b;

  return (
    <div className="space-y-4 p-3 sm:p-5">
      <FilterBar showPeriod={false} />
      {error && <ErrorNote error={error} />}
      <Card
        title="Zone risk ranking"
        subtitle={
          data
            ? `Forecast window ${fmtWindow(data.window.start, data.window.end)} · ${rows.length} zones · ${data.aggregation ?? "one crime type and band"}`
            : undefined
        }
        actions={
          <span className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
            {RISK_ORDER.map((b) => (
              <span key={b} className="tabular inline-flex items-center gap-1">
                <Swatch color={RISK_COLORS[b]} />
                {b}: {rows.filter((r) => r.risk_band === b).length}
              </span>
            ))}
          </span>
        }
      >
        {!data ? (
          <Loading />
        ) : (
          <DataTable<RiskItem>
            rows={rows}
            maxHeight={620}
            rowKey={(r) => r.zone_id}
            onRowClick={(r) => ui.select({ zoneId: r.zone_id, crimeType: r.crime_type, band: r.band })}
            columns={[
              { key: "rank", header: "#", render: (r) => rows.indexOf(r) + 1, align: "right" },
              { key: "zone", header: "Zone", render: (r) => <span className="font-semibold text-ink">{r.zone_id}</span> },
              { key: "station", header: "Station", render: (r) => station.get(r.zone_id) },
              { key: "crime", header: "Crime type", render: (r) => label(r.crime_type) },
              { key: "band", header: "Band", render: (r) => bandLabel(r.band) },
              { key: "final", header: "Blended score", render: (r) => <RiskBadge band={r.risk_band} value={r.final_risk} /> },
              { key: "crs", header: "CRS", render: (r) => fmtNum(r.crs), align: "right" },
              { key: "p", header: "Probability", render: (r) => fmtPct(r.probability), align: "right" },
              { key: "conf", header: "Confidence", render: (r) => <ConfidencePill level={r.confidence} /> },
              { key: "exp", header: "Expected", render: (r) => fmtNum(r.expected_count, 2), align: "right" },
              { key: "state", header: "Hotspot state", render: (r) => <StateBadge state={r.hotspot_state} /> },
            ]}
          />
        )}
        <p className="mt-3 text-[11px] leading-snug text-muted">
          Blended and CRS scores are 0–100 indicators, not probabilities. Probability is the calibrated chance of at least
          one reported incident of the crime type in the zone during the band on any day of the window. Click a row for its
          explanation.
        </p>
      </Card>
    </div>
  );
}
