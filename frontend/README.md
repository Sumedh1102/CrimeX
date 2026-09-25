# CrimeX frontend

Next.js (App Router) + TypeScript + Tailwind CSS v4, MapLibre GL v6, Recharts, Zustand, SWR,
Framer Motion. The UI only displays values from the FastAPI backend; it never re-derives
scores.

```bash
npm install
npm run dev        # http://localhost:3000 (expects the API on http://localhost:8000)
npm run lint && npm run typecheck
npm test           # vitest (src/**/*.test.ts)
npx vitest run src/lib/layers.test.ts -t "probability"   # a single test
npm run build
```

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `CRIMEX_API_URL` | `http://localhost:8000` | Where Next.js proxies `/api/v1/*` |
| `NEXT_PUBLIC_MAP_STYLE_URL` | unset | Extra vector style tried first (e.g. a keyed MapTiler/Stadia style), or `none` to force the offline reference map |

`scripts/copy-maplibre-worker.mjs` runs before `dev`/`build` and copies the MapLibre web
worker into `public/maplibre/` (MapLibre v6 resolves its worker relative to its own module
URL, which bundlers cannot follow).

Basemap (`src/lib/basemap.ts`): with "Auto" the map tries the custom style (if set), CARTO
Dark Matter (vector), OpenFreeMap Dark (vector) and CARTO Dark raster, in that order. Each
provider is probed with its style and one real tile over Mumbai before the map is created (6 s
overall deadline), and if street tiles fail at runtime the map switches in place to the
offline reference map: OSM-derived coastline, creeks and lakes bundled in `public/geo/`
(built by `scripts/build_reference_basemap.py`) with approximate locality labels
(`src/lib/localities.ts`). The chip at the map's top-left says which basemap is in use,
offers Retry, and lets the viewer pick a provider.

Color ramps in `src/lib/colors.ts` were validated for the dark surface with the dataviz
palette validator; every map layer also encodes meaning with labels, icons or texture.
