"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { Icon } from "@/components/ui/icons";
import { useUI } from "@/lib/store";

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

export function Logo() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2 px-2">
      <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden>
        <rect x="2" y="2" width="9" height="9" rx="2" fill="#3987e5" />
        <rect x="13" y="2" width="9" height="9" rx="2" fill="#222220" stroke="#383835" />
        <rect x="2" y="13" width="9" height="9" rx="2" fill="#222220" stroke="#383835" />
        <rect x="13" y="13" width="9" height="9" rx="2" fill="#ef8234" />
      </svg>
      <span className="text-[15px] font-semibold tracking-tight text-ink">CrimeX</span>
    </Link>
  );
}

function NavList() {
  const path = usePathname();
  return (
    <ul className="flex flex-col gap-0.5">
      {NAV.map((n) => {
        const active = path === n.href || path.startsWith(n.href + "/");
        return (
          <li key={n.href}>
            <Link
              href={n.href}
              aria-current={active ? "page" : undefined}
              className={clsx(
                "flex items-center gap-2.5 rounded-md px-2 py-2 text-[13px] transition-colors lg:py-1.5",
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
  );
}

const FOOTNOTE = "Decision support at zone level only. No individual-level profiling.";

/** Fixed rail on large screens; a slide-in drawer (opened from the top bar) below that. */
export function Sidebar() {
  const path = usePathname();
  const navOpen = useUI((s) => s.navOpen);
  const set = useUI((s) => s.set);

  // Close the drawer after navigating, and on Escape.
  useEffect(() => {
    set({ navOpen: false });
  }, [path, set]);
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && set({ navOpen: false });
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen, set]);

  return (
    <>
      <nav
        aria-label="Main"
        className="hidden w-[196px] shrink-0 flex-col border-r bg-plane px-3 py-4 lg:flex"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="mb-6">
          <Logo />
        </div>
        <NavList />
        <p className="mt-auto px-2 text-[10px] leading-snug text-muted">{FOOTNOTE}</p>
      </nav>
      {navOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/60"
            onClick={() => set({ navOpen: false })}
          />
          <nav
            aria-label="Main"
            id="mobile-nav"
            className="absolute inset-y-0 left-0 flex w-[260px] max-w-[85vw] flex-col border-r bg-plane px-3 py-4 shadow-2xl"
            style={{ borderColor: "var(--border-strong)" }}
          >
            <div className="mb-5 flex items-center justify-between">
              <Logo />
              <button
                type="button"
                onClick={() => set({ navOpen: false })}
                className="rounded p-1.5 text-muted hover:bg-surface hover:text-ink"
                aria-label="Close navigation"
              >
                <Icon name="close" />
              </button>
            </div>
            <NavList />
            <p className="mt-auto px-2 text-[11px] leading-snug text-muted">{FOOTNOTE}</p>
          </nav>
        </div>
      )}
    </>
  );
}
