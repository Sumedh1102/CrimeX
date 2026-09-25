import { describe, expect, it } from "vitest";
import { lonLatToTile, probeProvider, PROVIDERS, providerChain, referenceStyleParts, tileUrl } from "./basemap";
import { RISK_COLORS, RISK_ORDER } from "./colors";
import { LOCALITIES, nearestLocality } from "./localities";

const MUMBAI: [number, number] = [72.87, 19.08];

type Resp = { ok: boolean; status: number; json(): Promise<unknown> };
const ok = (body: unknown = {}): Resp => ({ ok: true, status: 200, json: async () => body });
const fail = (status = 403): Resp => ({ ok: false, status, json: async () => ({}) });

describe("provider chain", () => {
  it("auto tries a custom style first, then keyless providers, and always ends offline", () => {
    const ids = providerChain("auto", "https://example.test/style.json").map((p) => p.id);
    expect(ids).toEqual(["custom", "carto-dark", "openfreemap-dark", "carto-raster", "offline"]);
    expect(providerChain("auto").map((p) => p.id)[0]).toBe("carto-dark");
  });

  it("an explicit choice falls back only to offline; 'none' forces offline", () => {
    expect(providerChain("openfreemap-dark").map((p) => p.id)).toEqual(["openfreemap-dark", "offline"]);
    expect(providerChain("offline").map((p) => p.id)).toEqual(["offline"]);
    expect(providerChain("auto", "none").map((p) => p.id)).toEqual(["offline"]);
  });
});

describe("tile maths", () => {
  it("finds the slippy tile over Mumbai", () => {
    // z11 tile over Kurla: x = floor((72.87 + 180) / 360 * 2048) = 1438,
    // y = floor((1 - asinh(tan(19.08°)) / π) / 2 * 2048) = 913
    const t = lonLatToTile(MUMBAI[0], MUMBAI[1], 11);
    expect(t).toEqual({ x: 1438, y: 913, z: 11 });
    expect(tileUrl("https://t/{z}/{x}/{y}.png", t)).toBe("https://t/11/1438/913.png");
  });
});

describe("probeProvider", () => {
  it("accepts a vector style only when TileJSON and a real tile both load", async () => {
    const calls: string[] = [];
    const fetchImpl = async (url: string) => {
      calls.push(url);
      if (url.endsWith("style.json")) return ok({ version: 8, sources: { s: { type: "vector", url: "https://t/tiles.json" } }, layers: [] });
      if (url.endsWith("tiles.json")) return ok({ tiles: ["https://t/{z}/{x}/{y}.pbf"] });
      return ok();
    };
    const r = await probeProvider(PROVIDERS["carto-dark"], MUMBAI, { fetchImpl });
    expect(r.ok).toBe(true);
    expect(r.style?.version).toBe(8);
    expect(calls.at(-1)).toBe("https://t/11/1438/913.pbf");
  });

  it("rejects a provider whose style loads but whose tiles are blocked", async () => {
    const fetchImpl = async (url: string) =>
      url.endsWith("style.json") ? ok({ version: 8, sources: { s: { type: "vector", tiles: ["https://t/{z}/{x}/{y}"] } }, layers: [] }) : fail(403);
    const r = await probeProvider(PROVIDERS["carto-dark"], MUMBAI, { fetchImpl });
    expect(r).toMatchObject({ ok: false, reason: "HTTP 403" });
  });

  it("times out instead of hanging", async () => {
    const fetchImpl = (_: string, init?: { signal?: AbortSignal }) =>
      new Promise<Resp>((_, reject) => init?.signal?.addEventListener("abort", () => reject(new Error("aborted"))));
    const r = await probeProvider(PROVIDERS["carto-raster"], MUMBAI, { fetchImpl, timeoutMs: 20 });
    expect(r).toMatchObject({ ok: false, reason: "timed out" });
  });

  it("offline needs no network", async () => {
    expect(await probeProvider(PROVIDERS.offline, MUMBAI, { fetchImpl: async () => fail() })).toEqual({ ok: true });
  });
});

describe("offline reference map", () => {
  it("adds land, water and label layers, hidden unless offline", () => {
    const hidden = referenceStyleParts({ type: "FeatureCollection", features: [] }, false);
    const shown = referenceStyleParts({ type: "FeatureCollection", features: [] }, true);
    expect(Object.keys(hidden.sources)).toEqual(["ref-land", "ref-water", "ref-labels"]);
    for (const l of [...hidden.below, ...hidden.above]) expect(l.layout?.visibility).toBe("none");
    for (const l of [...shown.below, ...shown.above]) expect(l.layout?.visibility).toBe("visible");
  });

  it("names a zone after the nearest locality within 2.5 km, and nothing far from any", () => {
    expect(nearestLocality(72.8484, 19.117)?.name).toBe("Andheri");
    expect(nearestLocality(72.6, 19.0)).toBeNull(); // open sea
    expect(LOCALITIES.every((l) => l.lon > 72.7 && l.lon < 73.1 && l.lat > 18.85 && l.lat < 19.33)).toBe(true);
  });
});

describe("risk palette", () => {
  it("keeps one distinct colour per band, darkest to brightest", () => {
    const lum = (hex: string) => {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const values = RISK_ORDER.map((b) => RISK_COLORS[b]);
    expect(new Set(values).size).toBe(5);
    for (let i = 1; i < values.length; i++) expect(lum(values[i])).toBeGreaterThan(lum(values[i - 1]));
  });
});
