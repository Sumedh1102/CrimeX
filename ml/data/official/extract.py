"""Extract the Brihan Mumbai monthly crime statement (PDF) into structured records.

The extractor is deliberately strict:

* every parsed row must match the expected official head (see ``taxonomy``), in order;
* numbers are stored exactly as printed (``raw`` keeps the original cell text);
* blank cells are stored as ``None`` and are never silently turned into zero;
* the two known text-extraction artefacts of this layout are repaired explicitly and
  recorded in ``extraction_notes``.

Consistency checks and discrepancy flags live in ``validate.py``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ml.data.official.taxonomy import SECTIONS, OfficialHead, OfficialSection

EXTRACTOR_VERSION = "1.0.0"

_DATE_RE = re.compile(r"(\d{2})[./](\d{2})[./](\d{4})")
_INT_RE = re.compile(r"^\d+$")
_FLOAT_RE = re.compile(r"^\d+\.\d+$")


class ExtractionError(RuntimeError):
    """Raised when the PDF does not match the expected statement layout."""


@dataclass
class Cell:
    value: int | float | None
    raw: str


@dataclass
class Extraction:
    values: list[dict[str, Any]] = field(default_factory=list)
    heads: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add(self, section: str, head: str, period: str, metric: str, cell: Cell) -> None:
        self.values.append(
            {
                "section": section,
                "head": head,
                "period": period,
                "metric": metric,
                "value": cell.value,
                "raw": cell.raw,
            }
        )


def parse_number(raw: str | None) -> Cell:
    text = (raw or "").strip()
    if text in ("", "-"):
        return Cell(None, text)
    compact = text.replace(",", "")
    if _INT_RE.match(compact):
        return Cell(int(compact), text)
    if _FLOAT_RE.match(compact):
        return Cell(float(compact), text)
    raise ExtractionError(f"Unparseable numeric cell: {raw!r}")


def _clean_label(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()


def _parse_date(d: str) -> date:
    m = _DATE_RE.search(d)
    if not m:
        raise ExtractionError(f"No date in {d!r}")
    dd, mm, yyyy = (int(x) for x in m.groups())
    return date(yyyy, mm, dd)


def _match_head(expected: OfficialHead, label: str) -> None:
    if not re.search(expected.match, label, flags=re.IGNORECASE):
        raise ExtractionError(
            f"Row label {label!r} does not match expected head {expected.code} "
            f"({expected.label_official!r}); the PDF layout may have changed."
        )


def _head_record(section: OfficialSection, head: OfficialHead, label_raw: str, sr: str | None):
    return {
        "code": head.code,
        "section": section.id,
        "sr": sr,
        "label_official": head.label_official,
        "label_as_extracted": label_raw,
        "label": head.label,
        "parent": head.parent,
        "is_aggregate": head.is_total,
        "legal_reference": head.legal_reference,
    }


def _split_label_overflow(label: str, cell: str | None) -> tuple[str, str | None]:
    """Repair a label that overflowed into the first numeric cell (e.g. 'or)25')."""
    text = (cell or "").strip()
    m = re.match(r"^(\D+?)(\d+)$", text)
    if m and not _INT_RE.match(text):
        return label + m.group(1), m.group(2)
    return label, cell


def _distribute_merged_rows(rows: list[list[str | None]], value_cols: list[int]) -> list[str]:
    """Split cells holding several newline-separated numbers across following empty rows.

    pdfplumber merges the values of adjacent rows when their borders are faint (cyber
    rows 11-13). Returns repair notes.
    """
    notes: list[str] = []
    for i, row in enumerate(rows):
        first = row[value_cols[0]]
        if first is None or "\n" not in first:
            continue
        parts = [[p.strip() for p in (row[c] or "").split("\n")] for c in value_cols]
        k = len(parts[0])
        if any(len(p) != k for p in parts):
            raise ExtractionError(f"Inconsistent merged cells in row {row!r}")
        following = rows[i + 1 : i + k]
        if len(following) != k - 1 or any(r[value_cols[0]] not in (None, "") for r in following):
            raise ExtractionError(f"Cannot distribute merged cells of row {row!r}")
        for j, target in enumerate([row, *following]):
            for c, p in zip(value_cols, parts, strict=True):
                target[c] = p[j]
        notes.append(f"Split {k} merged rows starting at {row[2] or row[1]!r} into separate rows.")
    return notes


def _data_rows(table: list[list[str | None]], first_label: str):
    """Return rows from the first row whose label matches ``first_label`` onwards."""
    for i, row in enumerate(table):
        cells = [c for c in row if c]
        if any(re.search(first_label, _clean_label(c), re.IGNORECASE) for c in cells[:3]):
            return [list(r) for r in table[i:]]
    raise ExtractionError(f"Could not find first data row matching {first_label!r}")


# ---------------------------------------------------------------------------- periods


def _extract_periods(page1_table: list[list[str | None]]) -> dict[str, dict[str, Any]]:
    starts: list[date] = []
    ends: list[date] = []
    law: list[str] = []
    for row in page1_table[:8]:
        cells = [c or "" for c in row]
        dates = [c for c in cells if _DATE_RE.search(c)]
        if len(dates) == 4 and not starts:
            starts = [_parse_date(c) for c in dates]
        elif len(dates) == 4 and starts:
            ends = [_parse_date(c) for c in dates]
        labels = [c.strip() for c in cells if c.strip() in ("IPC + BNS", "IPC")]
        if len(labels) >= 3 and not law:
            law = labels
    if not (starts and ends and law):
        raise ExtractionError("Could not read the reporting periods from the IPC table header.")
    keys = ("CM", "PM", "CY", "PY")
    names = {
        "CM": "Current Month",
        "PM": "Previous Month",
        "CY": "Current Year (year to date)",
        "PY": "Previous Year (same period)",
    }
    law_labels = {"CM": law[0], "PM": law[1], "CY": law[2], "PY": None}
    periods = {
        k: {
            "label": names[k],
            "start": starts[i].isoformat(),
            "end": ends[i].isoformat(),
            "law_label_as_printed": law_labels[k],
        }
        for i, k in enumerate(keys)
    }
    return periods


# ---------------------------------------------------------------------------- sections


def _parse_reg_det_table(
    ex: Extraction,
    section: OfficialSection,
    rows: list[list[str | None]],
    *,
    label_col: int,
    first_value_col: int,
    has_diff: bool,
) -> None:
    heads = list(section.heads)
    if len(rows) < len(heads):
        raise ExtractionError(f"{section.id}: expected {len(heads)} rows, found {len(rows)}")
    for head, row in zip(heads, rows[: len(heads)], strict=True):
        sr = (row[0] or "").strip() or None
        label = _clean_label(row[label_col])
        if not label and row[0] and not _INT_RE.match(row[0].strip()):
            label = _clean_label(row[0])  # total rows put the label in column 0
            sr = None
        c = first_value_col
        label, fixed = _split_label_overflow(label, row[c])
        if fixed is not row[c]:
            ex.notes.append(
                f"{section.id}: label of {head.code} overflowed into its first value cell "
                f"({row[c]!r}); repaired to label={label!r}, value={fixed!r}."
            )
            row[c] = fixed
        _match_head(head, label)
        ex.heads.append(_head_record(section, head, label, sr))
        cols = {
            ("CM", "registered"): c,
            ("CM", "detected"): c + 1,
            ("PM", "registered"): c + 2,
            ("PM", "detected"): c + 3,
            ("CY", "registered"): c + 4,
            ("CY", "detected"): c + 5,
            ("CY", "detection_pct"): c + 6,
            ("PY", "registered"): c + 7,
            ("PY", "detected"): c + 8,
            ("PY", "detection_pct"): c + 9,
        }
        for (period, metric), col in cols.items():
            ex.add(section.id, head.code, period, metric, parse_number(row[col]))
        if has_diff:
            sign = (row[c + 10] or "").strip()
            magnitude = parse_number(row[c + 11])
            if magnitude.value is not None and sign not in ("+", "-"):
                raise ExtractionError(f"Missing sign for difference of {head.code}: {row!r}")
            value = None
            if magnitude.value is not None:
                value = magnitude.value if sign == "+" else -magnitude.value
            ex.add(
                section.id,
                head.code,
                "CY_VS_PY",
                "difference_registered",
                Cell(value, f"{sign} {magnitude.raw}".strip()),
            )


def _parse_ipc(ex: Extraction, table: list[list[str | None]]) -> None:
    section = SECTIONS[0]
    rows = _data_rows(table, r"^Murder$")
    _parse_reg_det_table(ex, section, rows, label_col=1, first_value_col=2, has_diff=True)


def _parse_caw(ex: Extraction, table: list[list[str | None]]) -> None:
    section = SECTIONS[1]
    rows = _data_rows(table, r"^Rape\s+u/s")
    _parse_reg_det_table(ex, section, rows, label_col=1, first_value_col=2, has_diff=False)


def _parse_ndps(ex: Extraction, table: list[list[str | None]]) -> None:
    section = SECTIONS[2]
    rows = _data_rows(table, r"^Heroin$")
    metrics = (
        "cases",
        "persons_arrested",
        "quantity_kg",
        "quantity_tablets",
        "quantity_litres",
        "value",
    )
    for head, row in zip(section.heads, rows, strict=True):
        label = _clean_label(row[0])
        _match_head(head, label)
        ex.heads.append(_head_record(section, head, label, None))
        for i, metric in enumerate(metrics, start=1):
            cell = row[i] if i < len(row) else None
            ex.add(section.id, head.code, "CM", metric, parse_number(cell))


def _parse_brothels(ex: Extraction, table: list[list[str | None]]) -> None:
    section = SECTIONS[3]
    rows = [r for r in table if (r[0] or "").strip().upper() == "TOTAL"]
    if len(rows) != 1:
        raise ExtractionError("Brothel statement: expected exactly one TOTAL row.")
    row = rows[0]
    header = " ".join(_clean_label(c) for r in table[:3] for c in r if c)
    for i, head in enumerate(section.heads):
        _match_head(head, header)
        ex.heads.append(_head_record(section, head, head.label_official, None))
        for j, period in enumerate(("CM", "CY", "PY")):
            ex.add(section.id, head.code, period, "count", parse_number(row[1 + 3 * i + j]))


def _parse_eow(ex: Extraction, table: list[list[str | None]]) -> None:
    section = SECTIONS[4]
    rows = _data_rows(table, r"^EOW\s+CASES")
    row = rows[0]
    head = section.heads[0]
    _match_head(head, _clean_label(row[0]))
    ex.heads.append(_head_record(section, head, _clean_label(row[0]), None))
    cols = {
        ("CM", "registered"): 1,
        ("CM", "detected"): 2,
        ("PM", "registered"): 3,
        ("PM", "detected"): 4,
        ("CY", "registered"): 5,
        ("CY", "detected"): 6,
        ("CY", "detection_pct"): 7,
        ("PY", "registered"): 8,
        ("PY", "detected"): 9,
        ("CY_VS_PY", "difference_registered_as_printed"): 10,
        ("CY", "property_involved_rs"): 11,
    }
    for (period, metric), col in cols.items():
        ex.add(section.id, head.code, period, metric, parse_number(row[col]))


def _parse_cyber(ex: Extraction, table: list[list[str | None]]) -> None:
    section = SECTIONS[5]
    rows = _data_rows(table, r"^Tampering\s+of\s+Source")
    ex.notes.extend(f"CYBER: {n}" for n in _distribute_merged_rows(rows, [3, 4, 5]))
    heads = list(section.heads)
    for head, row in zip(heads, rows[: len(heads)], strict=True):
        if head.parent == "CYBER_CHEATING":
            sr, label = (row[1] or "").strip(), _clean_label(row[2])
        elif head.code == "CYBER_TOTAL":
            sr, label = None, _clean_label(row[0])
        else:
            sr, label = (row[0] or "").strip(), _clean_label(row[1])
        _match_head(head, label)
        ex.heads.append(_head_record(section, head, label, sr or None))
        for metric, col in (("registered", 3), ("detected", 4), ("pa", 5)):
            ex.add(section.id, head.code, "CM", metric, parse_number(row[col]))


def _check_period_mentions(pages_text: list[str], periods: dict[str, dict[str, Any]]) -> list[str]:
    """Confirm that every page refers to the same reporting month as page 1."""
    notes = []
    cm_start = date.fromisoformat(periods["CM"]["start"])
    dotted = cm_start.strftime("%d.%m.%Y")
    slashed = cm_start.strftime("%d/%m/%Y")
    short = cm_start.strftime("%b-%y")
    for i, text in enumerate(pages_text, start=1):
        if not any(tok in text for tok in (dotted, slashed, short)):
            raise ExtractionError(f"Page {i} does not mention the reporting month {dotted}.")
    notes.append(f"All pages refer to the reporting month starting {cm_start.isoformat()}.")
    return notes


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_statement(pdf_path: str | Path) -> dict[str, Any]:
    """Parse the statement PDF and return a JSON-serialisable dict (without checks)."""
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError("Install the 'official' extra: pip install -e '.[official]'") from exc

    pdf_path = Path(pdf_path)
    ex = Extraction()
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) != len(SECTIONS):
            raise ExtractionError(f"Expected {len(SECTIONS)} pages, found {len(pdf.pages)}.")
        tables = []
        texts = []
        for page in pdf.pages:
            page_tables = page.extract_tables()
            if not page_tables:
                raise ExtractionError(f"No table found on page {page.page_number}.")
            tables.append(max(page_tables, key=len))
            texts.append(page.extract_text() or "")

    periods = _extract_periods(tables[0])
    ex.notes.extend(_check_period_mentions(texts, periods))
    _parse_ipc(ex, tables[0])
    _parse_caw(ex, tables[1])
    _parse_ndps(ex, tables[2])
    _parse_brothels(ex, tables[3])
    _parse_eow(ex, tables[4])
    _parse_cyber(ex, tables[5])

    return {
        "report": {
            "title": "Brihan Mumbai - monthly crime statement",
            "jurisdiction": "Brihan Mumbai (city level; no station or zone breakdown)",
            "source_file": pdf_path.name,
            "source_sha256": sha256_file(pdf_path),
            "statement_month": periods["CM"]["start"][:7],
            "data_nature": "OFFICIAL_AGGREGATE",
            "extractor_version": EXTRACTOR_VERSION,
        },
        "periods": periods,
        "sections": [{"id": s.id, "title": s.title, "page": s.page} for s in SECTIONS],
        "heads": ex.heads,
        "values": ex.values,
        "extraction_notes": ex.notes,
    }
