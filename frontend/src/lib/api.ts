"use client";

import useSWR, { type SWRConfiguration } from "swr";
import type {
  AffinityResponse,
  AnomaliesResponse,
  CrimeTypeProfile,
  CrimeTypesResponse,
  Dashboard,
  DataQuality,
  HotspotsResponse,
  LifecycleOverview,
  Meta,
  ModelCard,
  MovementResponse,
  OfficialSummary,
  RiskLayer,
  Station,
  StationDetail,
  StationsOverview,
  StatesResponse,
  ZoneDetail,
  ZoneLifecycle,
  ZonePatterns,
  ZonesGeoJSON,
} from "./types";

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export function qs(params: Record<string, string | number | null | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!entries.length) return "";
  return "?" + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

// Keep the previous response while a new one loads (no layout jump or flash).
const base: SWRConfiguration = { keepPreviousData: true, revalidateOnFocus: false };

function useApi<T>(path: string | null) {
  return useSWR<T, ApiError>(path, fetcher<T>, base);
}

export const useMeta = () => useApi<Meta>("/meta");
export const useZones = () => useApi<ZonesGeoJSON>("/zones");
export const useStations = () => useApi<{ data_label: string; items: Station[] }>("/stations");
export const useCrimeTypes = () => useApi<CrimeTypesResponse>("/crime-types");
export const useRiskLayer = (crimeType: string, band: string, enabled = true) =>
  useApi<RiskLayer>(enabled ? `/predictions${qs({ crime_type: crimeType, band })}` : null);
export const useHotspots = (
  crimeType: string,
  period: string,
  band: string,
  start?: string | null,
  end?: string | null,
  enabled = true,
) =>
  useApi<HotspotsResponse>(
    !enabled || (period === "custom" && (!start || !end))
      ? null
      : `/hotspots${qs({ crime_type: crimeType, period, band, start, end })}`,
  );
export const useStates = (crimeType: string, enabled = true) =>
  useApi<StatesResponse>(enabled ? `/emerging-hotspots${qs({ crime_type: crimeType })}` : null);
export const useAffinity = (crimeType: string, enabled = true) =>
  useApi<AffinityResponse>(enabled ? `/affinity${qs({ crime_type: crimeType })}` : null);
export const useAnomalies = (crimeType: string, enabled = true) =>
  useApi<AnomaliesResponse>(enabled ? `/anomalies${qs({ crime_type: crimeType })}` : null);
export const useZoneDetail = (zoneId: string | null, crimeType: string | null, band: string | null) =>
  useApi<ZoneDetail>(
    zoneId && crimeType && band ? `/zones/${zoneId}${qs({ crime_type: crimeType, band })}` : null,
  );
export const useDashboard = (crimeType: string, stationId: string | null) =>
  useApi<Dashboard>(`/dashboard/summary${qs({ crime_type: crimeType, station_id: stationId })}`);
export const useCrimeTypeProfile = (code: string) =>
  useApi<CrimeTypeProfile>(`/crime-types/${code}/profile`);
export const useOfficial = () => useApi<OfficialSummary>("/official/summary");
export const useModelCard = () => useApi<ModelCard>("/model");
export const useDataQuality = () => useApi<DataQuality>("/data-quality");
export const useLifecycle = (crimeType: string) =>
  useApi<LifecycleOverview>(`/hotspot-lifecycle${qs({ crime_type: crimeType })}`);
export const useMovement = (crimeType: string, step: number | null = null, enabled = true) =>
  useApi<MovementResponse>(enabled ? `/hotspot-movement${qs({ crime_type: crimeType, step })}` : null);
export const useZoneLifecycle = (zoneId: string | null, crimeType: string | null) =>
  useApi<ZoneLifecycle>(zoneId && crimeType ? `/zones/${zoneId}/lifecycle${qs({ crime_type: crimeType })}` : null);
export const useZonePatterns = (zoneId: string | null, crimeType: string | null) =>
  useApi<ZonePatterns>(zoneId && crimeType ? `/zones/${zoneId}/patterns${qs({ crime_type: crimeType })}` : null);
export const useStationsOverview = () => useApi<StationsOverview>("/stations/overview");
export const useStationDetail = (stationId: string | null, band: string) =>
  useApi<StationDetail>(stationId ? `/stations/${stationId}${qs({ band })}` : null);

/** Printable HTML briefs served by the API (open in a new tab; print to PDF). */
export const stationReportUrl = (stationId: string) => `${API_BASE}/reports/stations/${stationId}`;
export const zoneReportUrl = (zoneId: string, crimeType: string, band: string) =>
  `${API_BASE}/reports/zones/${zoneId}${qs({ crime_type: crimeType, band })}`;
