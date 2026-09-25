import type { Metadata } from "next";
import { Sidebar } from "@/components/shell/Sidebar";
import { LimitationFooter, TopBar } from "@/components/shell/TopBar";
import { ZonePanelHost } from "@/components/zone/ZonePanel";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "CrimeX · AI Crime Intelligence",
  description:
    "Explainable spatiotemporal crime-intelligence platform for police-station decision support (zone level).",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex h-full min-h-0 overflow-hidden">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
          <LimitationFooter />
        </div>
        <ZonePanelHost />
      </body>
    </html>
  );
}
