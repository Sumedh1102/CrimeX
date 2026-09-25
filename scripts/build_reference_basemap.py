"""Build the offline Mumbai reference basemap used when street-map tiles cannot load.

Clips OpenStreetMap-derived land and water-body polygons (the `geo-maps` project,
100 m resolution, ODbL) to the study area and writes compact GeoJSON files into
``frontend/public/geo/``. The frontend draws them under the zone grid so the map
still shows the real coastline, creeks and lakes of Mumbai without a network.

This is a one-off build step; its output is committed. Extra dependencies (not
needed by the platform itself): ``pip install shapely ijson``.

Download the sources first (from the npm registry):

    npm pack @geo-maps/earth-lands-100m@0.6.0 @geo-maps/earth-waterbodies-100m@0.6.0
    tar xzf geo-maps-earth-lands-100m-0.6.0.tgz  --one-top-level=lands
    tar xzf geo-maps-earth-waterbodies-100m-0.6.0.tgz --one-top-level=water

Then run:

    python scripts/build_reference_basemap.py lands/package/map.geo.json water/package/map.geo.json
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path

import ijson
import shapely
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union
from shapely.validation import make_valid

# Study-region bbox (configs/default.yaml) padded so the coastline beyond the grid
# (Mira-Bhayandar, Thane, Navi Mumbai) gives geographic context.
WEST, SOUTH, EAST, NORTH = 72.70, 18.84, 73.08, 19.33
SIMPLIFY_DEG = 0.00015  # ~16 m
PRECISION_DEG = 1e-5  # ~1 m

OUT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public" / "geo"
ATTRIBUTION = "© OpenStreetMap contributors (ODbL), via geo-maps 0.6.0 (100 m)"


def _bbox_hit(ring: list[list[float]]) -> bool:
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return not (max(xs) < WEST or min(xs) > EAST or max(ys) < SOUTH or min(ys) > NORTH)


def _polygons(geom: dict) -> Iterator[list]:
    kind = geom["type"]
    if kind == "Polygon":
        yield geom["coordinates"]
    elif kind == "MultiPolygon":
        yield from geom["coordinates"]
    elif kind == "GeometryCollection":
        for g in geom["geometries"]:
            yield from _polygons(g)


def clip(path: Path) -> shapely.Geometry:
    """Stream a (very large) GeometryCollection and keep only what falls in the bbox."""
    parts = []
    with path.open("rb") as f:
        for item in ijson.items(f, "geometries.item", use_float=True):
            for rings in _polygons(item):
                if not _bbox_hit(rings[0]):
                    continue
                holes = [r for r in rings[1:] if _bbox_hit(r)]
                # Rectangle clipping is robust to the source's minor self-intersections;
                # the small clipped result is then repaired.
                piece = shapely.clip_by_rect(Polygon(rings[0], holes), WEST, SOUTH, EAST, NORTH)
                if not piece.is_empty:
                    parts.append(make_valid(piece))
    merged = unary_union(parts).simplify(SIMPLIFY_DEG, preserve_topology=True)
    merged = shapely.set_precision(merged, PRECISION_DEG)
    parts = getattr(merged, "geoms", [merged])
    polys = [g for g in parts if g.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(polys)


def write(name: str, geom: shapely.Geometry) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    feature = {
        "type": "Feature",
        "properties": {"layer": name, "attribution": ATTRIBUTION},
        "geometry": mapping(geom),
    }
    out = OUT_DIR / f"mumbai-{name}.geojson"
    out.write_text(json.dumps(feature, separators=(",", ":")))
    size_kib = out.stat().st_size / 1024
    print(f"{out.relative_to(OUT_DIR.parents[2])}: {geom.geom_type}, {size_kib:.0f} KiB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("lands", type=Path, help="geo-maps earth-lands-100m map.geo.json")
    ap.add_argument("water", type=Path, help="geo-maps earth-waterbodies-100m map.geo.json")
    args = ap.parse_args()
    write("land", clip(args.lands))
    write("water", clip(args.water))


if __name__ == "__main__":
    main()
