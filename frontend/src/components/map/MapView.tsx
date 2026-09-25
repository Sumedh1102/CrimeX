"use client";

import type {
  GeoJSONSource,
  LayerSpecification,
  Map as MLMap,
  MapLayerMouseEvent,
  StyleSpecification,
} from "maplibre-gl";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMeta, useZones } from "@/lib/api";
import {
  offlineBaseStyle,
  probeProvider,
  providerChain,
  rasterBaseStyle,
  referenceStyleParts,
  REFERENCE_LAYERS,
  REFERENCE_SOURCES,
  type BasemapProvider,
} from "@/lib/basemap";
import { CHROME, RISK_FILL_OPACITY } from "@/lib/colors";
import { stationBoundaries, styleFor, type LayerItem } from "@/lib/layers";
import { localitiesGeoJSON } from "@/lib/localities";
import { useUI } from "@/lib/store";
import type { LayerKey, ZonesGeoJSON } from "@/lib/types";
import { BasemapStatus, type BasemapState } from "./BasemapStatus";
import { ICONS, labelImage, PIXEL_RATIO, referenceLabelImage, TEXTURES } from "./mapImages";
import { MapTooltip } from "./MapTooltip";
import { ZonePopup } from "./ZonePopup";
import { useLayerData } from "./useLayerData";

const PROBE_DEADLINE_MS = 6000; // after this the offline reference map is used
const TILE_WATCHDOG_MS = 12000; // live basemap that has loaded no tile by then -> offline

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

/** Probe providers in parallel; take the first, in priority order, that serves a real tile. */
async function chooseBasemap(
  chain: BasemapProvider[],
  center: [number, number],
): Promise<{ provider: BasemapProvider; style: StyleSpecification; failures: string[] }> {
  const offline = chain[chain.length - 1];
  const live = chain.filter((p) => p.kind !== "offline");
  const probes = live.map((p) => probeProvider(p, center, { timeoutMs: PROBE_DEADLINE_MS - 500 }));
  const failures: string[] = [];
  for (let i = 0; i < live.length; i++) {
    const r = await probes[i];
    if (r.ok) {
      const p = live[i];
      return { provider: p, style: p.kind === "raster" ? rasterBaseStyle(p) : r.style!, failures };
    }
    failures.push(`${live[i].label}: ${r.reason}`);
  }
  return { provider: offline, style: offlineBaseStyle(), failures };
}

/** Basemap + the offline reference layers (hidden unless offline). */
function composeStyle(base: StyleSpecification, offline: boolean): StyleSpecification {
  const ref = referenceStyleParts(localitiesGeoJSON(), offline);
  const layers = base.layers ?? [];
  const firstSymbol = layers.findIndex((l) => l.type === "symbol");
  const cut = firstSymbol < 0 ? layers.length : firstSymbol;
  const sea: LayerSpecification = {
    id: "ref-sea",
    type: "background",
    layout: { visibility: offline ? "visible" : "none" },
    paint: { "background-color": "#0f1a26" },
  };
  return {
    ...base,
    sources: { ...base.sources, ...ref.sources },
    layers: [...layers.slice(0, cut), sea, ...ref.below, ...layers.slice(cut), ...ref.above],
  };
}

function isOurs(id: string) {
  return (
    id === "ref-sea" ||
    (REFERENCE_LAYERS as readonly string[]).includes(id) ||
    id.startsWith("zones-") ||
    id.startsWith("zone-") ||
    id === "stations-line"
  );
}

function addOverlays(map: MLMap, zones: ZonesGeoJSON) {
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
  // Fills sit under the basemap's labels so place and road names stay readable.
  const beforeLabels = map.getStyle().layers.find((l) => l.type === "symbol" && !isOurs(l.id))?.id ??
    (map.getLayer("ref-labels") ? "ref-labels" : undefined);
  map.addLayer({
    id: "zones-fill",
    type: "fill",
    source: "zones",
    filter: ["==", ["get", "has_fill"], true],
    paint: {
      "fill-color": ["get", "fill"],
      "fill-opacity": ["case", ["==", ["get", "outside"], true], 0.12, 0.74],
    },
  }, beforeLabels);
  map.addLayer({
    id: "zones-texture",
    type: "fill",
    source: "zones",
    filter: ["all", ["==", ["get", "has_texture"], true], ["!=", ["get", "outside"], true]],
    paint: { "fill-pattern": ["get", "texture"], "fill-opacity": 0.85 },
  }, beforeLabels);
  map.addLayer({
    id: "zones-grid",
    type: "line",
    source: "zones",
    paint: { "line-color": CHROME.plane, "line-width": 0.8, "line-opacity": 0.85 },
  }, beforeLabels);
  map.addLayer({
    id: "stations-line",
    type: "line",
    source: "stations",
    paint: { "line-color": CHROME.ink2, "line-width": 1.3, "line-opacity": 0.6 },
  }, beforeLabels);
  map.addLayer({
    id: "zones-hit",
    type: "fill",
    source: "zones",
    paint: { "fill-color": "#000000", "fill-opacity": 0 },
  });
  // Hover / selection outlines: white line on a dark halo, legible on the brightest fill.
  for (const [id, width] of [["zones-hover", 1.6], ["zones-selected", 2.6]] as const) {
    map.addLayer({
      id: `${id}-halo`,
      type: "line",
      source: "zones",
      filter: ["==", ["get", "zone_id"], ""],
      paint: { "line-color": CHROME.plane, "line-width": width + 3 },
    });
    map.addLayer({
      id,
      type: "line",
      source: "zones",
      filter: ["==", ["get", "zone_id"], ""],
      paint: { "line-color": CHROME.ink, "line-width": width },
    });
  }
  map.addLayer({
    id: "zone-icons",
    type: "symbol",
    source: "centroids",
    filter: ["!=", ["get", "icon"], ""],
    layout: {
      "icon-image": ["get", "icon"],
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
      "icon-size": ["interpolate", ["linear"], ["zoom"], 9, 0.8, 12, 1, 14, 1.15],
    },
  });
  map.addLayer({
    id: "zone-labels",
    type: "symbol",
    source: "centroids",
    minzoom: 11.6,
    filter: ["!=", ["get", "label"], ""],
    layout: {
      "icon-image": ["get", "label"],
      "icon-allow-overlap": false,
      // Values sit below a marker when the zone has one.
      "icon-offset": ["case", ["!=", ["get", "icon"], ""], ["literal", [0, 15]], ["literal", [0, 0]]],
    },
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
  const camera = useRef<{ center: [number, number]; zoom: number } | null>(null);
  const [ready, setReady] = useState(false);
  const [basemap, setBasemap] = useState<BasemapState>({ phase: "probing" });
  const [attempt, setAttempt] = useState(0);
  const [hover, setHover] = useState<{ x: number; y: number; zoneId: string } | null>(null);
  const [popup, setPopup] = useState<{ zoneId: string; lngLat: [number, number] } | null>(null);
  const [popupPoint, setPopupPoint] = useState<{ x: number; y: number } | null>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });

  const ui = useUI();
  const layer = layerProp ?? ui.layer;
  const { data: zones, error: zonesError } = useZones();
  const { data: meta } = useMeta();
  const data = useLayerData(layer);

  const stationZones = useMemo(() => {
    if (!zones || !ui.stationId) return null;
    return new Set(zones.features.filter((f) => f.properties.station_id === ui.stationId).map((f) => f.properties.zone_id));
  }, [zones, ui.stationId]);

  const centroids = useMemo(
    () => new Map((zones?.features ?? []).map((f) => [f.properties.zone_id, centroid(f.geometry.coordinates[0])])),
    [zones],
  );

  // Latest values for event handlers bound once at map creation.
  const latest = useRef({ centroids, popup });
  useEffect(() => {
    latest.current = { centroids, popup };
  });

  useEffect(() => {
    const el = container.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!container.current || !zones || mapRef.current) return;
    let cancelled = false;
    let map: MLMap | null = null;
    let watchdog: ReturnType<typeof setTimeout> | undefined;
    setBasemap({ phase: "probing" });
    (async () => {
      const ml = await import("maplibre-gl");
      ml.setWorkerUrl(`${window.location.origin}/maplibre/maplibre-gl-worker.mjs`);
      const [[w, s], [e, n]] = bbox(zones);
      const chain = providerChain(ui.basemap, process.env.NEXT_PUBLIC_MAP_STYLE_URL);
      const { provider, style: base, failures } = await chooseBasemap(chain, [(w + e) / 2, (s + n) / 2]);
      if (cancelled || !container.current) return;
      const offline = provider.kind === "offline";
      const baseSources = new Set(Object.keys(base.sources ?? {}));
      map = new ml.Map({
        container: container.current,
        style: composeStyle(base, offline),
        ...(camera.current
          ? { center: camera.current.center, zoom: camera.current.zoom }
          : { bounds: [[w, s], [e, n]] as [[number, number], [number, number]], fitBoundsOptions: { padding: 24 } }),
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
        cooperativeGestures: false,
        minZoom: 9,
        maxZoom: 16,
        maxBounds: [[w - 0.45, s - 0.35], [e + 0.45, n + 0.35]],
      });
      map.touchZoomRotate.disableRotation();
      map.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
      // Canvas-drawn images are generated on demand; MapLibre waits for the resolver. This
      // also re-supplies icons and textures if a style reload drops them.
      map.setMissingStyleImageResolver((id) => {
        if (!map || map.hasImage(id)) return;
        const make = TEXTURES[id] ?? ICONS[id];
        const img = id.startsWith("lbl:") ? labelImage(id.slice(4)) : id.startsWith("ref:") ? referenceLabelImage(id) : make?.();
        if (img) map.addImage(id, img, { pixelRatio: PIXEL_RATIO });
      });

      let failedOver: string | null = null; // runtime failure reason, if the live basemap died
      const goOffline = (reason: string) => {
        if (!map || failedOver) return;
        failedOver = reason;
        for (const l of map.getStyle().layers) {
          const ref = l.id === "ref-sea" || (REFERENCE_LAYERS as readonly string[]).includes(l.id);
          if (ref) map.setLayoutProperty(l.id, "visibility", "visible");
          else if (!isOurs(l.id)) map.setLayoutProperty(l.id, "visibility", "none");
        }
        setBasemap({ phase: "offline", provider: provider.label, reason, failures });
      };

      let tilesOk = 0;
      let tileErrors = 0;
      map.on("data", (ev) => {
        const e = ev as { dataType?: string; sourceId?: string; tile?: unknown };
        if (e.dataType === "source" && e.tile && e.sourceId && baseSources.has(e.sourceId)) tilesOk++;
      });
      map.on("error", (ev) => {
        const sid = (ev as { sourceId?: string }).sourceId;
        if (offline || !sid || !baseSources.has(sid) || (REFERENCE_SOURCES as readonly string[]).includes(sid)) return;
        tileErrors++;
        if (tilesOk === 0 && tileErrors >= 3) goOffline(`${provider.label}: street tiles failed to load`);
      });

      map.on("load", () => {
        if (!map) return;
        addOverlays(map, zones);
        setReady(true);
        // Tile errors can arrive before "load"; a failover already reported wins.
        if (failedOver) setBasemap({ phase: "offline", provider: provider.label, reason: failedOver, failures });
        else
          setBasemap(
            offline
              ? { phase: "offline", provider: provider.label, reason: failures.length ? "no street-map provider reachable" : "selected", failures }
              : { phase: "live", provider: provider.label, failures },
          );
        if (!offline && !failedOver) {
          watchdog = setTimeout(() => {
            if (tilesOk === 0) goOffline(`${provider.label}: no street tiles loaded`);
          }, TILE_WATCHDOG_MS);
        }
      });

      const openPopup = (zoneId: string | undefined) => {
        if (!zoneId) return;
        const c = latest.current.centroids.get(zoneId);
        if (c) setPopup({ zoneId, lngLat: c });
      };
      map.on("mousemove", "zones-hit", (ev: MapLayerMouseEvent) => {
        const zoneId = ev.features?.[0]?.properties?.zone_id as string | undefined;
        if (!zoneId || !map) return;
        map.getCanvas().style.cursor = "pointer";
        map.setFilter("zones-hover", ["==", ["get", "zone_id"], zoneId]);
        map.setFilter("zones-hover-halo", ["==", ["get", "zone_id"], zoneId]);
        setHover({ x: ev.point.x, y: ev.point.y, zoneId });
      });
      map.on("mouseleave", "zones-hit", () => {
        if (!map) return;
        map.getCanvas().style.cursor = "";
        map.setFilter("zones-hover", ["==", ["get", "zone_id"], ""]);
        map.setFilter("zones-hover-halo", ["==", ["get", "zone_id"], ""]);
        setHover(null);
      });
      // Markers and zone polygons both open the popup (markers are larger tap targets).
      map.on("click", (ev) => {
        if (!map) return;
        const pad = 10;
        const hits = map.queryRenderedFeatures(
          [[ev.point.x - pad, ev.point.y - pad], [ev.point.x + pad, ev.point.y + pad]],
          { layers: ["zone-icons"] },
        );
        // Markers can sit closer together than the tap box: take the nearest one.
        let nearest: { id: string; d: number } | null = null;
        for (const h of hits) {
          const c = latest.current.centroids.get(h.properties?.zone_id as string);
          if (!c) continue;
          const q = map.project(c);
          const d = Math.hypot(q.x - ev.point.x, q.y - ev.point.y);
          if (!nearest || d < nearest.d) nearest = { id: h.properties.zone_id as string, d };
        }
        const zoneId = (nearest?.id ??
          map.queryRenderedFeatures(ev.point, { layers: ["zones-hit"] })[0]?.properties?.zone_id) as string | undefined;
        if (zoneId) openPopup(zoneId);
        else setPopup(null);
      });
      map.on("mouseenter", "zone-icons", () => map && (map.getCanvas().style.cursor = "pointer"));
      // Keep the popup anchored to its zone while the map pans and zooms.
      map.on("move", () => {
        const p = latest.current.popup;
        if (p && map) setPopupPoint(map.project(p.lngLat));
      });

      mapRef.current = map;
      if (process.env.NODE_ENV !== "production") {
        (window as unknown as { __crimexMap?: MLMap }).__crimexMap = map; // e2e / debugging hook
      }
    })();
    return () => {
      cancelled = true;
      clearTimeout(watchdog);
      if (map) {
        const c = map.getCenter();
        camera.current = { center: [c.lng, c.lat], zoom: map.getZoom() };
        map.remove();
      }
      mapRef.current = null;
      setReady(false);
    };
    // ui.basemap / attempt: a new provider choice or a retry rebuilds the map (camera kept).
  }, [zones, ui.basemap, attempt]);

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
    // Risk bands are near-opaque so they stay distinguishable; other layers keep their
    // validated translucent fill.
    const opacity = layer === "risk" ? RISK_FILL_OPACITY : 0.74;
    map.setPaintProperty("zones-fill", "fill-opacity", ["case", ["==", ["get", "outside"], true], 0.12, opacity]);
  }, [ready, zones, layer, data.byZone, ui.riskMetric, ui.textures, stationZones]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const id = popup?.zoneId ?? ui.selected?.zoneId ?? "";
    map.setFilter("zones-selected", ["==", ["get", "zone_id"], id]);
    map.setFilter("zones-selected-halo", ["==", ["get", "zone_id"], id]);
  }, [ready, ui.selected, popup]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setLayoutProperty("stations-line", "visibility", ui.showStations ? "visible" : "none");
  }, [ready, ui.showStations]);

  useEffect(() => {
    const map = mapRef.current;
    setPopupPoint(popup && map && ready ? map.project(popup.lngLat) : null);
  }, [popup, ready]);

  useEffect(() => {
    if (!popup) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setPopup(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [popup]);

  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  const hoverZone = hover && zones?.features.find((f) => f.properties.zone_id === hover.zoneId)?.properties;
  const popupZone = popup && zones?.features.find((f) => f.properties.zone_id === popup.zoneId)?.properties;

  return (
    <div className={className} style={{ position: "relative", height }}>
      {/* Inline positioning: MapLibre's own .maplibregl-map rule (position: relative) would
          otherwise override utility classes and collapse the container to zero height. */}
      <div
        ref={container}
        className="overflow-hidden rounded-md"
        style={{ position: "absolute", inset: 0, background: "#0f1a26" }}
        aria-label="Zone risk map"
        role="region"
      />
      {basemap.phase === "probing" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-xs text-muted">
          Loading map…
        </div>
      )}
      <div className="absolute left-2 top-2 z-10 flex max-w-[calc(100%-56px)] flex-col items-start gap-1.5">
        <BasemapStatus state={basemap} onRetry={retry} />
        {(data.validating || data.loading) && (
          <div className="pointer-events-none rounded bg-plane/85 px-2 py-1 text-[11px] text-muted">Updating…</div>
        )}
      </div>
      {(zonesError || data.error) && (
        <div className="absolute inset-x-3 top-12 z-10 rounded border bg-plane/90 px-3 py-2 text-xs text-ink-2" style={{ borderColor: "rgba(208,59,59,0.5)" }}>
          {(zonesError ?? data.error)?.message}
        </div>
      )}
      {children}
      {hover && hoverZone && meta && !popup && (
        <MapTooltip
          x={hover.x}
          y={hover.y}
          zone={hoverZone}
          layer={layer}
          item={data.byZone.get(hover.zoneId)}
          meta={meta}
          metric={ui.riskMetric}
          band={ui.band}
          bounds={size}
        />
      )}
      {popup && popupZone && popupPoint && (
        <ZonePopup
          key={popup.zoneId}
          zone={popupZone}
          point={popupPoint}
          bounds={size}
          item={data.byZone.get(popup.zoneId) as (LayerItem & { crime_type?: string; band?: string }) | undefined}
          onClose={() => setPopup(null)}
        />
      )}
    </div>
  );
}
