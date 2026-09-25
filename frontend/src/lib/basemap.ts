// Basemap providers and the offline Mumbai reference map.
//
// The street map is decoration: every overlay works without it. Providers are tried in
// order; each is probed (style JSON, then one real tile over Mumbai) before the map is
// created, and tile failures at runtime switch the map to the bundled offline reference
// (OSM-derived coastline and water bodies, approximate locality labels), which needs no
// network at all.
import type { StyleSpecification } from "maplibre-gl";

export type BasemapChoice = "auto" | "carto-dark" | "openfreemap-dark" | "carto-raster" | "offline";

export interface BasemapProvider {
  id: Exclude<BasemapChoice, "auto"> | "custom";
  label: string;
  kind: "vector" | "raster" | "offline";
  styleUrl?: string;
  tiles?: string[];
  attribution?: string;
}

const OSM = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export const PROVIDERS: Record<Exclude<BasemapChoice, "auto">, BasemapProvider> = {
  "carto-dark": {
    id: "carto-dark",
    label: "CARTO Dark Matter",
    kind: "vector",
    styleUrl: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  },
  "openfreemap-dark": {
    id: "openfreemap-dark",
    label: "OpenFreeMap Dark",
    kind: "vector",
    styleUrl: "https://tiles.openfreemap.org/styles/dark",
  },
  "carto-raster": {
    id: "carto-raster",
    label: "CARTO Dark (raster)",
    kind: "raster",
    tiles: ["a", "b", "c", "d"].map((s) => `https://${s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png`),
    attribution: `${OSM} © <a href="https://carto.com/attributions">CARTO</a>`,
  },
  offline: { id: "offline", label: "Offline reference map", kind: "offline" },
};

export const BASEMAP_OPTIONS: { value: BasemapChoice; label: string }[] = [
  { value: "auto", label: "Auto (best available)" },
  { value: "carto-dark", label: PROVIDERS["carto-dark"].label },
  { value: "openfreemap-dark", label: PROVIDERS["openfreemap-dark"].label },
  { value: "carto-raster", label: PROVIDERS["carto-raster"].label },
  { value: "offline", label: PROVIDERS.offline.label },
];

/**
 * Providers to try, in order. `NEXT_PUBLIC_MAP_STYLE_URL` puts a custom style (e.g. a
 * keyed MapTiler or Stadia style) first; the value "none" forces the offline map.
 */
export function providerChain(choice: BasemapChoice, customStyleUrl?: string): BasemapProvider[] {
  if (customStyleUrl === "none") return [PROVIDERS.offline];
  if (choice !== "auto") return choice === "offline" ? [PROVIDERS.offline] : [PROVIDERS[choice], PROVIDERS.offline];
  const chain: BasemapProvider[] = [];
  if (customStyleUrl) chain.push({ id: "custom", label: "Custom style", kind: "vector", styleUrl: customStyleUrl });
  chain.push(PROVIDERS["carto-dark"], PROVIDERS["openfreemap-dark"], PROVIDERS["carto-raster"], PROVIDERS.offline);
  return chain;
}

/** Slippy-map tile containing a point. */
export function lonLatToTile(lon: number, lat: number, z: number): { x: number; y: number; z: number } {
  const n = 2 ** z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const r = (lat * Math.PI) / 180;
  const y = Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n);
  return { x, y, z };
}

export function tileUrl(template: string, t: { x: number; y: number; z: number }): string {
  return template.replace("{z}", String(t.z)).replace("{x}", String(t.x)).replace("{y}", String(t.y));
}

type Fetch = (url: string, init?: { signal?: AbortSignal }) => Promise<{ ok: boolean; status: number; json(): Promise<unknown> }>;

async function fetchWithTimeout(fetchImpl: Fetch, url: string, ms: number) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const res = await fetchImpl(url, { signal: ctrl.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res;
  } catch (e) {
    throw new Error(ctrl.signal.aborted ? "timed out" : e instanceof Error ? e.message : String(e));
  } finally {
    clearTimeout(timer);
  }
}

/** First tile URL template of a style's first vector/raster source (resolving TileJSON). */
async function styleTileTemplate(style: StyleSpecification, fetchImpl: Fetch, ms: number): Promise<string | null> {
  for (const src of Object.values(style.sources ?? {})) {
    if (src.type !== "vector" && src.type !== "raster") continue;
    if ("tiles" in src && src.tiles?.length) return src.tiles[0];
    if ("url" in src && src.url) {
      const tj = (await (await fetchWithTimeout(fetchImpl, src.url, ms)).json()) as { tiles?: string[] };
      if (tj.tiles?.length) return tj.tiles[0];
    }
  }
  return null;
}

export interface ProbeResult {
  ok: boolean;
  style?: StyleSpecification;
  reason?: string;
}

/** Can this provider actually serve Mumbai right now? Checks the style and one real tile. */
export async function probeProvider(
  p: BasemapProvider,
  center: [number, number],
  { fetchImpl = fetch as unknown as Fetch, timeoutMs = 4000 }: { fetchImpl?: Fetch; timeoutMs?: number } = {},
): Promise<ProbeResult> {
  if (p.kind === "offline") return { ok: true };
  const tile = lonLatToTile(center[0], center[1], 11);
  try {
    if (p.kind === "raster") {
      await fetchWithTimeout(fetchImpl, tileUrl(p.tiles![0], tile), timeoutMs);
      return { ok: true };
    }
    const style = (await (await fetchWithTimeout(fetchImpl, p.styleUrl!, timeoutMs)).json()) as StyleSpecification;
    const template = await styleTileTemplate(style, fetchImpl, timeoutMs);
    if (!template) return { ok: false, reason: "style has no tile source" };
    await fetchWithTimeout(fetchImpl, tileUrl(template, tile), timeoutMs);
    return { ok: true, style };
  } catch (e) {
    return { ok: false, reason: e instanceof Error ? e.message : String(e) };
  }
}

// ------------------------------------------------------------------ offline reference

export const REFERENCE_COLORS = {
  sea: "#0f1a26", // map background = open water
  land: "#1c1c1a",
  water: "#0f1a26", // creeks, lakes
  coast: "#3a4a5a",
  label: "#c3c2b7",
  waterLabel: "#7f93a8",
} as const;

export const REFERENCE_ATTRIBUTION =
  `Offline reference: coastline & water ${OSM} (ODbL) via geo-maps · locality labels approximate`;

export const REFERENCE_SOURCES = ["ref-land", "ref-water", "ref-labels"] as const;
export const REFERENCE_LAYERS = ["ref-land", "ref-water", "ref-coast", "ref-labels", "ref-labels-minor"] as const;

/** Offline reference sources + layers (added to every style; visible only in offline mode). */
export function referenceStyleParts(labels: GeoJSON.FeatureCollection, visible: boolean) {
  const visibility = visible ? "visible" : "none";
  const sources: StyleSpecification["sources"] = {
    "ref-land": { type: "geojson", data: "/geo/mumbai-land.geojson", attribution: REFERENCE_ATTRIBUTION },
    "ref-water": { type: "geojson", data: "/geo/mumbai-water.geojson" },
    "ref-labels": { type: "geojson", data: labels },
  };
  const below: StyleSpecification["layers"] = [
    { id: "ref-land", type: "fill", source: "ref-land", layout: { visibility }, paint: { "fill-color": REFERENCE_COLORS.land } },
    { id: "ref-water", type: "fill", source: "ref-water", layout: { visibility }, paint: { "fill-color": REFERENCE_COLORS.water } },
    {
      id: "ref-coast",
      type: "line",
      source: "ref-land",
      layout: { visibility },
      paint: { "line-color": REFERENCE_COLORS.coast, "line-width": 0.8 },
    },
  ];
  // Labels are canvas images ("ref:" ids) so they render without a glyph server. Major
  // localities first; the rest appear once zoomed in, so labels don't bury the zones.
  const label = (id: string, minzoom: number, filter: ["<=" | ">", ["get", "rank"], number]) => ({
    id,
    type: "symbol" as const,
    source: "ref-labels",
    minzoom,
    filter,
    layout: {
      visibility,
      "icon-image": ["concat", "ref:", ["get", "kind"], ":", ["get", "name"]] as ["concat", ...unknown[]],
      "icon-allow-overlap": false,
      "icon-padding": 2,
      "symbol-sort-key": ["get", "rank"] as ["get", string],
    },
    paint: { "icon-opacity": 0.9 },
  });
  const above = [
    label("ref-labels", 9.5, ["<=", ["get", "rank"], 2]),
    label("ref-labels-minor", 11.3, [">", ["get", "rank"], 2]),
  ] as StyleSpecification["layers"];
  return { sources, below, above };
}

/** Style for the offline provider: water background plus the reference layers. */
export function offlineBaseStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {},
    layers: [{ id: "background", type: "background", paint: { "background-color": REFERENCE_COLORS.sea } }],
  };
}

export function rasterBaseStyle(p: BasemapProvider): StyleSpecification {
  return {
    version: 8,
    sources: { basemap: { type: "raster", tiles: p.tiles!, tileSize: 256, maxzoom: 19, attribution: p.attribution } },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#121211" } },
      { id: "basemap", type: "raster", source: "basemap", paint: { "raster-opacity": 0.95 } },
    ],
  };
}
