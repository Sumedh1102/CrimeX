"use client";

import { useState } from "react";
import { useMeta } from "@/lib/api";
import { useUI } from "@/lib/store";
import type { LayerKey } from "@/lib/types";
import { LayerControls } from "./Controls";
import { Legend } from "./Legend";
import MapView from "./MapView";
import { useLayerData } from "./useLayerData";

export function MapCard({
  height = 540,
  layer: fixedLayer,
  title = "Operational map",
  showControls = true,
}: {
  height?: number | string;
  layer?: LayerKey;
  title?: string;
  showControls?: boolean;
}) {
  const ui = useUI();
  const layer = fixedLayer ?? ui.layer;
  const { data: meta } = useMeta();
  const data = useLayerData(layer);
  const [legendOpen, setLegendOpen] = useState(true);
  const legend = meta && (
    <Legend layer={layer} meta={meta} metric={ui.riskMetric} textures={ui.textures} items={data.byZone} />
  );
  // Phones get a shorter map so the legend below it and the page stay reachable.
  const mapHeight = typeof height === "number" ? `clamp(340px, 62vh, ${height}px)` : height;
  return (
    <section className="flex h-full min-w-0 flex-col rounded-lg border bg-surface" style={{ borderColor: "var(--border)" }}>
      <header className="flex flex-wrap items-center justify-between gap-2 px-3 pt-3 sm:px-4">
        <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
        {showControls && !fixedLayer && <LayerControls compact />}
      </header>
      <div className="flex-1 p-2 sm:p-3">
        <MapView layer={layer} height={mapHeight}>
          {legend && (
            <div
              className="absolute bottom-2 left-2 z-10 hidden w-[256px] rounded-md border bg-plane/90 backdrop-blur-sm md:block"
              style={{ borderColor: "var(--border)" }}
            >
              <button
                type="button"
                onClick={() => setLegendOpen((o) => !o)}
                aria-expanded={legendOpen}
                className="flex w-full items-center justify-between px-3 py-1.5 text-[11px] font-semibold text-ink-2 hover:text-ink"
              >
                Legend
                <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
                  <path d={legendOpen ? "M2 3.5 5 6.5l3-3" : "M2 6.5 5 3.5l3 3"} fill="none" stroke="currentColor" strokeWidth="1.4" />
                </svg>
              </button>
              {legendOpen && <div className="px-3 pb-2.5">{legend}</div>}
            </div>
          )}
        </MapView>
        {legend && (
          <div className="mt-2 rounded-md border bg-plane px-3 py-2.5 md:hidden" style={{ borderColor: "var(--border)" }}>
            {legend}
          </div>
        )}
      </div>
    </section>
  );
}
