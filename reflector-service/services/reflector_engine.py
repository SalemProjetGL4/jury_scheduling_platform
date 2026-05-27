from __future__ import annotations

import json
from typing import Any

from adapters.llm_provider_adapter import get_provider
from adapters.prompt_registry import prompt_registry
from contracts.api_models import ReflectRequest
from contracts.reflector_output import ReflectorOutput, safe_parse_reflector_output
from services.evaluator import ReflectorEvaluator
import logging
from pathlib import Path


# configure logger — /app/logs is volume-mounted from the host
LOG_DIR = Path("/app/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("reflector")
if not logger.handlers:
    handler = logging.FileHandler(LOG_DIR / "reflector_debug.log")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)
    logger.setLevel(logging.INFO)


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
            result = parsed.model_dump(mode="json")
            _write_scores_to_redis(request, result)
            return result
    except Exception as exc:
        # Surface LLM errors clearly but return a valid ReflectorOutput dict
        msg = str(exc) or ""
        lower = msg.lower()
        logger.exception("LLM reflection failed: %s", exc)

        reason = "LLM_PROVIDER_FAILURE"
        if "invalid api key" in lower or "invalid_api_key" in lower or "401" in lower or "auth" in lower:
            reason = "LLM_AUTH_FAILURE"

        # Map errors into an INFEASIBLE response with the error noted in the summary
        return {
            "status": "INFEASIBLE",
            "summary": f"LLM error ({reason}): {msg}",
            "ranking_basis": "human_cost_hierarchy",
            "recommended_solution_index": None,
            "compromised_solutions": [],
            "relaxation_suggestions": [],
        }

    # If LLM was not used / returned None, use the deterministic fallback
    result = _build_fallback_reflection(payload)
    _write_scores_to_redis(request, result)
    return result


def build_reflector_context(payload: dict[str, Any]) -> dict[str, Any]:
    solver_result = payload.get("solver_result", {})
    solver_payload = payload.get("solver_payload", {})
    status = solver_result.get("status", "")
    failed_constraints = solver_result.get("failed_constraints", [])

    # BUILD NAME LOOKUP from db_snapshot if available (has real names)
    db_snapshot = payload.get("db_snapshot", {})
    prof_names = {
        p["id"]: p.get("name", f"Professor {p['id']}")
        for p in db_snapshot.get("professors", [])
    }
    proj_titles = {
        p["id"]: p.get("title", f"Project {p['id']}")
        for p in db_snapshot.get("projects", [])
    }

    context: dict[str, Any] = {
        "request_id": payload.get("request_id"),
        "solver_result": solver_result,
        "strategic_intent": payload.get("strategic_intent", {}),
        "iteration_state": payload.get("iteration_state", {}),
    }

    if status != "INFEASIBLE":
        # COMPROMISED: only send violated soft constraints, no grid
        solutions = solver_result.get("solutions", [])
        context["solver_result"]["solutions"] = [
            {
                "solution_index": s["solution_index"],
                "status": s["status"],
                "objective_value": s.get("objective_value", 0),
                "unsatisfied_soft_constraints": s.get("unsatisfied_soft_constraints", []),
            }
            for s in solutions
        ]

        # Enrich soft constraint violations with real names
        for solution in context["solver_result"]["solutions"]:
            for violation in solution.get("unsatisfied_soft_constraints", []):
                p = violation.get("payload", {})
                if "professor_id" in p:
                    violation["professor_name"] = prof_names.get(
                        p["professor_id"], f"Professor {p['professor_id']}"
                    )
                if "project_id" in p:
                    violation["project_title"] = proj_titles.get(
                        p["project_id"], f"Project {p['project_id']}"
                    )
        return context

    # --- INFEASIBLE: detect bottleneck type and build targeted context ---
    professors = {p["id"]: p for p in solver_payload.get("professors", [])}
    projects = solver_payload.get("projects", [])
    sessions = solver_payload.get("sessions", [])
    unavailabilities = solver_payload.get("unavailabilities", [])
    conflicts = solver_payload.get("conflicts", [])

    # Detect which constraint types are failing
    failed_types = {fc["constraint"] for fc in failed_constraints}

    # --- CASE 1: Slot capacity (not enough sessions for all projects) ---
    if "project_slot_capacity" in failed_types:
        from collections import Counter

        supervisor_counts = Counter(p["supervisor_id"] for p in projects)
        unique_dates = {s["date"] for s in sessions}

        context["capacity_summary"] = {
            "professor_count": len(professors),
            "project_count": len(projects),
            "session_count": len(sessions),
            "unique_days": len(unique_dates),
            "morning_slots": sum(1 for s in sessions if s["period"] == "morning"),
            "afternoon_slots": sum(1 for s in sessions if s["period"] == "afternoon"),
            "slot_deficit": len(projects) - len(sessions),
            "hard_max_juries": solver_payload.get("constraints", {}).get("hard_max_juries", 8),
            "overloaded_supervisors": [
                {
                    "professor_id": pid,
                    "professor_name": prof_names.get(pid, f"Professor {pid}"),
                    "project_count": count,
                }
                for pid, count in supervisor_counts.most_common(5)
                if count > 3
            ],
        }

    # --- CASE 2: Professor unavailability blocking a project ---
    if "professor_unavailable" in failed_types or any(
        "unavailab" in fc["constraint"].lower() for fc in failed_constraints
    ):
        # Find which professors are unavailable and which projects they supervise
        unavailable_prof_ids = {u["professor_id"] for u in unavailabilities}

        blocked_projects = [
            {
                "project_id": p["id"],
                "project_title": proj_titles.get(p["id"], f"Project {p['id']}"),
                "supervisor_id": p["supervisor_id"],
                "supervisor_name": prof_names.get(p["supervisor_id"], f"Professor {p['supervisor_id']}"),
            }
            for p in projects
            if p["supervisor_id"] in unavailable_prof_ids
        ]

        context["unavailability_context"] = {
            "unavailabilities": [
                {
                    "professor_id": u["professor_id"],
                    "professor_name": prof_names.get(u["professor_id"], f"Professor {u['professor_id']}"),
                    "date": u["date"],
                    "period": u["period"],
                }
                for u in unavailabilities
            ],
            "blocked_projects": blocked_projects,
        }

    # --- CASE 3: Conflict of interest between professors ---
    if "conflict_of_interest" in failed_types or any(
        "conflict" in fc["constraint"].lower() for fc in failed_constraints
    ):
        # Enrich conflicts with real names
        enriched_conflicts = [
            {
                "professor_a_id": c["professor_a"],
                "professor_a_name": prof_names.get(c["professor_a"], f"Professor {c['professor_a']}"),
                "professor_b_id": c["professor_b"],
                "professor_b_name": prof_names.get(c["professor_b"], f"Professor {c['professor_b']}"),
            }
            for c in conflicts
        ]

        # Find projects where both conflicting professors are supervisors
        # (i.e. they'd inevitably share a jury)
        conflict_pairs = {
            (min(c["professor_a"], c["professor_b"]), max(c["professor_a"], c["professor_b"]))
            for c in conflicts
        }

        # Find projects supervised by professors involved in conflicts
        conflicted_prof_ids = {pid for pair in conflict_pairs for pid in pair}
        affected_projects = [
            {
                "project_id": p["id"],
                "project_title": proj_titles.get(p["id"], f"Project {p['id']}"),
                "supervisor_id": p["supervisor_id"],
                "supervisor_name": prof_names.get(p["supervisor_id"], f"Professor {p['supervisor_id']}"),
            }
            for p in projects
            if p["supervisor_id"] in conflicted_prof_ids
        ]

        context["conflict_context"] = {
            "conflict_pairs": enriched_conflicts,
            "affected_projects": affected_projects[:10],
            "total_conflict_pairs": len(enriched_conflicts),
        }

    # --- CASE 4: Supervisor binding impossible ---
    if "supervisor_binding" in failed_types:
        binding_conflicts = []
        for p in projects:
            sup_id = p["supervisor_id"]
            # Check if supervisor has any unavailability at all
            sup_unavailable = [u for u in unavailabilities if u["professor_id"] == sup_id]
            if sup_unavailable:
                binding_conflicts.append(
                    {
                        "project_id": p["id"],
                        "project_title": proj_titles.get(p["id"], f"Project {p['id']}"),
                        "supervisor_id": sup_id,
                        "supervisor_name": prof_names.get(sup_id, f"Professor {sup_id}"),
                        "supervisor_unavailable_on": [
                            {"date": u["date"], "period": u["period"]}
                            for u in sup_unavailable
                        ],
                    }
                )

        context["supervisor_binding_context"] = {
            "binding_conflicts": binding_conflicts[:10],
        }

    # --- CASE 5: Not enough fully available professors to fill each jury role ---
    if "role_uniqueness" in failed_types or "each_role_filled_once" in failed_types:
        unavailable_prof_ids = {u["professor_id"] for u in unavailabilities}
        conflicted_prof_ids = set()
        for c in conflicts:
            conflicted_prof_ids.add(c["professor_a"])
            conflicted_prof_ids.add(c["professor_b"])

        restricted_professors = unavailable_prof_ids | conflicted_prof_ids
        available_count = len(professors) - len(restricted_professors)

        context["role_uniqueness_context"] = {
            "total_professors": len(professors),
            "unavailable_professors": len(unavailable_prof_ids),
            "conflicted_professors": len(conflicted_prof_ids),
            "effectively_available": available_count,
            "minimum_needed_per_jury": 3,
            "description": (
                f"Only {available_count} professors are fully available. "
                f"Each jury needs 3 distinct professors. "
                f"Some projects may have an insufficient pool."
            ),
        }

    # --- CASE 5: One professor is required in multiple simultaneous projects ---
    if "no_simultaneous_slots" in failed_types:
        from collections import Counter

        supervisor_counts = Counter(p["supervisor_id"] for p in projects)

        context["simultaneous_slots_context"] = {
            "description": "A professor is required in two projects simultaneously.",
            "high_risk_professors": [
                {
                    "professor_id": pid,
                    "professor_name": prof_names.get(pid, f"Professor {pid}"),
                    "supervised_project_count": count,
                    "projects": [
                        {
                            "project_id": p["id"],
                            "project_title": proj_titles.get(p["id"], f"Project {p['id']}")
                        }
                        for p in projects
                        if p["supervisor_id"] == pid
                    ],
                }
                for pid, count in supervisor_counts.most_common(5)
                if count >= 2
            ],
        }

    # --- CASE 6: Half-day exclusivity bottleneck ---
    if "half_day_exclusivity" in failed_types:
        from collections import defaultdict, Counter

        # Group sessions by date and period
        sessions_by_date_period = defaultdict(list)
        for s in sessions:
            sessions_by_date_period[(s["date"], s["period"])].append(s["id"])

        # Find professors who supervise many projects - they're most likely
        # to hit the half-day constraint
        supervisor_counts = Counter(p["supervisor_id"] for p in projects)

        high_risk = []
        for pid, count in supervisor_counts.most_common(10):
            if count >= 2:
                supervised = [
                    {
                        "project_id": p["id"],
                        "project_title": proj_titles.get(p["id"], f"Project {p['id']}")
                    }
                    for p in projects if p["supervisor_id"] == pid
                ]
                high_risk.append({
                    "professor_id": pid,
                    "professor_name": prof_names.get(pid, f"Professor {pid}"),
                    "supervised_project_count": count,
                    "supervised_projects": supervised,
                    "risk": "HIGH" if count >= 4 else "MEDIUM"
                })

        context["half_day_context"] = {
            "description": (
                "A professor cannot work both morning and afternoon on the same day. "
                "Professors supervising many projects are most at risk."
            ),
            "unique_days": len(set(s["date"] for s in sessions)),
            "high_risk_professors": high_risk,
        }

    return context


def _apply_llm_reflection(payload: dict[str, Any]) -> ReflectorOutput | None:
    system_prompt, _ = prompt_registry.get_with_hash("reflector.system.txt")
    schema_prompt, _ = prompt_registry.get_with_hash("reflector.schema.txt")

    provider = get_provider()
    adapter_name = provider.__class__.__name__

    # Tag the system prompt so we can verify which prompt was actually sent
    tagged_system = f"REFLECTOR_V3\n{system_prompt}\n\nReturn strict JSON only.\n{schema_prompt}"

    reflector_context = build_reflector_context(payload)
    user_message = json.dumps(reflector_context, ensure_ascii=True)

    # Log what we're about to send
    logger.info("LLM adapter: %s", adapter_name)
    logger.info("SYSTEM PROMPT (first 300 chars): %s", tagged_system[:300].replace('\n', '\\n'))
    logger.info("USER PAYLOAD (first 1000 chars): %s", user_message[:1000])

    try:
        raw_output = provider.complete(
            system_prompt=tagged_system,
            user_message=user_message,
        )
    except Exception as exc:  # log and re-raise
        logger.exception("LLM provider.complete() failed: %s", exc)
        raise

    logger.info("RAW MODEL OUTPUT (first 2000 chars): %s", (raw_output or '')[:2000])
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


def _write_scores_to_redis(request: ReflectRequest, reflector_result: dict[str, Any]) -> None:
    """Update the existing solver Redis blob with reflector score fields.

    The solver already stores the full result at `solver:result:{request_id}`.
    We enrich each solution in that stored payload with reflector scoring output.
    """
    request_id = str(request.request_id or "").strip()
    if not request_id:
        return

    evaluator = ReflectorEvaluator()
    redis_client = getattr(evaluator, "redis_client", None)
    if not redis_client:
        return

    key = f"solver:result:{request_id}"
    try:
        raw = redis_client.get(key)
        if not raw:
            return

        stored = json.loads(raw)
        has_nested_result = isinstance(stored, dict) and "result" in stored and isinstance(stored.get("result"), dict)
        solver_result = stored["result"] if has_nested_result else stored

        solutions = list((solver_result or {}).get("solutions") or [])
        if not solutions:
            return

        scored_reviews = evaluator.score_solutions(solutions)
        review_by_index = {int(review["solution_index"]): review for review in scored_reviews}

        enriched_solutions: list[dict[str, Any]] = []
        for solution in solutions:
            index = int(solution.get("solution_index") or 0)
            review = review_by_index.get(index)
            if review:
                enriched_solution = dict(solution)
                enriched_solution.update(
                    {
                        "rating": review.get("rating"),
                        "violations_count": review.get("violations_count"),
                        "total_penalty": review.get("total_penalty"),
                        "violated_soft_constraints": review.get("violated_soft_constraints", []),
                        "explanation": review.get("explanation"),
                    }
                )
                enriched_solutions.append(enriched_solution)
            else:
                enriched_solutions.append(dict(solution))

        solver_result["solutions"] = enriched_solutions
        solver_result["scored_solutions"] = scored_reviews
        solver_result["reflector_result"] = reflector_result

        if has_nested_result:
            stored["result"] = solver_result
        else:
            stored = solver_result

        payload = json.dumps(stored, ensure_ascii=True)
        try:
            current_ttl = redis_client.ttl(key)
        except Exception:
            current_ttl = -1

        if current_ttl and current_ttl > 0:
            redis_client.setex(key, current_ttl, payload)
        else:
            redis_client.set(key, payload)

        logger.info("Wrote reflector scores back to Redis key: %s", key)
    except Exception as exc:
        logger.exception("Failed to write reflector scores to Redis for %s: %s", request_id, exc)


def _build_compromised_reviews(solutions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evaluator = ReflectorEvaluator()
    # evaluator.score_solutions already sorts and returns review dicts
    return evaluator.score_solutions(solutions)


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


def _build_strategic_relaxations(solver_result: dict[str, Any], solver_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Use evaluator to recommend weight adjustments to get a feasible run next."""
    solutions = solver_result.get("solutions") or []
    evaluator = ReflectorEvaluator()
    adjustments = evaluator.suggest_weight_adjustments(solutions, solver_payload)

    # Convert adjustments to patch-like hints
    patches: list[dict[str, Any]] = []
    for adj in adjustments:
        patches.append({
            "op": "set",
            "path": f"constraint_rules.{adj['rule']}.weight",
            "value": adj["suggested_weight"],
            "reason": adj["reason"],
        })
    return patches


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
