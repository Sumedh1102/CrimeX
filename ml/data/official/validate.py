"""Consistency checks for the extracted official statement.

Checks never modify values. A failed check becomes a *discrepancy* entry that is
shown alongside the data, so users see exactly where the source disagrees with
itself. Blank cells are treated as 0 only inside sums, and that is stated in the
check description.
"""

from __future__ import annotations

from typing import Any

Key = tuple[str, str, str, str]


def _index(values: list[dict[str, Any]]) -> dict[Key, int | float | None]:
    return {(v["section"], v["head"], v["period"], v["metric"]): v["value"] for v in values}


def _z(x):
    return 0 if x is None else x


class _Checker:
    def __init__(self, values: list[dict[str, Any]]):
        self.v = _index(values)
        self.checks: list[dict[str, Any]] = []

    def get(self, section, head, period, metric):
        return self.v.get((section, head, period, metric))

    def record(self, check_id, section, description, expected, observed, tol=0.0):
        ok = (
            expected is not None
            and observed is not None
            and abs(float(expected) - float(observed)) <= tol
        )
        self.checks.append(
            {
                "id": check_id,
                "section": section,
                "description": description,
                "expected": expected,
                "observed": observed,
                "status": "pass" if ok else "discrepancy",
            }
        )

    def sum_check(self, check_id, section, parts, total, period, metric, what):
        s = sum(_z(self.get(section, h, period, metric)) for h in parts)
        t = self.get(section, total, period, metric)
        s = round(s, 6)
        self.record(
            check_id,
            section,
            f"{what}: sum of components equals printed {total} ({period} {metric}; "
            "blank cells counted as 0)",
            s,
            t,
            tol=1e-6,
        )


REG_DET_PERIODS = (
    ("CM", "registered"),
    ("CM", "detected"),
    ("PM", "registered"),
    ("PM", "detected"),
    ("CY", "registered"),
    ("CY", "detected"),
    ("PY", "registered"),
    ("PY", "detected"),
)


def _detection_pct_checks(c: _Checker, section: str, heads: list[str]) -> None:
    for head in heads:
        for period in ("CY", "PY"):
            reg = c.get(section, head, period, "registered")
            det = c.get(section, head, period, "detected")
            pct = c.get(section, head, period, "detection_pct")
            if pct is None or not reg:
                continue
            c.record(
                f"{section}.{head}.{period}.detection_pct",
                section,
                f"{head} {period}: printed detection % matches 100*detected/registered "
                "(within rounding)",
                round(100.0 * _z(det) / reg, 1),
                pct,
                tol=0.5 + 1e-9,
            )


def run_checks(doc: dict[str, Any]) -> list[dict[str, Any]]:
    c = _Checker(doc["values"])
    heads_by_section: dict[str, list[dict[str, Any]]] = {}
    for h in doc["heads"]:
        heads_by_section.setdefault(h["section"], []).append(h)

    # IPC -------------------------------------------------------------------------
    ipc_parts = [h["code"] for h in heads_by_section["IPC"] if not h["is_aggregate"]]
    for period, metric in REG_DET_PERIODS:
        c.sum_check(
            f"IPC.total.{period}.{metric}",
            "IPC",
            ipc_parts,
            "TOTAL_IPC",
            period,
            metric,
            "Total IPC",
        )
    for head in [*ipc_parts, "TOTAL_IPC"]:
        cy = c.get("IPC", head, "CY", "registered")
        py = c.get("IPC", head, "PY", "registered")
        c.record(
            f"IPC.{head}.difference",
            "IPC",
            f"{head}: printed difference equals current-year minus previous-year registrations",
            None if cy is None or py is None else cy - py,
            c.get("IPC", head, "CY_VS_PY", "difference_registered"),
        )
    _detection_pct_checks(c, "IPC", [*ipc_parts, "TOTAL_IPC"])

    # Crime against women ---------------------------------------------------------
    for period, metric in REG_DET_PERIODS:
        c.sum_check(
            f"CAW.rape_total.{period}.{metric}",
            "CAW",
            ["CAW_RAPE_POCSO_MINOR", "CAW_RAPE_MAJOR"],
            "CAW_RAPE_TOTAL",
            period,
            metric,
            "Total Rape Cases",
        )
        c.sum_check(
            f"CAW.kidnapping_total.{period}.{metric}",
            "CAW",
            ["CAW_KIDNAPPING_MINOR", "CAW_KIDNAPPING_MAJOR"],
            "CAW_KIDNAPPING_TOTAL",
            period,
            metric,
            "Total Kidnapping Cases",
        )
    _detection_pct_checks(c, "CAW", [h["code"] for h in heads_by_section["CAW"]])

    # Cross-table: the same head printed in the IPC and CAW tables.
    for ipc_head, caw_head in (
        ("RAPE", "CAW_RAPE_TOTAL"),
        ("SEXUAL_OFFENCES_SEC69", "CAW_SEXUAL_OFFENCES_SEC69"),
        ("MOLESTATION", "CAW_OUTRAGING_MODESTY"),
    ):
        for period, metric in REG_DET_PERIODS:
            c.record(
                f"CROSS.{ipc_head}.{period}.{metric}",
                "CROSS",
                f"IPC table '{ipc_head}' equals CAW table '{caw_head}' ({period} {metric})",
                c.get("IPC", ipc_head, period, metric),
                c.get("CAW", caw_head, period, metric),
            )

    # The printed CAW total's composition is not stated beyond its label; report the
    # sum of the item-level rows next to it without assuming which rows it includes.
    caw_items = [
        "CAW_RAPE_TOTAL",
        "CAW_SEXUAL_OFFENCES_SEC69",
        "CAW_KIDNAPPING_TOTAL",
        "CAW_OUTRAGING_MODESTY",
        "CAW_INSULT_TO_MODESTY",
        "CAW_DOWRY_MURDER",
        "CAW_DOWRY_DEATH",
        "CAW_DOWRY_SUICIDE",
        "CAW_DOWRY_HARASSMENT",
        "CAW_MURDER_OTHER_REASONS",
        "CAW_SUICIDE_OTHER_REASONS",
        "CAW_HARASSMENT_OTHER_REASONS",
        "CAW_ACID_ATTACK",
    ]
    for period, metric in REG_DET_PERIODS:
        c.sum_check(
            f"CAW.total.{period}.{metric}",
            "CAW",
            caw_items,
            "CAW_TOTAL",
            period,
            metric,
            "Total Crime Against Women vs items 1-9 (composition not stated)",
        )

    # NDPS ------------------------------------------------------------------------
    drugs = [h["code"] for h in heads_by_section["NDPS"] if h["parent"] == "NDPS_POSSESSION_TOTAL"]
    for metric in ("cases", "persons_arrested", "value", "quantity_tablets"):
        c.sum_check(
            f"NDPS.possession.{metric}",
            "NDPS",
            drugs,
            "NDPS_POSSESSION_TOTAL",
            "CM",
            metric,
            "Total Possession Cases",
        )
    # Cough syrup's 123.20 is printed in the Kgs column but the total rows carry it under
    # litres (see NOTE.NDPS_COUGH_SYRUP_COLUMN), so kg and litres are checked that way.
    solids = [d for d in drugs if d != "NDPS_COUGH_SYRUP"]
    c.sum_check(
        "NDPS.possession.quantity_kg_excl_cough_syrup",
        "NDPS",
        solids,
        "NDPS_POSSESSION_TOTAL",
        "CM",
        "quantity_kg",
        "Total Possession kg vs drugs other than Cough Syrup",
    )
    c.record(
        "NDPS.possession.cough_syrup_litres",
        "NDPS",
        "Cough Syrup quantity (printed in the Kgs column) equals the litres total",
        c.get("NDPS", "NDPS_COUGH_SYRUP", "CM", "quantity_kg"),
        c.get("NDPS", "NDPS_POSSESSION_TOTAL", "CM", "quantity_litres"),
    )
    c.record(
        "NDPS.total.quantity_kg",
        "NDPS",
        "Total NDPS kg equals Total Possession kg (within 0.01 kg of printed rounding)",
        c.get("NDPS", "NDPS_POSSESSION_TOTAL", "CM", "quantity_kg"),
        c.get("NDPS", "NDPS_TOTAL", "CM", "quantity_kg"),
        tol=0.01,
    )
    for metric in ("cases", "persons_arrested"):
        c.sum_check(
            f"NDPS.total.{metric}",
            "NDPS",
            ["NDPS_POSSESSION_TOTAL", "NDPS_CONSUMPTION"],
            "NDPS_TOTAL",
            "CM",
            metric,
            "Total NDPS Cases",
        )

    # EOW -------------------------------------------------------------------------
    cy = c.get("EOW", "EOW_CASES", "CY", "registered")
    py = c.get("EOW", "EOW_CASES", "PY", "registered")
    c.record(
        "EOW.difference",
        "EOW",
        "EOW: printed 'Diff. in Reg.' equals current-year minus previous-year registrations",
        None if cy is None or py is None else cy - py,
        c.get("EOW", "EOW_CASES", "CY_VS_PY", "difference_registered_as_printed"),
    )
    _detection_pct_checks(c, "EOW", ["EOW_CASES"])

    # Cyber -----------------------------------------------------------------------
    cyber = heads_by_section["CYBER"]
    subs = [h["code"] for h in cyber if h["parent"] == "CYBER_CHEATING"]
    top = [h["code"] for h in cyber if h["parent"] is None and h["code"] != "CYBER_TOTAL"]
    for metric in ("registered", "detected", "pa"):
        c.sum_check(
            f"CYBER.cheating.{metric}", "CYBER", subs, "CYBER_CHEATING", "CM", metric, "Cheating"
        )
        c.sum_check(
            f"CYBER.total.{metric}", "CYBER", top, "CYBER_TOTAL", "CM", metric, "Cyber total"
        )
    return c.checks


# Observations about the source that are not arithmetic checks. Each is phrased as a
# fact about what is printed; none of them changes a value.
SOURCE_NOTES: list[dict[str, str]] = [
    {
        "id": "NOTE.PREVIOUS_MONTH_LAW_LABEL",
        "description": "The 'Previous Month' columns are headed 'IPC' while the current month "
        "and current year are headed 'IPC + BNS'. Values are stored as printed; month-to-month "
        "comparisons may mix legal frameworks.",
    },
    {
        "id": "NOTE.CYBER_PA_UNDEFINED",
        "description": "The cyber table's 'PA' column is not defined in the source. It is stored "
        "under the metric name 'pa' without interpretation.",
    },
    {
        "id": "NOTE.BROTHELS_NO_ZONES",
        "description": "The brothel statement is titled 'zonewise' but contains only a Mumbai "
        "TOTAL row; no zone breakdown is available.",
    },
    {
        "id": "NOTE.NDPS_VALUE_UNIT",
        "description": "The NDPS 'Values' column does not state its currency or unit.",
    },
    {
        "id": "NOTE.NDPS_COUGH_SYRUP_COLUMN",
        "description": "Cough Syrup's quantity 123.20 is printed in the Kgs column, while both "
        "total rows list 123.20 under litres. Stored as printed (quantity_kg).",
    },
    {
        "id": "NOTE.NO_SPATIAL_OR_TEMPORAL_DETAIL",
        "description": "The statement is city-level only: no incident records, timestamps, "
        "coordinates, police-station or zone breakdown. It cannot train a spatial or "
        "temporal model on its own.",
    },
    {
        "id": "NOTE.SPELLING_AS_PRINTED",
        "description": "Labels keep the source spelling (e.g. 'Mejor', 'Harrasment').",
    },
]


def summarise(checks: list[dict[str, Any]]) -> dict[str, int]:
    passed = sum(ch["status"] == "pass" for ch in checks)
    return {"total": len(checks), "passed": passed, "discrepancies": len(checks) - passed}
