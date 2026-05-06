from __future__ import annotations

import json
from typing import Any

from contracts.translator_output import SUPPORTED_HARD_RULES, SUPPORTED_SOFT_RULES

SUPPORTED_RULES = SUPPORTED_HARD_RULES | SUPPORTED_SOFT_RULES
SUPPORTED_ROLES = {"SUPERVISOR", "PRESIDENT", "EXAMINER"}
WEIGHT_KEYS = {"workload", "expertise", "clustering", "overload", "custom"}


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value: Any, *, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalized_rule_type(rule_name: str) -> str | None:
    if rule_name in SUPPORTED_HARD_RULES:
        return "hard"
    if rule_name in SUPPORTED_SOFT_RULES:
        return "soft"
    return None


def normalize_roles(raw_roles: Any) -> list[str]:
    if isinstance(raw_roles, str):
        items = [raw_roles]
    elif isinstance(raw_roles, list):
        items = [str(role) for role in raw_roles]
    else:
        return []
    normalized = [role.upper().strip() for role in items if role]
    return [role for role in normalized if role in SUPPORTED_ROLES]


def rule_signature(rule: dict[str, Any]) -> str:
    return json.dumps(rule, sort_keys=True, ensure_ascii=True)
