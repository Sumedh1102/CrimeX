"use client";

import { useRiskLayer } from "./api";
import type { Selection } from "./store";

/**
 * Resolve "AUTO" crime type / band to the zone's highest blended risk for the window
 * (the value the map shows when a filter is "All"). Nothing is recomputed: the pick
 * comes from the API's own risk layer.
 */
export function useResolvedSelection(sel: Pick<Selection, "zoneId" | "crimeType" | "band">) {
  const needCrime = sel.crimeType === "AUTO";
  const needBand = sel.band === "AUTO";
  const { data } = useRiskLayer(needCrime ? "ALL" : sel.crimeType, needBand ? "ALL" : sel.band, needCrime || needBand);
  const item = data?.items.find((i) => i.zone_id === sel.zoneId);
  return {
    crimeType: needCrime ? (item?.crime_type ?? null) : sel.crimeType,
    band: needBand ? (item?.band ?? null) : sel.band,
  };
}
