"use client";

import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent, StyleSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMeta, useZones } from "@/lib/api";
import { CHROME } from "@/lib/colors";
import { stationBoundaries, styleFor, type LayerItem } from "@/lib/layers";
import { useUI } from "@/lib/store";
import type { LayerKey, ZonesGeoJSON } from "@/lib/types";
import { ICONS, labelImage, PIXEL_RATIO, TEXTURES } from "./mapImages";
import { MapTooltip } from "./MapTooltip";
import { useLayerData } from "./useLayerData";

const DEFAULT_STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#121211" } }],
};

async function resolveStyle(): Promise<{ style: StyleSpecification; offline: boolean }> {
  const url = process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? DEFAULT_STYLE_URL;
  if (url === "none") return { style: FALLBACK_STYLE, offline: true };
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 4000);
    const res = await fetch(url, { signal: ctrl.signal });
    clearTimeout(timer);
    if (!res.ok) throw new Error(String(res.status));
    return { style: (await res.json()) as StyleSpecification, offline: false };
  } catch {
    return { style: FALLBACK_STYLE, offline: true };
  }
}

function bbox(zones: ZonesGeoJSON): [[number, number], [number, number]] {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  for (const f of zones.features)
    for (const [x, y] of f.geometry.coordinates[0]) {
      w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y);
    }
  return [[w, s], [e, n]];
}

function centroid(ring: number[][]): [number, number] {
  const pts = ring.slice(0, -1);
  return [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length];
}

const EMPTY_FC: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function addLayers(map: MLMap, zones: ZonesGeoJSON) {
  for (const [id, make] of Object.entries({ ...TEXTURES, ...ICONS })) {
    if (!map.hasImage(id)) map.addImage(id, make(), { pixelRatio: PIXEL_RATIO });
  }
  map.addSource("zones", { type: "geojson", data: zones as unknown as GeoJSON.FeatureCollection });
  map.addSource("centroids", { type: "geojson", data: EMPTY_FC });
  const segs = stationBoundaries(
    zones.features.map((f) => ({ row: f.properties.row, col: f.properties.col,
      station_id: f.properties.station_id, ring: f.geometry.coordinates[0] })),
  );
  map.addSource("stations", {
    type: "geojson",
    data: { type: "Feature", properties: {}, geometry: { type: "MultiLineString", coordinates: segs } },
  });
  map.addLayer({
    id: "zones-fill",
    type: "fill",
    source: "zones",
    filter: ["==", ["get", "has_fill"], true],
    paint: {
      "fill-color": ["get", "fill"],
      "fill-opacity": ["case", ["==", ["get", "outside"], true], 0.12, 0.74],
    },
  });
  map.addLayer({
    id: "zones-texture",
    type: "fill",
    source: "zones",
    filter: ["all", ["==", ["get", "has_texture"], true], ["!=", ["get", "outside"], true]],
    paint: { "fill-pattern": ["get", "texture"], "fill-opacity": 0.85 },
  });
  map.addLayer({
    id: "zones-grid",
    type: "line",
    source: "zones",
    paint: { "line-color": CHROME.baseline, "line-width": 0.6, "line-opacity": 0.9 },
  });
  map.addLayer({
    id: "stations-line",
    type: "line",
    source: "stations",
    paint: { "line-color": CHROME.ink2, "line-width": 1.3, "line-opacity": 0.55 },
  });
  map.addLayer({
    id: "zones-hit",
    type: "fill",
    source: "zones",
    paint: { "fill-color": "#000000", "fill-opacity": 0 },
  });
  map.addLayer({
    id: "zones-hover",
    type: "line",
    source: "zones",
    filter: ["==", ["get", "zone_id"], ""],
    paint: { "line-color": CHROME.ink, "line-width": 1.5 },
  });
  map.addLayer({
    id: "zones-selected",
    type: "line",
    source: "zones",
    filter: ["==", ["get", "zone_id"], ""],
    paint: { "line-color": CHROME.ink, "line-width": 2.6 },
  });
  map.addLayer({
    id: "zone-icons",
    type: "symbol",
    source: "centroids",
    filter: ["!=", ["get", "icon"], ""],
    layout: { "icon-image": ["get", "icon"], "icon-allow-overlap": true, "icon-ignore-placement": true },
  });
  map.addLayer({
    id: "zone-labels",
    type: "symbol",
    source: "centroids",
    minzoom: 11.6,
    filter: ["all", ["!=", ["get", "label"], ""], ["==", ["get", "icon"], ""]],
    layout: { "icon-image": ["get", "label"], "icon-allow-overlap": false },
  });
}

export default function MapView({
  layer: layerProp,
  height = 520,
  className,
  children,
}: {
  layer?: LayerKey;
  height?: number | string;
  className?: string;
  children?: ReactNode; // overlays positioned inside the map box (legend, …)
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(false);
  const [offline, setOffline] = useState(false);
  const [hover, setHover] = useState<{ x: number; y: number; zoneId: string } | null>(null);

  const ui = useUI();
  const layer = layerProp ?? ui.layer;
  const { data: zones, error: zonesError } = useZones();
  const { data: meta } = useMeta();
  const data = useLayerData(layer);

  const stationZones = useMemo(() => {
    if (!zones || !ui.stationId) return null;
    return new Set(zones.features.filter((f) => f.properties.station_id === ui.stationId).map((f) => f.properties.zone_id));
  }, [zones, ui.stationId]);

  // Latest values for event handlers bound once at map creation.
  const latest = useRef({ layer, byZone: data.byZone, crimeType: ui.crimeType, band: ui.band });
  useEffect(() => {
    latest.current = { layer, byZone: data.byZone, crimeType: ui.crimeType, band: ui.band };
  });

  useEffect(() => {
    if (!container.current || !zones || mapRef.current) return;
    let cancelled = false;
    let map: MLMap | null = null;
    (async () => {
      const ml = await import("maplibre-gl");
      ml.setWorkerUrl(`${window.location.origin}/maplibre/maplibre-gl-worker.mjs`);
      const { style, offline: off } = await resolveStyle();
      if (cancelled || !container.current) return;
      setOffline(off);
      map = new ml.Map({
        container: container.current,
        style,
        bounds: bbox(zones),
        fitBoundsOptions: { padding: 24 },
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
        minZoom: 9,
        maxZoom: 16,
      });
      map.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
      // Value labels are generated on demand; MapLibre waits for the resolver.
      map.setMissingStyleImageResolver((id) => {
        if (id.startsWith("lbl:") && map && !map.hasImage(id)) {
          map.addImage(id, labelImage(id.slice(4)), { pixelRatio: PIXEL_RATIO });
        }
      });
      map.on("load", () => {
        if (!map) return;
        addLayers(map, zones);
        setReady(true);
      });
      map.on("mousemove", "zones-hit", (e: MapLayerMouseEvent) => {
        const zoneId = e.features?.[0]?.properties?.zone_id as string | undefined;
        if (!zoneId || !map) return;
        map.getCanvas().style.cursor = "pointer";
        map.setFilter("zones-hover", ["==", ["get", "zone_id"], zoneId]);
        setHover({ x: e.point.x, y: e.point.y, zoneId });
      });
      map.on("mouseleave", "zones-hit", () => {
        if (!map) return;
        map.getCanvas().style.cursor = "";
        map.setFilter("zones-hover", ["==", ["get", "zone_id"], ""]);
        setHover(null);
      });
      map.on("click", "zones-hit", (e: MapLayerMouseEvent) => {
        const zoneId = e.features?.[0]?.properties?.zone_id as string | undefined;
        if (!zoneId) return;
        const { byZone, crimeType, band } = latest.current;
        const item = byZone.get(zoneId) as (LayerItem & { crime_type?: string; band?: string }) | undefined;
        useUI.getState().select({
          zoneId,
          crimeType: crimeType !== "ALL" ? crimeType : item?.crime_type ?? "AUTO",
          band: band !== "ALL" ? band : item && "band" in item && item.band && item.band !== "ALL" ? item.band : "AUTO",
        });
      });
      mapRef.current = map;
      if (process.env.NODE_ENV !== "production") {
        (window as unknown as { __crimexMap?: MLMap }).__crimexMap = map; // e2e / debugging hook
      }
    })();
    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
      setReady(false);
    };
  }, [zones]);

  // Push layer styling into the sources whenever data or presentation options change.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !zones) return;
    const opts = { metric: ui.riskMetric, textures: ui.textures };
    const features = zones.features.map((f) => {
      const st = styleFor(layer, data.byZone.get(f.properties.zone_id), opts);
      const outside = stationZones ? !stationZones.has(f.properties.zone_id) : false;
      return {
        ...f,
        properties: {
          ...f.properties,
          fill: st.fill ?? "#000000",
          has_fill: st.fill !== null,
          texture: st.texture ?? "",
          has_texture: st.texture !== null,
          outside,
        },
      };
    });
    const points = zones.features.map((f) => {
      const st = styleFor(layer, data.byZone.get(f.properties.zone_id), opts);
      const outside = stationZones ? !stationZones.has(f.properties.zone_id) : false;
      return {
        type: "Feature" as const,
        properties: {
          zone_id: f.properties.zone_id,
          icon: !outside && st.icon ? st.icon : "",
          label: !outside && st.label ? `lbl:${st.label}` : "",
        },
        geometry: { type: "Point" as const, coordinates: centroid(f.geometry.coordinates[0]) },
      };
    });
    (map.getSource("zones") as GeoJSONSource).setData({ type: "FeatureCollection", features } as GeoJSON.FeatureCollection);
    (map.getSource("centroids") as GeoJSONSource).setData({ type: "FeatureCollection", features: points });
  }, [ready, zones, layer, data.byZone, ui.riskMetric, ui.textures, stationZones]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setFilter("zones-selected", ["==", ["get", "zone_id"], ui.selected?.zoneId ?? ""]);
  }, [ready, ui.selected]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setLayoutProperty("stations-line", "visibility", ui.showStations ? "visible" : "none");
  }, [ready, ui.showStations]);

  const hoverZone = hover && zones?.features.find((f) => f.properties.zone_id === hover.zoneId)?.properties;

  return (
    <div className={className} style={{ position: "relative", height }}>
      {/* Inline positioning: MapLibre's own .maplibregl-map rule (position: relative) would
          otherwise override utility classes and collapse the container to zero height. */}
      <div
        ref={container}
        className="overflow-hidden rounded-md"
        style={{ position: "absolute", inset: 0, background: "#121211" }}
      />
      {(data.validating || data.loading) && (
        <div className="pointer-events-none absolute left-3 top-3 rounded bg-plane/80 px-2 py-1 text-[11px] text-muted">
          Updating…
        </div>
      )}
      {offline && ready && (
        <div className="pointer-events-none absolute right-12 top-3 rounded bg-plane/80 px-2 py-1 text-[10px] text-muted">
          Basemap unavailable offline: showing the zone grid only
        </div>
      )}
      {(zonesError || data.error) && (
        <div className="absolute inset-x-3 top-3 rounded border bg-plane/90 px-3 py-2 text-xs text-ink-2" style={{ borderColor: "rgba(208,59,59,0.5)" }}>
          {(zonesError ?? data.error)?.message}
        </div>
      )}
      {children}
      {hover && hoverZone && meta && (
        <MapTooltip
          x={hover.x}
          y={hover.y}
          zone={hoverZone}
          layer={layer}
          item={data.byZone.get(hover.zoneId)}
          meta={meta}
          metric={ui.riskMetric}
          band={ui.band}
        />
      )}
    </div>
  );
}
