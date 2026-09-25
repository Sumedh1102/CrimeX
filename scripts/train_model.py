#!/usr/bin/env python
"""Train, calibrate and evaluate the forecasting models; save a versioned bundle.

Usage:
    python scripts/train_model.py [--config configs/default.yaml]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.config import load_config  # noqa: E402
from ml.pipeline import load_inputs  # noqa: E402
from ml.training.train import train_models  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    cfg = load_config(args.config)
    inputs = load_inputs(cfg)
    bundle = train_models(inputs)
    path = bundle.save(cfg.paths.artifacts_dir / "models")
    print(f"saved {path}")
    test = bundle.metrics["test"]
    print(f"{'model (test period)':<28}{'PR-AUC':>8}{'ROC-AUC':>9}{'Brier':>9}{'top-K':>8}")
    for name, m in test.items():
        brier = f"{m['brier']:.4f}" if "brier" in m else "   -"
        print(
            f"{name:<28}{m['pr_auc']:>8.3f}{m['roc_auc']:>9.3f}{brier:>9}"
            f"{m['top_k']['capture_rate']:>8.3f}"
        )
    counts = bundle.metrics["test_counts"]
    for name, m in counts.items():
        print(f"{name:<28} MAE={m['mae']:.4f} RMSE={m['rmse']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
