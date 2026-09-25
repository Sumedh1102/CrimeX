"""Read-only access to the extracted official statement JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

DEFAULT_STATEMENT = (
    Path(__file__).resolve().parents[3] / "data/official/mumbai_police_statement_2026-08.json"
)


@dataclass(frozen=True)
class OfficialStatement:
    doc: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path = DEFAULT_STATEMENT) -> OfficialStatement:
        with Path(path).open(encoding="utf-8") as fh:
            return cls(json.load(fh))

    @cached_property
    def _values(self) -> dict[tuple[str, str, str, str], int | float | None]:
        return {
            (v["section"], v["head"], v["period"], v["metric"]): v["value"]
            for v in self.doc["values"]
        }

    @cached_property
    def heads(self) -> dict[str, dict[str, Any]]:
        return {h["code"]: h for h in self.doc["heads"]}

    @property
    def periods(self) -> dict[str, dict[str, Any]]:
        return self.doc["periods"]

    def value(self, section: str, head: str, period: str, metric: str) -> int | float | None:
        key = (section, head, period, metric)
        if key not in self._values:
            raise KeyError(f"No official value for {key}")
        return self._values[key]

    def ipc_registered(self, head: str, period: str) -> int:
        v = self.value("IPC", head, period, "registered")
        if v is None:
            raise ValueError(f"IPC {head} {period} registered is blank in the source")
        return int(v)
