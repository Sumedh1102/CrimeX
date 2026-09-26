const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  return Math.round(n).toLocaleString("en-IN");
}

export function fmtNum(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  return n.toFixed(digits);
}

/** Probability as a percentage; tiny values are shown as "< 0.1%". */
export function fmtPct(p: number | null | undefined): string {
  if (p === null || p === undefined || Number.isNaN(p)) return "–";
  const v = p * 100;
  if (v > 0 && v < 0.1) return "< 0.1%";
  return `${v < 10 ? v.toFixed(1) : Math.round(v)}%`;
}

export function fmtSignedPct(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const r = Math.round(v);
  return `${r > 0 ? "+" : ""}${r}%`;
}

function parseDate(iso: string): Date {
  // Treat date-only and naive timestamps as local calendar values.
  const [d, t = "00:00:00"] = iso.replace("Z", "").split("T");
  const [y, m, day] = d.split("-").map(Number);
  const [hh, mm] = t.split(":").map(Number);
  return new Date(y, m - 1, day, hh || 0, mm || 0);
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = parseDate(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = parseDate(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${fmtDate(iso)} ${hh}:${mm}`;
}

/** A window [start, end) displayed with an inclusive end date, e.g. "1–7 Sep 2026". */
export function fmtWindow(start: string, end: string): string {
  const s = parseDate(start);
  const e = parseDate(end);
  e.setDate(e.getDate() - 1);
  if (s.getMonth() === e.getMonth() && s.getFullYear() === e.getFullYear()) {
    return `${s.getDate()}–${e.getDate()} ${MONTHS[e.getMonth()]} ${e.getFullYear()}`;
  }
  return `${s.getDate()} ${MONTHS[s.getMonth()]} – ${e.getDate()} ${MONTHS[e.getMonth()]} ${e.getFullYear()}`;
}

export function fmtWeek(iso: string): string {
  const d = parseDate(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export function titleCase(s: string): string {
  return s
    .toLowerCase()
    .split(/[\s_]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function compact(n: number): string {
  if (Math.abs(n) >= 1e7) return `${(n / 1e7).toFixed(1)} Cr`;
  if (Math.abs(n) >= 1e5) return `${(n / 1e5).toFixed(1)} L`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

/** "next 7 days" / "next 24 hours" for a forecast window of ``days`` days. */
export function fmtNextWindow(days: number): string {
  return days === 1 ? "next 24 hours" : `next ${days} days`;
}

/** Name of one panel window: "day", "week" or "N-day window". */
export function windowUnit(days: number): string {
  return days === 1 ? "day" : days === 7 ? "week" : `${days}-day window`;
}
