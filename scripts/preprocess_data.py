#!/usr/bin/env python
"""Run data quality checks and gridding on raw incidents -> data/processed/.

Usage:
    python scripts/preprocess_data.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.config import load_config  # noqa: E402
from ml.preprocessing.pipeline import preprocess  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    out = preprocess(cfg)
    m, q = out["manifest"], out["quality"]
    print(f"{m['data_label']}: {m['dataset_version']}")
    print(f"  rows in={q['rows_in']} out={q['rows_out']} rejected={q['rows_rejected']}")
    for c in q["checks"]:
        if c["rows_with_issue"]:
            print(
                f"  {c['label']:<55} {c['rows_with_issue']:>6} ({100 * c['rate']:.2f}%) "
                f"-> {c['action']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
