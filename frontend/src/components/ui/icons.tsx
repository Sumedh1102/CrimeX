import type { HotspotState } from "@/lib/types";

/** Shape per hotspot state, so state never depends on color alone. */
export function StateIcon({
  state,
  color,
  size = 14,
}: {
  state: HotspotState;
  color: string;
  size?: number;
}) {
  const common = { width: size, height: size, viewBox: "0 0 16 16", "aria-hidden": true as const };
  switch (state) {
    case "EMERGING":
      return (
        <svg {...common}>
          <path d="M8 2 14.5 13.5h-13L8 2Z" fill={color} />
        </svg>
      );
    case "ACTIVE":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6" fill={color} />
        </svg>
      );
    case "PERSISTENT":
      return (
        <svg {...common}>
          <rect x="2.5" y="2.5" width="11" height="11" rx="1.5" fill={color} />
        </svg>
      );
    case "DECLINING":
      return (
        <svg {...common}>
          <path d="M8 14 1.5 2.5h13L8 14Z" fill={color} />
        </svg>
      );
    case "SPORADIC":
      return (
        <svg {...common}>
          <path d="M8 1.8 14.2 8 8 14.2 1.8 8 8 1.8Z" fill="none" stroke={color} strokeWidth="2" />
        </svg>
      );
    case "STABLE":
      return (
        <svg {...common}>
          <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
  }
}

export function AlertIcon({ size = 14, color = "#86b6ef" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden>
      <circle cx="8" cy="8" r="7" fill={color} />
      <path d="M8 4v5" stroke="#0d0d0d" strokeWidth="2" strokeLinecap="round" />
      <circle cx="8" cy="11.8" r="1.1" fill="#0d0d0d" />
    </svg>
  );
}

export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  const p = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true as const };
  switch (name) {
    case "dashboard":
      return (<svg {...p}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></svg>);
    case "map":
      return (<svg {...p}><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Z" /><path d="M9 4v14M15 6v14" /></svg>);
    case "stations":
      return (<svg {...p}><path d="M4 21V9l8-5 8 5v12" /><path d="M9 21v-6h6v6M3 21h18" /></svg>);
    case "predictions":
      return (<svg {...p}><path d="M4 19h16" /><path d="M6 15l4-5 3 3 5-7" /></svg>);
    case "hotspots":
      return (<svg {...p}><circle cx="12" cy="12" r="3" /><circle cx="12" cy="12" r="7" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>);
    case "anomalies":
      return (<svg {...p}><path d="M3 12h4l2-6 4 12 2-6h6" /></svg>);
    case "crime-types":
      return (<svg {...p}><path d="M4 6h16M4 12h16M4 18h10" /></svg>);
    case "official":
      return (<svg {...p}><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></svg>);
    case "model":
      return (<svg {...p}><circle cx="6" cy="6" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="12" cy="18" r="2" /><path d="M7.5 7.5 11 16M16.5 7.5 13 16M8 6h8" /></svg>);
    case "data":
      return (<svg {...p}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></svg>);
    case "menu":
      return (<svg {...p}><path d="M4 7h16M4 12h16M4 17h16" /></svg>);
    case "close":
      return (<svg {...p}><path d="M6 6l12 12M18 6 6 18" /></svg>);
    case "info":
      return (<svg {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>);
    case "table":
      return (<svg {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M9 10v10" /></svg>);
    case "chart":
      return (<svg {...p}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg>);
    default:
      return null;
  }
}
