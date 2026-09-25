"use client";

import { FilterBar } from "@/components/map/Controls";
import { MapCard } from "@/components/map/MapCard";

export default function MapPage() {
  return (
    <div className="flex h-full flex-col gap-3 p-3 sm:p-5">
      <FilterBar />
      <div className="min-h-[380px] flex-1 sm:min-h-[520px]">
        <MapCard height="max(360px, calc(100dvh - 310px))" title="Map" />
      </div>
      <p className="text-[11px] text-muted">
        Click or tap a zone or marker for its summary, then open the full intelligence panel. Zones are 1.5 km grid cells over an approximate Mumbai study region (not
        an official boundary); station outlines are synthetic demonstration jurisdictions.
      </p>
    </div>
  );
}
