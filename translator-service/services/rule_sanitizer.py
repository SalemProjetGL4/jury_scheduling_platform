from __future__ import annotations

from typing import Any

from contracts.translator_output import SUPPORTED_HARD_RULES, SUPPORTED_SOFT_RULES
from services.rule_utils import (
    SUPPORTED_ROLES,
    SUPPORTED_RULES,
    as_float,
    as_int,
    normalize_roles,
    normalized_rule_type,
)


def sanitize_rule(
    raw_rule: Any,
    *,
    rule_type: str,
    professor_ids: set[int],
    project_ids: set[int],
    session_ids: set[int],
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw_rule, dict):
        return None, "Rule must be a JSON object"

    name = str(raw_rule.get("rule", "")).strip().lower()
    if name not in SUPPORTED_RULES:
        return None, "Rule is not supported by solver"

    if rule_type == "hard" and name not in SUPPORTED_HARD_RULES:
        return None, "Rule type mismatch for hard constraints"
    if rule_type == "soft" and name not in SUPPORTED_SOFT_RULES:
        return None, "Rule type mismatch for soft constraints"

    normalized: dict[str, Any] = {"rule": name}

    if name == "prefer_morning":
        if rule_type == "soft":
            normalized["weight"] = as_float(raw_rule.get("weight", 1.0), default=1.0)
        return normalized, None

    professor_id = as_int(raw_rule.get("professor_id"))
    project_id = as_int(raw_rule.get("project_id"))
    session_id = as_int(raw_rule.get("session_id"))

    if name in {"forbid_professor_session", "avoid_professor_session"}:
        if professor_id not in professor_ids or session_id not in session_ids:
            return None, "professor_id or session_id not found in database snapshot"
        normalized["professor_id"] = professor_id
        normalized["session_id"] = session_id

    elif name in {"require_project_session", "prefer_project_session"}:
        if project_id not in project_ids or session_id not in session_ids:
            return None, "project_id or session_id not found in database snapshot"
        normalized["project_id"] = project_id
        normalized["session_id"] = session_id

    elif name in {"forbid_professor_project", "penalize_professor_project"}:
        if professor_id not in professor_ids or project_id not in project_ids:
            return None, "professor_id or project_id not found in database snapshot"
        normalized["professor_id"] = professor_id
        normalized["project_id"] = project_id
        roles = normalize_roles(raw_rule.get("roles"))
        if roles:
            normalized["roles"] = roles

    elif name in {"require_professor_role", "prefer_professor_role"}:
        role = str(raw_rule.get("role", "")).upper().strip()
        if professor_id not in professor_ids or project_id not in project_ids:
            return None, "professor_id or project_id not found in database snapshot"
        if role not in SUPPORTED_ROLES:
            return None, "role must be one of SUPERVISOR, PRESIDENT, EXAMINER"
        normalized["professor_id"] = professor_id
        normalized["project_id"] = project_id
        normalized["role"] = role
        if session_id is not None:
            if session_id not in session_ids:
                return None, "session_id not found in database snapshot"
            normalized["session_id"] = session_id

    if rule_type == "soft":
        normalized["weight"] = as_float(raw_rule.get("weight", 1.0), default=1.0)

    return normalized, None
