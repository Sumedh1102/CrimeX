import type { NextConfig } from "next";

// The browser talks to /api/v1/* on the Next.js origin; Next proxies it to FastAPI.
const API_URL = process.env.CRIMEX_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${API_URL}/api/v1/:path*` }];
  },
};

export default nextConfig;
