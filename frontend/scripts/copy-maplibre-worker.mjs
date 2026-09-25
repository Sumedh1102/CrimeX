// MapLibre GL v6 loads its web worker from a URL next to its module file, which a
// bundler cannot follow. Copy the worker (and the chunk it imports) into public/ so
// the app can point MapLibre at /maplibre/maplibre-gl-worker.mjs.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dist = dirname(require.resolve("maplibre-gl/package.json")) + "/dist";
const out = join(process.cwd(), "public", "maplibre");
mkdirSync(out, { recursive: true });
for (const f of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(dist, f), join(out, f));
}
console.log(`copied MapLibre worker to ${out}`);
