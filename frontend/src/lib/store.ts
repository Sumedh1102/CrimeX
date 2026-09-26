"use client";

import { create } from "zustand";
import type { BasemapChoice } from "./basemap";
import type { LayerKey, RiskMetric } from "./types";

export interface Selection {
  zoneId: string;
  crimeType: string;
  band: string;
}

interface UIState {
  layer: LayerKey;
  crimeType: string; // code or "ALL"
  band: string; // code or "ALL"
  period: string; // hotspot analysis period
  customStart: string | null;
  customEnd: string | null;
  stationId: string | null;
  riskMetric: RiskMetric;
  showStations: boolean;
  showMovement: boolean; // hotspot movement overlay (latest analysis step)
  textures: boolean;
  basemap: BasemapChoice;
  navOpen: boolean; // mobile / tablet navigation drawer
  selected: Selection | null;
  set: (patch: Partial<Omit<UIState, "set" | "select" | "clearSelection">>) => void;
  select: (s: Selection) => void;
  clearSelection: () => void;
}

export const useUI = create<UIState>((set) => ({
  layer: "risk",
  crimeType: "ALL",
  band: "ALL",
  period: "90d",
  customStart: null,
  customEnd: null,
  stationId: null,
  riskMetric: "final_risk",
  showStations: true,
  showMovement: false,
  textures: true,
  basemap: "auto",
  navOpen: false,
  selected: null,
  set: (patch) => set(patch),
  select: (s) => set({ selected: s }),
  clearSelection: () => set({ selected: null }),
}));
