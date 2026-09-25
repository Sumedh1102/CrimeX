#!/usr/bin/env python
"""Run the whole pipeline: synthetic data -> quality/gridding -> training -> predictions.

Usage:
    python scripts/run_pipeline.py [--config configs/default.yaml] [--skip-data]
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
from ml.inference.predict import generate_predictions, write_predictions  # noqa: E402
from ml.pipeline import load_inputs  # noqa: E402
from ml.preprocessing.grid import Grid  # noqa: E402
from ml.preprocessing.pipeline import preprocess  # noqa: E402
from ml.training.train import train_models  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--skip-data", action="store_true", help="reuse data/raw")
    args = parser.parse_args()
    cfg = load_config(args.config)
    t0 = time.time()

    if not args.skip_data:
        grid = Grid.build(cfg.region, cfg.grid)
        stmt = OfficialStatement.load(cfg.paths.official_statement)
        write_outputs(SyntheticGenerator(cfg, grid, stmt).generate(), cfg.paths.raw_dir)
        print(f"[{time.time() - t0:5.0f}s] synthetic data generated (SYNTHETIC / DEMONSTRATION)")
    pre = preprocess(cfg)
    print(f"[{time.time() - t0:5.0f}s] preprocessed: {pre['manifest']['dataset_version']}")
    inputs = load_inputs(cfg)
    bundle = train_models(inputs, log=lambda m: print(f"[{time.time() - t0:5.0f}s]   {m}"))
    bundle.save(cfg.paths.artifacts_dir / "models")
    out = generate_predictions(inputs, bundle)
    path = write_predictions(out, cfg.paths.artifacts_dir / "predictions")
    print(f"[{time.time() - t0:5.0f}s] predictions written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
