"use client";

import { useMemo } from "react";
import { useAffinity, useAnomalies, useHotspots, useRiskLayer, useStates } from "@/lib/api";
import type { LayerItem } from "@/lib/layers";
import { useUI } from "@/lib/store";
import type { LayerKey } from "@/lib/types";

/** Fetch only the active layer; returns its items keyed by zone. */
export function useLayerData(layer: LayerKey) {
  const { crimeType, band, period, customStart, customEnd } = useUI();
  const risk = useRiskLayer(crimeType, band, layer === "risk");
  const hotspots = useHotspots(crimeType, period, band, customStart, customEnd, layer === "hotspots");
  const states = useStates(crimeType, layer === "states");
  const affinity = useAffinity(crimeType, layer === "affinity");
  const anomalies = useAnomalies(crimeType, layer === "anomalies");
  const src = { risk, hotspots, states, affinity, anomalies }[layer];
  const byZone = useMemo(
    () => new Map(((src.data?.items ?? []) as LayerItem[]).map((i) => [i.zone_id, i])),
    [src.data],
  );
  return {
    byZone,
    response: src.data,
    error: src.error,
    loading: src.isLoading,
    validating: src.isValidating,
  };
}
