// Canvas-drawn images registered with MapLibre: state icons, the surge-alert icon,
// 45/135-degree textures, and value labels. Drawing labels as images keeps them
// working with the offline fallback style, which has no font glyphs.
import { REFERENCE_COLORS } from "@/lib/basemap";
import { CHROME, RISK_COLORS, STATE_STYLE, TEXTURE_INK } from "@/lib/colors";
import type { HotspotState } from "@/lib/types";

const PR = 2; // pixel ratio for crisp images

export interface MapImage {
  width: number;
  height: number;
  data: Uint8ClampedArray;
}

function canvas(w: number, h: number) {
  const c = document.createElement("canvas");
  c.width = w * PR;
  c.height = h * PR;
  const ctx = c.getContext("2d")!;
  ctx.scale(PR, PR);
  return { c, ctx };
}

function toImage(c: HTMLCanvasElement): MapImage {
  const ctx = c.getContext("2d")!;
  const d = ctx.getImageData(0, 0, c.width, c.height);
  return { width: c.width, height: c.height, data: d.data };
}

function shapePath(ctx: CanvasRenderingContext2D, state: HotspotState, s: number) {
  const m = s / 2;
  ctx.beginPath();
  switch (state) {
    case "EMERGING":
      ctx.moveTo(m, 2.5);
      ctx.lineTo(s - 2, s - 3);
      ctx.lineTo(2, s - 3);
      break;
    case "ACTIVE":
      ctx.arc(m, m, m - 3, 0, Math.PI * 2);
      break;
    case "PERSISTENT":
      ctx.rect(3.5, 3.5, s - 7, s - 7);
      break;
    case "DECLINING":
      ctx.moveTo(m, s - 2.5);
      ctx.lineTo(s - 2, 3);
      ctx.lineTo(2, 3);
      break;
    case "SPORADIC":
      ctx.moveTo(m, 2.5);
      ctx.lineTo(s - 2.5, m);
      ctx.lineTo(m, s - 2.5);
      ctx.lineTo(2.5, m);
      break;
    default:
      break;
  }
  ctx.closePath();
}

export function stateIcon(state: HotspotState): MapImage {
  const s = 18;
  const { c, ctx } = canvas(s, s);
  const color = state === "DECLINING" || state === "SPORADIC" ? CHROME.ink2 : STATE_STYLE[state].color!;
  // 2px surface ring keeps the mark legible over any fill
  shapePath(ctx, state, s);
  ctx.lineWidth = 3;
  ctx.strokeStyle = CHROME.plane;
  ctx.lineJoin = "round";
  ctx.stroke();
  shapePath(ctx, state, s);
  if (state === "SPORADIC") {
    ctx.lineWidth = 1.8;
    ctx.strokeStyle = color;
    ctx.stroke();
  } else {
    ctx.fillStyle = color;
    ctx.fill();
  }
  return toImage(c);
}

export function alertIcon(): MapImage {
  const s = 18;
  const { c, ctx } = canvas(s, s);
  ctx.beginPath();
  ctx.arc(s / 2, s / 2, s / 2 - 1.5, 0, Math.PI * 2);
  ctx.fillStyle = "#86b6ef";
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = CHROME.plane;
  ctx.stroke();
  ctx.fillStyle = CHROME.plane;
  ctx.fillRect(s / 2 - 1, 4.5, 2, 6);
  ctx.beginPath();
  ctx.arc(s / 2, 13, 1.2, 0, Math.PI * 2);
  ctx.fill();
  return toImage(c);
}

/** Tone-on-tone line texture at 45 degrees (and 135 degrees for the cross variant). */
export function texture(ink: string, cross: boolean): MapImage {
  const s = 10;
  const { c, ctx } = canvas(s, s);
  ctx.strokeStyle = ink;
  ctx.lineWidth = 1.3;
  ctx.lineCap = "square";
  const diag = (flip: boolean) => {
    ctx.beginPath();
    for (const o of [-s, 0, s]) {
      if (flip) {
        ctx.moveTo(o, 0);
        ctx.lineTo(o + s, s);
      } else {
        ctx.moveTo(o, s);
        ctx.lineTo(o + s, 0);
      }
    }
    ctx.stroke();
  };
  diag(false);
  if (cross) diag(true);
  return toImage(c);
}

export const TEXTURES: Record<string, () => MapImage> = {
  "tex-risk-high": () => texture(TEXTURE_INK.riskHigh, false),
  "tex-risk-veryhigh": () => texture(TEXTURE_INK.riskVeryHigh, true),
  "tex-persistent": () => texture(TEXTURE_INK.persistent, false),
};

/**
 * Attention marker for zones in the HIGH / VERY HIGH risk bands: an ink ring (filled
 * centre for VERY HIGH) with a dark halo, so the mark reads on any fill and is a second,
 * non-colour cue for the top bands.
 */
export function riskMarker(veryHigh: boolean): MapImage {
  const s = 20;
  const { c, ctx } = canvas(s, s);
  const m = s / 2;
  ctx.beginPath();
  ctx.arc(m, m, 6.5, 0, Math.PI * 2);
  ctx.lineWidth = 4.5;
  ctx.strokeStyle = CHROME.plane;
  ctx.stroke();
  ctx.lineWidth = 2;
  ctx.strokeStyle = CHROME.ink;
  ctx.stroke();
  if (veryHigh) {
    ctx.beginPath();
    ctx.arc(m, m, 3, 0, Math.PI * 2);
    ctx.fillStyle = CHROME.ink;
    ctx.fill();
  } else {
    ctx.beginPath();
    ctx.arc(m, m, 2.2, 0, Math.PI * 2);
    ctx.fillStyle = RISK_COLORS.HIGH;
    ctx.fill();
  }
  return toImage(c);
}

/**
 * Hotspot movement markers in ink on a dark halo (shape carries the meaning):
 * arrow = shifted (drawn pointing north, rotated to the bearing on the map),
 * ring = continued in place, plus = new cluster, cross = dissipated.
 */
export function movementIcon(kind: "arrow" | "hold" | "new" | "gone"): MapImage {
  const s = 20;
  const m = s / 2;
  const { c, ctx } = canvas(s, s);
  const stroke = (width: number, color: string) => {
    ctx.lineWidth = width;
    ctx.strokeStyle = color;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.stroke();
  };
  ctx.beginPath();
  if (kind === "arrow") {
    ctx.moveTo(m, 2.5);
    ctx.lineTo(s - 4, s - 4);
    ctx.lineTo(m, s - 7);
    ctx.lineTo(4, s - 4);
    ctx.closePath();
    stroke(3.5, CHROME.plane);
    ctx.fillStyle = CHROME.ink;
    ctx.fill();
    return toImage(c);
  }
  if (kind === "hold") {
    ctx.arc(m, m, 5.5, 0, Math.PI * 2);
    stroke(4.5, CHROME.plane);
    stroke(1.8, CHROME.ink);
    return toImage(c);
  }
  ctx.arc(m, m, 7, 0, Math.PI * 2);
  ctx.fillStyle = CHROME.plane;
  ctx.fill();
  stroke(1.4, CHROME.ink);
  ctx.beginPath();
  if (kind === "new") {
    ctx.moveTo(m, m - 3.5);
    ctx.lineTo(m, m + 3.5);
    ctx.moveTo(m - 3.5, m);
    ctx.lineTo(m + 3.5, m);
  } else {
    ctx.moveTo(m - 2.8, m - 2.8);
    ctx.lineTo(m + 2.8, m + 2.8);
    ctx.moveTo(m + 2.8, m - 2.8);
    ctx.lineTo(m - 2.8, m + 2.8);
  }
  stroke(1.8, CHROME.ink);
  return toImage(c);
}

export const ICONS: Record<string, () => MapImage> = {
  "move-arrow": () => movementIcon("arrow"),
  "move-hold": () => movementIcon("hold"),
  "move-new": () => movementIcon("new"),
  "move-gone": () => movementIcon("gone"),
  "risk-high": () => riskMarker(false),
  "risk-veryhigh": () => riskMarker(true),
  "state-emerging": () => stateIcon("EMERGING"),
  "state-active": () => stateIcon("ACTIVE"),
  "state-persistent": () => stateIcon("PERSISTENT"),
  "state-declining": () => stateIcon("DECLINING"),
  "state-sporadic": () => stateIcon("SPORADIC"),
  alert: () => alertIcon(),
};

/** Value label image for ids like "lbl:74". White text with a dark halo. */
export function labelImage(text: string): MapImage {
  const font = "600 11px system-ui, -apple-system, 'Segoe UI', sans-serif";
  const probe = document.createElement("canvas").getContext("2d")!;
  probe.font = font;
  const w = Math.ceil(probe.measureText(text).width) + 8;
  const h = 16;
  const { c, ctx } = canvas(w, h);
  ctx.font = font;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(13,13,13,0.85)";
  ctx.strokeText(text, w / 2, h / 2 + 0.5);
  ctx.fillStyle = CHROME.ink;
  ctx.fillText(text, w / 2, h / 2 + 0.5);
  return toImage(c);
}

/**
 * Offline reference labels for ids like "ref:place:Andheri". Places in secondary ink,
 * water names in italic blue-grey, areas outside the study region in muted ink.
 */
export function referenceLabelImage(id: string): MapImage {
  const [, kind, ...rest] = id.split(":");
  const text = rest.join(":");
  const font =
    kind === "water"
      ? "italic 500 11px system-ui, -apple-system, 'Segoe UI', sans-serif"
      : kind === "context"
        ? "500 10px system-ui, -apple-system, 'Segoe UI', sans-serif"
        : "600 10.5px system-ui, -apple-system, 'Segoe UI', sans-serif";
  const color = kind === "water" ? REFERENCE_COLORS.waterLabel : kind === "context" ? CHROME.muted : REFERENCE_COLORS.label;
  const probe = document.createElement("canvas").getContext("2d")!;
  probe.font = font;
  const label = kind === "context" ? text.toUpperCase() : text;
  const w = Math.ceil(probe.measureText(label).width) + 8;
  const h = 16;
  const { c, ctx } = canvas(w, h);
  ctx.font = font;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(13,13,13,0.9)";
  ctx.strokeText(label, w / 2, h / 2 + 0.5);
  ctx.fillStyle = color;
  ctx.fillText(label, w / 2, h / 2 + 0.5);
  return toImage(c);
}

export const PIXEL_RATIO = PR;
