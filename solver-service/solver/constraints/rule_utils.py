from __future__ import annotations

from dataclasses import dataclass
from typing import Any


WEIGHT_SCALE = 100


@dataclass(frozen=True)
class RuleSpec:
    name: str
    weight: int
    payload: dict[str, Any]


def normalize_weight(value: Any, *, default: float = 1.0) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return max(0, int(round(numeric * WEIGHT_SCALE)))


def collect_rule_specs(data: dict[str, Any], rule_type: str) -> list[RuleSpec]:
    normalized_type = rule_type.lower()
    rules: list[RuleSpec] = []

    for inline_rule in data.get("constraints", {}).get(normalized_type, []):
        spec = _to_rule_spec(inline_rule, fallback_type=normalized_type)
        if spec is not None:
            rules.append(spec)

    for db_rule in data.get("constraint_rules", []):
        if not isinstance(db_rule, dict):
            continue
        if not db_rule.get("enabled", True):
            continue
        if str(db_rule.get("type", "")).lower() != normalized_type:
            continue
        spec = _to_rule_spec(db_rule, fallback_type=normalized_type)
        if spec is not None:
            rules.append(spec)

    return rules


def _to_rule_spec(raw_rule: Any, *, fallback_type: str) -> RuleSpec | None:
    name = _extract_name(raw_rule)
    if not name:
        return None

    if isinstance(raw_rule, dict):
        weight_raw = raw_rule.get("weight", 1)
        payload = _extract_payload(raw_rule)
    else:
        weight_raw = 1
        payload = {}

    # Keep all weights integer for CP-SAT objective while still supporting decimal inputs.
    weight = normalize_weight(weight_raw, default=1)
    if fallback_type == "hard":
        weight = max(1, weight)

    return RuleSpec(name=name, weight=weight, payload=payload)


def _extract_name(raw_rule: Any) -> str:
    if isinstance(raw_rule, str):
        return raw_rule.strip().lower()

    if not isinstance(raw_rule, dict):
        return ""

    candidates = [
        raw_rule.get("rule"),
        raw_rule.get("name"),
        raw_rule.get("payload", {}).get("rule") if isinstance(raw_rule.get("payload"), dict) else None,
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().lower()

    return ""


def _extract_payload(raw_rule: dict[str, Any]) -> dict[str, Any]:
    payload = raw_rule.get("payload")
    if isinstance(payload, dict):
        return dict(payload)

    reserved = {"id", "name", "rule", "type", "weight", "enabled", "payload"}
    return {k: v for k, v in raw_rule.items() if k not in reserved}