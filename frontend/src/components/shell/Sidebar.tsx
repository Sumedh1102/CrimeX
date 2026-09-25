"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/ui/icons";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { href: "/map", label: "Map", icon: "map" },
  { href: "/predictions", label: "Predictions", icon: "predictions" },
  { href: "/hotspots", label: "Hotspots", icon: "hotspots" },
  { href: "/anomalies", label: "Anomalies", icon: "anomalies" },
  { href: "/crime-types", label: "Crime types", icon: "crime-types" },
  { href: "/official", label: "Official statistics", icon: "official" },
  { href: "/model", label: "Model", icon: "model" },
  { href: "/data", label: "Data quality", icon: "data" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <nav
      aria-label="Main"
      className="flex w-[196px] shrink-0 flex-col border-r bg-plane px-3 py-4"
      style={{ borderColor: "var(--border)" }}
    >
      <Link href="/dashboard" className="mb-6 flex items-center gap-2 px-2">
        <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden>
          <rect x="2" y="2" width="9" height="9" rx="2" fill="#3987e5" />
          <rect x="13" y="2" width="9" height="9" rx="2" fill="#222220" stroke="#383835" />
          <rect x="2" y="13" width="9" height="9" rx="2" fill="#222220" stroke="#383835" />
          <rect x="13" y="13" width="9" height="9" rx="2" fill="#ef8234" />
        </svg>
        <span className="text-[15px] font-semibold tracking-tight text-ink">CrimeX</span>
      </Link>
      <ul className="flex flex-col gap-0.5">
        {NAV.map((n) => {
          const active = path === n.href || path.startsWith(n.href + "/");
          return (
            <li key={n.href}>
              <Link
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={clsx(
                  "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] transition-colors",
                  active ? "bg-surface-2 text-ink" : "text-muted hover:bg-surface hover:text-ink-2",
                )}
              >
                <Icon name={n.icon} />
                {n.label}
              </Link>
            </li>
          );
        })}
      </ul>
      <p className="mt-auto px-2 text-[10px] leading-snug text-muted">
        Decision support at zone level only. No individual-level profiling.
      </p>
    </nav>
  );
}
