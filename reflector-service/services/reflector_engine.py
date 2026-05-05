from __future__ import annotations

import json
from typing import Any

from adapters.llm_provider_adapter import get_provider
from adapters.prompt_registry import prompt_registry
from contracts.api_models import ReflectRequest
from contracts.reflector_output import ReflectorOutput, safe_parse_reflector_output


def reflect_solver_output(request: ReflectRequest) -> dict[str, Any]:
    payload = {
        "request_id": request.request_id,
        "solver_result": request.solver_result,
        "solver_payload": request.solver_payload,
        "db_snapshot": request.db_snapshot,
    }

    try:
        parsed = _apply_llm_reflection(payload)
        if parsed is not None:
            return parsed.model_dump(mode="json")
    except Exception:
        pass

    return _build_fallback_reflection(payload)


def _apply_llm_reflection(payload: dict[str, Any]) -> ReflectorOutput | None:
    system_prompt, _ = prompt_registry.get_with_hash("reflector.system.txt")
    schema_prompt, _ = prompt_registry.get_with_hash("reflector.schema.txt")

    provider = get_provider()
    user_message = json.dumps(payload, ensure_ascii=True)
    raw_output = provider.complete(
        system_prompt=f"{system_prompt}\n\nReturn strict JSON only.\n{schema_prompt}",
        user_message=user_message,
    )

    parsed, _ = safe_parse_reflector_output(raw_output)
    return parsed


def _build_fallback_reflection(payload: dict[str, Any]) -> dict[str, Any]:
    solver_result = payload.get("solver_result") or {}
    solver_payload = payload.get("solver_payload")
    status = str(solver_result.get("status", "")).upper()

    if status == "INFEASIBLE":
        relaxations = _build_relaxation_suggestions(
            solver_result.get("failed_constraints") or [],
            solver_payload,
        )
        return {
            "status": "INFEASIBLE",
            "summary": "Solver reported infeasible. Suggested relaxations focus on blocking hard constraints.",
            "ranking_basis": "fewer_soft_violations",
            "recommended_solution_index": None,
            "compromised_solutions": [],
            "relaxation_suggestions": relaxations,
        }

    solutions = solver_result.get("solutions") or []
    compromised_reviews = _build_compromised_reviews(solutions)

    if compromised_reviews:
        return {
            "status": "COMPROMISED",
            "summary": "Multiple compromised solutions ranked with fewer soft violations prioritized.",
            "ranking_basis": "fewer_soft_violations",
            "recommended_solution_index": compromised_reviews[0]["solution_index"],
            "compromised_solutions": compromised_reviews,
            "relaxation_suggestions": [],
        }

    recommended_index = None
    if solutions:
        recommended_index = int(solutions[0].get("solution_index") or 1)

    return {
        "status": "OPTIMAL" if solutions else "FEASIBLE",
        "summary": "Feasible solution(s) with no soft constraint violations detected.",
        "ranking_basis": "fewer_soft_violations",
        "recommended_solution_index": recommended_index,
        "compromised_solutions": [],
        "relaxation_suggestions": [],
    }


def _build_compromised_reviews(solutions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []

    for idx, solution in enumerate(solutions, start=1):
        violations = list(solution.get("unsatisfied_soft_constraints") or [])
        total_penalty = _solution_penalty(solution, violations)
        violations_count = len(violations)

        if not _is_compromised(solution, violations):
            continue

        rating = _score_solution(violations_count, total_penalty)
        explanation = _build_violation_explanation(violations)

        reviews.append(
            {
                "solution_index": int(solution.get("solution_index") or idx),
                "rating": rating,
                "violations_count": violations_count,
                "total_penalty": total_penalty,
                "violated_soft_constraints": violations,
                "explanation": explanation,
            }
        )

    reviews.sort(
        key=lambda item: (
            -item["rating"],
            item["total_penalty"],
            item["violations_count"],
            item["solution_index"],
        )
    )
    return reviews


def _is_compromised(solution: dict[str, Any], violations: list[dict[str, Any]]) -> bool:
    return bool(violations)


def _solution_penalty(solution: dict[str, Any], violations: list[dict[str, Any]]) -> float:
    total = 0.0
    for violation in violations:
        if "penalty_weighted" in violation:
            total += _as_float(violation.get("penalty_weighted"))
        elif "penalty" in violation:
            total += _as_float(violation.get("penalty")) / 100

    if total > 0:
        return total

    if "custom_soft_penalty" in solution:
        try:
            return float(solution.get("custom_soft_penalty") or 0)
        except (TypeError, ValueError):
            return 0.0
    if "custom_soft_penalty_scaled" in solution:
        try:
            return float(solution.get("custom_soft_penalty_scaled") or 0) / 100
        except (TypeError, ValueError):
            return 0.0

    return total


def _score_solution(violations_count: int, total_penalty: float) -> int:
    score = 100 - (violations_count * 15) - int(round(total_penalty * 2))
    return max(0, min(100, score))


def _build_violation_explanation(violations: list[dict[str, Any]]) -> str:
    if not violations:
        return "No soft constraint violations."

    parts: list[str] = []
    for violation in violations[:3]:
        rule = str(violation.get("rule") or "unknown_rule")
        payload = violation.get("payload") or {}
        if payload:
            payload_text = json.dumps(payload, ensure_ascii=True)
            parts.append(f"{rule} {payload_text}")
        else:
            parts.append(rule)

    summary = "; ".join(parts)
    if len(violations) > 3:
        summary = f"{summary}; and {len(violations) - 3} more"

    return f"Violations: {summary}."


def _build_relaxation_suggestions(
    failed_constraints: list[dict[str, Any]],
    solver_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in failed_constraints:
        constraint = str(item.get("constraint") or "unknown_constraint")
        details = item.get("details") or {}
        action, reason = _map_relaxation_action(constraint, details)
        patch = _build_relaxation_patch(constraint, details, solver_payload, action)

        key = json.dumps({"constraint": constraint, "details": details}, sort_keys=True, ensure_ascii=True)
        if key in seen:
            continue

        suggestion = {
            "constraint": constraint,
            "action": action,
            "reason": reason,
            "details": details,
            "patch": patch,
        }

        suggestions.append(suggestion)
        seen.add(key)

    return suggestions


def _map_relaxation_action(constraint: str, details: dict[str, Any]) -> tuple[str, str]:
    if constraint == "project_scheduled_once":
        return "allow_unscheduled_project", _explain_project_scheduled_once(details)
    if constraint == "role_unique_per_project":
        return "allow_role_vacancy", _explain_role_unique(details)
    if constraint == "role_session_link":
        return "decouple_role_from_session", _explain_role_session_link(details)
    if constraint == "one_role_per_professor_session":
        return "allow_multiple_roles_same_session", _explain_one_role(details)
    if constraint == "max_juries_per_professor":
        return "increase_hard_max_juries", _explain_max_juries(details)
    if constraint == "supervisor_fixed":
        return "allow_non_supervisor_as_supervisor", _explain_supervisor_fixed(details)
    if constraint == "half_day_exclusivity":
        return "allow_full_day_service", _explain_half_day(details)
    if constraint == "professor_unavailable":
        return "relax_unavailability", _explain_unavailability(details)
    if constraint == "conflict_of_interest":
        return "relax_conflict", _explain_conflict(details)
    if constraint.startswith("custom_hard_"):
        return "disable_custom_hard_rule", _explain_custom_rule(details)

    return "relax_constraint", "Relax this hard constraint to regain feasibility."


def _build_relaxation_patch(
    constraint: str,
    details: dict[str, Any],
    solver_payload: dict[str, Any] | None,
    action: str,
) -> dict[str, Any] | None:
    if action == "increase_hard_max_juries" and solver_payload:
        current = solver_payload.get("constraints", {}).get("hard_max_juries")
        if isinstance(current, int):
            return {"op": "set", "path": "constraints.hard_max_juries", "value": current + 1}

    if action == "relax_unavailability" and details:
        return {"op": "remove", "path": "unavailabilities", "match": details}

    if action == "relax_conflict" and details:
        return {"op": "remove", "path": "conflicts", "match": details}

    if action == "disable_custom_hard_rule" and details:
        rule = details.get("rule")
        payload = details.get("payload")
        if rule:
            return {"op": "disable_rule", "path": "constraint_rules", "match": {"rule": rule, "payload": payload}}

    if action == "allow_unscheduled_project" and details.get("project_id") is not None:
        return {"op": "allow_unscheduled", "path": "projects", "match": {"id": details.get("project_id")}}

    return None


def _explain_project_scheduled_once(details: dict[str, Any]) -> str:
    project_id = details.get("project_id")
    return f"Allow project {project_id} to be unscheduled or placed in multiple sessions."


def _explain_role_unique(details: dict[str, Any]) -> str:
    project_id = details.get("project_id")
    role = details.get("role")
    return f"Allow the {role} role on project {project_id} to be empty or shared."


def _explain_role_session_link(details: dict[str, Any]) -> str:
    project_id = details.get("project_id")
    session_id = details.get("session_id")
    role = details.get("role")
    return (
        f"Allow {role} assignment for project {project_id} to be in a different session than {session_id}."
    )


def _explain_one_role(details: dict[str, Any]) -> str:
    professor_id = details.get("professor_id")
    session_id = details.get("session_id")
    return (
        f"Allow professor {professor_id} to hold multiple roles in session {session_id}."
    )


def _explain_max_juries(details: dict[str, Any]) -> str:
    professor_id = details.get("professor_id")
    max_juries = details.get("max_juries")
    return (
        f"Increase the hard jury cap so professor {professor_id} can exceed {max_juries} total assignments."
    )


def _explain_supervisor_fixed(details: dict[str, Any]) -> str:
    project_id = details.get("project_id")
    supervisor_id = details.get("supervisor_id")
    return (
        f"Allow a non-supervisor to fill the supervisor role for project {project_id} (current {supervisor_id})."
    )


def _explain_half_day(details: dict[str, Any]) -> str:
    professor_id = details.get("professor_id")
    date = details.get("date")
    return (
        f"Allow professor {professor_id} to take both morning and afternoon sessions on {date}."
    )


def _explain_unavailability(details: dict[str, Any]) -> str:
    professor_id = details.get("professor_id")
    date = details.get("date")
    period = details.get("period")
    return (
        f"Allow professor {professor_id} to be scheduled on {date} during {period}."
    )


def _explain_conflict(details: dict[str, Any]) -> str:
    professor_a = details.get("professor_a")
    professor_b = details.get("professor_b")
    project_id = details.get("project_id")
    session_id = details.get("session_id")
    return (
        f"Allow professors {professor_a} and {professor_b} to serve together on project {project_id} in session {session_id}."
    )


def _explain_custom_rule(details: dict[str, Any]) -> str:
    rule = details.get("rule")
    return f"Disable or relax custom hard rule {rule} to regain feasibility."


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
