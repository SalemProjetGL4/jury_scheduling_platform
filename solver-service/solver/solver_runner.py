from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from solver.cp_sat_model import build_model
from solver.extractor import (
    build_infeasibility_report,
    evaluate_soft_constraint_violations,
    extract_assignments,
)
from solver.variables import ROLES, VariableBundle


def solve(data: dict[str, Any]) -> dict[str, Any]:
    """
    Input: structured JSON
    Output: schedule or infeasibility report
    """
    precheck_violations = build_infeasibility_report(data)
    if precheck_violations:
        return {
            "status": "INFEASIBLE",
            "failed_constraints": precheck_violations,
        }

    bundle = build_model(data)
    options = data.get("solver_options", {})
    max_solutions = _as_positive_int(options.get("max_solutions"), default=1)
    include_soft_diagnostics = bool(options.get("include_soft_diagnostics", True))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0

    solutions: list[dict[str, Any]] = []

    while len(solutions) < max_solutions:
        status = solver.Solve(bundle.model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break

        assignments = extract_assignments(solver, data, bundle.vars_)
        soft_eval = evaluate_soft_constraint_violations(data, assignments)
        raw_status = solver.StatusName(status)
        quality_status = _derive_quality_status(raw_status, soft_eval["custom_soft_penalty_scaled"])
        solution: dict[str, Any] = {
            "solution_index": len(solutions) + 1,
            "status": quality_status,
            "raw_status": raw_status,
            "objective_value": int(round(solver.ObjectiveValue())),
            "assignments": assignments,
        }
        if include_soft_diagnostics:
            solution.update(soft_eval)

        solutions.append(solution)
        _add_no_good_cut(bundle.model, bundle.vars_, assignments)

    if solutions:
        best_objective = min(int(solution["objective_value"]) for solution in solutions)
        best_soft_penalty = min(int(solution.get("custom_soft_penalty_scaled", 0)) for solution in solutions)
        for solution in solutions:
            objective_value = int(solution["objective_value"])
            solution["objective_delta_from_best"] = objective_value - best_objective
            if "custom_soft_penalty_scaled" in solution:
                penalty_scaled = int(solution["custom_soft_penalty_scaled"])
                solution["custom_soft_penalty_delta_from_best_scaled"] = penalty_scaled - best_soft_penalty
                solution["custom_soft_penalty_delta_from_best"] = round(
                    solution["custom_soft_penalty"] - (best_soft_penalty / 100),
                    2,
                )

        first_solution = solutions[0]
        response = {
            "status": first_solution["raw_status"],
            "quality_status": first_solution["status"],
            "assignments": first_solution["assignments"],
            "solutions": solutions,
            "solution_count": len(solutions),
            "solutions_limit_reached": max_solutions > 1 and len(solutions) >= max_solutions,
        }
        if include_soft_diagnostics:
            response["custom_soft_penalty_scaled"] = first_solution["custom_soft_penalty_scaled"]
            response["custom_soft_penalty"] = first_solution["custom_soft_penalty"]
            response["unsatisfied_soft_constraints"] = first_solution["unsatisfied_soft_constraints"]
        return response

    return {
        "status": "INFEASIBLE",
        "failed_constraints": [
            {
                "constraint": "cp_sat_solve",
                "reason": "Model has no feasible solution with current hard constraints",
            }
        ],
    }


def _add_no_good_cut(
    model: cp_model.CpModel,
    vars_: VariableBundle,
    assignments: list[dict[str, Any]],
) -> None:
    selected_literals: list[cp_model.IntVar] = []

    for assignment in assignments:
        project_id = int(assignment["project_id"])
        session_id = int(assignment["session_id"])
        selected_literals.append(vars_.y[(project_id, session_id)])

        roles = assignment.get("roles", {})
        for role in ROLES:
            professor_id = roles.get(role.lower())
            if professor_id is None:
                continue
            selected_literals.append(vars_.x[(int(professor_id), project_id, role, session_id)])

    if selected_literals:
        model.Add(sum(selected_literals) <= len(selected_literals) - 1)


def _as_positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _derive_quality_status(raw_status: str, custom_soft_penalty_scaled: int) -> str:
    normalized = raw_status.upper()
    if normalized not in {"OPTIMAL", "FEASIBLE"}:
        return normalized
    if custom_soft_penalty_scaled <= 0:
        return "SOFT_OPTIMAL"
    return "SOFT_COMPROMISED"
