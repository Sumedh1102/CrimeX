#!/usr/bin/env python
"""Generate the SYNTHETIC / DEMONSTRATION incident dataset.

Usage:
    python scripts/generate_synthetic_data.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.config import load_config  # noqa: E402
from ml.data.official.load import OfficialStatement  # noqa: E402
from ml.data.synthetic import SyntheticGenerator, write_outputs  # noqa: E402
from ml.preprocessing.grid import Grid  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    t0 = time.time()
    cfg = load_config(args.config)
    grid = Grid.build(cfg.region, cfg.grid)
    stmt = OfficialStatement.load(cfg.paths.official_statement)
    result = SyntheticGenerator(cfg, grid, stmt).generate()
    write_outputs(result, cfg.paths.raw_dir)

    s = result["summary"]
    print(f"SYNTHETIC / DEMONSTRATION DATA written to {cfg.paths.raw_dir}")
    print(
        f"  zones={s['n_zones']} incidents={s['n_incidents_clean']} "
        f"published_rows={s['n_rows_published']} ({time.time() - t0:.1f}s)"
    )
    print(f"  injected defects: {s['injected_defects']}")
    print("  anchoring (official registered vs synthetic generated):")
    for row in s["anchoring"]:
        o, g = row["official_registered"], row["synthetic_generated"]
        print(
            f"    {row['crime_type']:<24} "
            + "  ".join(f"{k}: {o[k]:>5} vs {g[k]:>5}" for k in ("PY", "CY", "PM", "CM"))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
