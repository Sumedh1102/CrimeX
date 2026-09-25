#!/usr/bin/env python
"""Generate versioned predictions for the forecast window starting at time.as_of.

Usage:
    python scripts/run_inference.py [--config configs/default.yaml] [--model-version V]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.config import load_config  # noqa: E402
from ml.inference.predict import generate_predictions, write_predictions  # noqa: E402
from ml.models.registry import ModelBundle  # noqa: E402
from ml.pipeline import load_inputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--model-version", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    bundle = ModelBundle.load(cfg.paths.artifacts_dir / "models", args.model_version)
    out = generate_predictions(load_inputs(cfg), bundle)
    path = write_predictions(out, cfg.paths.artifacts_dir / "predictions")
    m = out["manifest"]
    print(f"{m['data_label']}: predictions for {m['window_start']} .. {m['window_end']}")
    print(
        f"  model={m['model_version']} rows={m['counts']['predictions']} "
        f"surge_alerts={m['counts']['surge_alerts']} states={m['counts']['states']}"
    )
    print(f"  written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
