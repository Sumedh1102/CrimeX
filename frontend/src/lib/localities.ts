// Approximate positions of well-known Mumbai localities, used only as map reference
// labels (offline map) and to give a zone a "near …" name in the popup. They are not
// boundaries, and nothing is computed from them.
export interface Locality {
  name: string;
  lon: number;
  lat: number;
  kind: "place" | "water" | "context"; // context = outside the study region
  rank: number; // lower = placed first when labels collide
}

export const LOCALITIES: Locality[] = [
  { name: "Colaba", lon: 72.8147, lat: 18.9067, kind: "place", rank: 1 },
  { name: "Fort", lon: 72.8347, lat: 18.9340, kind: "place", rank: 2 },
  { name: "Marine Lines", lon: 72.8235, lat: 18.9447, kind: "place", rank: 3 },
  { name: "Byculla", lon: 72.8330, lat: 18.9790, kind: "place", rank: 2 },
  { name: "Worli", lon: 72.8170, lat: 19.0000, kind: "place", rank: 1 },
  { name: "Dadar", lon: 72.8430, lat: 19.0190, kind: "place", rank: 1 },
  { name: "Wadala", lon: 72.8580, lat: 19.0170, kind: "place", rank: 3 },
  { name: "Dharavi", lon: 72.8540, lat: 19.0400, kind: "place", rank: 3 },
  { name: "Sion", lon: 72.8620, lat: 19.0430, kind: "place", rank: 3 },
  { name: "Bandra", lon: 72.8360, lat: 19.0600, kind: "place", rank: 1 },
  { name: "Kurla", lon: 72.8790, lat: 19.0650, kind: "place", rank: 2 },
  { name: "Chembur", lon: 72.9000, lat: 19.0620, kind: "place", rank: 2 },
  { name: "Mankhurd", lon: 72.9320, lat: 19.0480, kind: "place", rank: 4 },
  { name: "Santacruz", lon: 72.8410, lat: 19.0810, kind: "place", rank: 3 },
  { name: "Ghatkopar", lon: 72.9080, lat: 19.0860, kind: "place", rank: 2 },
  { name: "Vile Parle", lon: 72.8440, lat: 19.1000, kind: "place", rank: 4 },
  { name: "Andheri", lon: 72.8470, lat: 19.1190, kind: "place", rank: 1 },
  { name: "Powai", lon: 72.9060, lat: 19.1180, kind: "place", rank: 2 },
  { name: "Vikhroli", lon: 72.9280, lat: 19.1110, kind: "place", rank: 3 },
  { name: "Jogeshwari", lon: 72.8490, lat: 19.1360, kind: "place", rank: 4 },
  { name: "Bhandup", lon: 72.9370, lat: 19.1440, kind: "place", rank: 3 },
  { name: "Goregaon", lon: 72.8490, lat: 19.1640, kind: "place", rank: 2 },
  { name: "Mulund", lon: 72.9560, lat: 19.1720, kind: "place", rank: 2 },
  { name: "Malad", lon: 72.8480, lat: 19.1870, kind: "place", rank: 2 },
  { name: "Kandivali", lon: 72.8520, lat: 19.2050, kind: "place", rank: 3 },
  { name: "Borivali", lon: 72.8620, lat: 19.2310, kind: "place", rank: 1 },
  { name: "Dahisar", lon: 72.8590, lat: 19.2500, kind: "place", rank: 3 },
  { name: "Sanjay Gandhi National Park", lon: 72.9100, lat: 19.2150, kind: "place", rank: 2 },
  { name: "Arabian Sea", lon: 72.7600, lat: 19.0300, kind: "water", rank: 1 },
  { name: "Thane Creek", lon: 72.9700, lat: 19.0550, kind: "water", rank: 2 },
  { name: "Mumbai Harbour", lon: 72.8750, lat: 18.9400, kind: "water", rank: 3 },
  { name: "Thane", lon: 72.9780, lat: 19.2000, kind: "context", rank: 3 },
  { name: "Navi Mumbai", lon: 73.0150, lat: 19.0600, kind: "context", rank: 3 },
  { name: "Mira-Bhayandar", lon: 72.8600, lat: 19.2950, kind: "context", rank: 4 },
];

export function localitiesGeoJSON(): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: LOCALITIES.map((l) => ({
      type: "Feature",
      properties: { name: l.name, kind: l.kind, rank: l.rank },
      geometry: { type: "Point", coordinates: [l.lon, l.lat] },
    })),
  };
}

function distanceKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const kx = 111.32 * Math.cos((((lat1 + lat2) / 2) * Math.PI) / 180);
  return Math.hypot((lon2 - lon1) * kx, (lat2 - lat1) * 110.57);
}

/** Nearest in-region locality within `maxKm` of a point, for "near …" zone names. */
export function nearestLocality(lon: number, lat: number, maxKm = 2.5): { name: string; km: number } | null {
  let best: { name: string; km: number } | null = null;
  for (const l of LOCALITIES) {
    if (l.kind !== "place" || l.name === "Sanjay Gandhi National Park") continue;
    const km = distanceKm(lon, lat, l.lon, l.lat);
    if (km <= maxKm && (!best || km < best.km)) best = { name: l.name, km };
  }
  return best;
}
