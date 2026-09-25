"use client";

import { FilterBar } from "@/components/map/Controls";
import { MapCard } from "@/components/map/MapCard";

export default function MapPage() {
  return (
    <div className="flex h-full flex-col gap-3 p-5">
      <FilterBar />
      <div className="min-h-[560px] flex-1">
        <MapCard height="calc(100vh - 290px)" title="Map" />
      </div>
      <p className="text-[11px] text-muted">
        Click a zone for its intelligence panel. Zones are 1.5 km grid cells over an approximate Mumbai study region (not
        an official boundary); station outlines are synthetic demonstration jurisdictions.
      </p>
    </div>
  );
}
