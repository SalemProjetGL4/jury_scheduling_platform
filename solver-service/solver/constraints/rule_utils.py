from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model


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


_ALL_ROLES = ("SUPERVISOR", "PRESIDENT", "EXAMINER")


def collect_custom_bound_terms(
    payload: dict[str, Any],
    vars_x: dict[tuple[int, int, str, int], cp_model.IntVar],
    all_professor_ids: list[int],
    all_project_ids: list[int],
    all_sessions: list[dict[str, Any]],
) -> list[cp_model.IntVar]:
    """Return the list of x-variables that match the filters in a custom_bound payload.

    The caller sums these and applies operator/bound as a hard or soft constraint.
    Omitting a filter (null / missing) means "match all".
    """
    def _to_int_set(raw: Any, fallback: list[int]) -> set[int]:
        if raw is None:
            return set(fallback)
        try:
            return {int(v) for v in raw}
        except (TypeError, ValueError):
            return set(fallback)

    prof_filter = _to_int_set(payload.get("professor_ids"), all_professor_ids)
    proj_filter = _to_int_set(payload.get("project_ids"), all_project_ids)

    raw_roles = payload.get("roles")
    role_filter: set[str] = (
        {str(r).upper() for r in raw_roles if str(r).upper() in _ALL_ROLES}
        if raw_roles is not None
        else set(_ALL_ROLES)
    )

    # Build session filter, applying optional period/date narrowing.
    period_filter: str | None = payload.get("period")
    date_filter: str | None = payload.get("date")
    raw_sess_ids = payload.get("session_ids")

    candidate_sessions = all_sessions
    if period_filter:
        candidate_sessions = [s for s in candidate_sessions if str(s.get("period", "")).lower() == period_filter]
    if date_filter:
        candidate_sessions = [s for s in candidate_sessions if str(s.get("date", "")) == date_filter]

    if raw_sess_ids is not None:
        explicit = {int(v) for v in raw_sess_ids}
        sess_filter = {s["id"] for s in candidate_sessions} & explicit
    else:
        sess_filter = {s["id"] for s in candidate_sessions}

    terms: list[cp_model.IntVar] = []
    for pid in prof_filter:
        for pr_id in proj_filter:
            for role in role_filter:
                for sid in sess_filter:
                    var = vars_x.get((pid, pr_id, role, sid))
                    if var is not None:
                        terms.append(var)
    return terms