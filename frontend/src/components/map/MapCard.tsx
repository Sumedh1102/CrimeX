"use client";

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
  return (
    <section className="flex h-full flex-col rounded-lg border bg-surface" style={{ borderColor: "var(--border)" }}>
      <header className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3">
        <h2 className="text-[13px] font-semibold text-ink">{title}</h2>
        {showControls && !fixedLayer && <LayerControls compact />}
      </header>
      <div className="flex-1 p-3">
        <MapView layer={layer} height={height}>
          {meta && (
            <div
              className="absolute bottom-3 left-3 z-10 w-[250px] rounded-md border bg-plane/90 px-3 py-2.5 backdrop-blur-sm"
              style={{ borderColor: "var(--border)" }}
            >
              <Legend layer={layer} meta={meta} metric={ui.riskMetric} textures={ui.textures} items={data.byZone} />
            </div>
          )}
        </MapView>
      </div>
    </section>
  );
}
