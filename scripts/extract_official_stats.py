#!/usr/bin/env python
"""Extract the official Brihan Mumbai statement PDF into validated JSON.

Usage:
    python scripts/extract_official_stats.py \
        --pdf data/official/MumbaiCrime2026data.pdf \
        --out data/official/mumbai_police_statement_2026-08.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.data.official.extract import extract_statement  # noqa: E402
from ml.data.official.validate import SOURCE_NOTES, run_checks, summarise  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", default=ROOT / "data/official/MumbaiCrime2026data.pdf")
    parser.add_argument(
        "--out", default=ROOT / "data/official/mumbai_police_statement_2026-08.json"
    )
    args = parser.parse_args()

    doc = extract_statement(args.pdf)
    checks = run_checks(doc)
    doc["checks"] = checks
    doc["checks_summary"] = summarise(checks)
    doc["source_notes"] = SOURCE_NOTES

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    s = doc["checks_summary"]
    print(f"Wrote {out} ({len(doc['values'])} values, {len(doc['heads'])} heads)")
    print(f"Checks: {s['passed']}/{s['total']} passed, {s['discrepancies']} discrepancies")
    for ch in checks:
        if ch["status"] != "pass":
            print(f"  DISCREPANCY {ch['id']}: expected {ch['expected']}, printed {ch['observed']}")
    for note in doc["extraction_notes"]:
        print(f"  note: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
