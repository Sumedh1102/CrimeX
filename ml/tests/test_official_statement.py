"""The extracted official statement must match the source PDF exactly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ml.data.official.load import DEFAULT_STATEMENT, OfficialStatement
from ml.data.official.validate import run_checks

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "data" / "official" / "MumbaiCrime2026data.pdf"


@pytest.fixture(scope="module")
def stmt() -> OfficialStatement:
    return OfficialStatement.load()


def test_periods(stmt):
    assert stmt.periods["CM"]["start"] == "2026-08-01"
    assert stmt.periods["CM"]["end"] == "2026-08-31"
    assert stmt.periods["PM"]["start"] == "2026-07-01"
    assert stmt.periods["CY"]["start"] == "2026-01-01"
    assert stmt.periods["PY"] == {
        "label": "Previous Year (same period)",
        "start": "2025-01-01",
        "end": "2025-08-31",
        "law_label_as_printed": None,
    }


@pytest.mark.parametrize(
    ("section", "head", "period", "metric", "expected"),
    [
        ("IPC", "MURDER", "CM", "registered", 16),
        ("IPC", "ROBBERY_CHAIN_SNATCHING", "CY", "registered", 70),
        ("IPC", "THEFT", "CY", "detection_pct", 42),
        ("IPC", "MV_THEFT", "CY_VS_PY", "difference_registered", 272),
        ("IPC", "THEFT", "CY_VS_PY", "difference_registered", -882),
        ("IPC", "SEXUAL_OFFENCES_SEC69", "CM", "registered", 25),  # repaired overflow cell
        ("IPC", "TOTAL_IPC", "CY", "registered", 55471),
        ("CAW", "CAW_KIDNAPPING_MAJOR", "PM", "registered", None),  # blank in source
        ("CAW", "CAW_TOTAL", "CY", "registered", 4354),
        ("NDPS", "NDPS_MD", "CM", "value", 1665310035),
        ("NDPS", "NDPS_TOTAL", "CM", "cases", 5552),
        ("BROTHELS", "BROTHEL_ACCUSED_ARRESTED", "PY", "count", 66),
        ("EOW", "EOW_CASES", "CY", "property_involved_rs", 54852628884),
        ("CYBER", "CYBER_CHEATING_GOVT_OFFICIAL", "CM", "registered", 95),  # merged row
        ("CYBER", "CYBER_TOTAL", "CM", "pa", 794),
    ],
)
def test_spot_values(stmt, section, head, period, metric, expected):
    assert stmt.value(section, head, period, metric) == expected


def test_official_terminology_is_preserved(stmt):
    assert stmt.heads["HBT_DAY"]["label_official"] == "H.B.T.Day"
    assert stmt.heads["HBT_DAY"]["label"] == "House Breaking Theft - Day"
    assert stmt.heads["ROBBERY_CHAIN_SNATCHING"]["label"] == "Robbery Chain Snatching"


def test_ipc_table_reconciles(stmt):
    checks = run_checks(stmt.doc)
    ipc = [c for c in checks if c["section"] == "IPC"]
    assert ipc and all(c["status"] == "pass" for c in ipc)


def test_discrepancies_are_exactly_the_known_source_inconsistencies(stmt):
    failing = {c["id"] for c in run_checks(stmt.doc) if c["status"] != "pass"}
    expected = {
        *(f"CROSS.RAPE.{p}.{m}" for p in ("CY", "PY") for m in ("registered", "detected")),
        "CROSS.MOLESTATION.PM.registered",
        "CROSS.MOLESTATION.PM.detected",
        "CROSS.MOLESTATION.CY.registered",
        "CROSS.MOLESTATION.PY.registered",
        "CROSS.MOLESTATION.PY.detected",
        *(
            f"CAW.total.{p}.{m}"
            for p in ("CM", "PM", "CY", "PY")
            for m in ("registered", "detected")
        ),
        "NDPS.possession.quantity_kg_excl_cough_syrup",
        "EOW.difference",
    }
    assert failing == expected


def test_committed_json_is_reproducible_from_pdf(stmt):
    pytest.importorskip("pdfplumber")
    from ml.data.official.extract import extract_statement

    fresh = extract_statement(PDF)
    assert fresh["report"]["source_sha256"] == stmt.doc["report"]["source_sha256"]
    assert fresh["values"] == stmt.doc["values"]
    assert fresh["heads"] == stmt.doc["heads"]


def test_default_statement_path_exists():
    assert DEFAULT_STATEMENT.exists()
    json.loads(DEFAULT_STATEMENT.read_text(encoding="utf-8"))
