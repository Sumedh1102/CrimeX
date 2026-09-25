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
| `NEXT_PUBLIC_MAP_STYLE_URL` | CARTO Dark Matter | Basemap style URL, or `none` for the offline grid-only style |

`scripts/copy-maplibre-worker.mjs` runs before `dev`/`build` and copies the MapLibre web
worker into `public/maplibre/` (MapLibre v6 resolves its worker relative to its own module
URL, which bundlers cannot follow).

Color ramps in `src/lib/colors.ts` were validated for the dark surface with the dataviz
palette validator; every map layer also encodes meaning with labels, icons or texture.
