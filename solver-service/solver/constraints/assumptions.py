from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ortools.sat.python import cp_model


@dataclass(frozen=True)
class AssumptionInfo:
    key: str
    reason: str
    details: dict[str, Any]
    literal: cp_model.BoolVar


class AssumptionRegistry:
    def __init__(self, model: cp_model.CpModel, *, prefix: str = "assumption") -> None:
        self._model = model
        self._prefix = prefix
        self._items: list[AssumptionInfo] = []
        self._by_literal_index: dict[int, AssumptionInfo] = {}

    def register(self, key: str, reason: str, details: dict[str, Any] | None = None) -> cp_model.BoolVar:
        literal = self._model.NewBoolVar(f"{self._prefix}_{len(self._items) + 1}")
        self._model.AddAssumption(literal)

        info = AssumptionInfo(
            key=key,
            reason=reason,
            details=details or {},
            literal=literal,
        )
        self._items.append(info)

        literal_index = _literal_index(literal)
        if literal_index is not None:
            self._by_literal_index[literal_index] = info

        return literal

    def report_from_literals(self, literals: Iterable[Any]) -> list[dict[str, Any]]:
        report: list[dict[str, Any]] = []
        seen: set[int] = set()

        for literal in literals:
            literal_index = _literal_index(literal)
            if literal_index is None:
                continue
            info = self._by_literal_index.get(literal_index)
            if info is None:
                continue
            info_id = id(info)
            if info_id in seen:
                continue

            entry = {
                "constraint": info.key,
                "reason": info.reason,
            }
            if info.details:
                entry["details"] = info.details

            report.append(entry)
            seen.add(info_id)

        return report


def _literal_index(literal: Any) -> int | None:
    try:
        return abs(int(literal.Index()))
    except AttributeError:
        try:
            return abs(int(literal))
        except (TypeError, ValueError):
            return None
