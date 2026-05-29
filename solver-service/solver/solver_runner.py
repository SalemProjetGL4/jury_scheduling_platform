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
    import time
    import logging
    _log = logging.getLogger("solver")

    timing_info: dict[str, float] = {}

    t0 = time.monotonic()
    precheck_violations = build_infeasibility_report(data)
    timing_info["precheck_ms"] = round((time.monotonic() - t0) * 1000)
    _log.info("TIMING precheck: %.2fs", time.monotonic() - t0)
    if precheck_violations:
        return {
            "status": "INFEASIBLE",
            "failed_constraints": precheck_violations,
            "timing_info": timing_info,
        }

    options = data.get("solver_options", {})
    max_solutions = _as_positive_int(options.get("max_solutions"), default=1)
    include_soft_diagnostics = bool(options.get("include_soft_diagnostics", True))

    # Auto-disable conflict refiner for large problems: it adds one BoolVar assumption
    # per constraint (~150K vars for 236 projects × 194 slots), doubling model size and
    # making constraint building 2-3× slower.
    n_proj = len(data.get("projects", []))
    n_slots = len(data.get("sessions", []))
    auto_large = n_proj * n_slots > 10_000
    include_conflict_refiner = bool(options.get("include_conflict_refiner", not auto_large))
    _log.info("SOLVE config — max_solutions=%d conflict_refiner=%s (auto_large=%s)", max_solutions, include_conflict_refiner, auto_large)

    t1 = time.monotonic()
    bundle = build_model(data, include_conflict_refiner=include_conflict_refiner)
    timing_info["model_build_ms"] = round((time.monotonic() - t1) * 1000)
    _log.info("TIMING model_build: %.2fs", time.monotonic() - t1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = options.get("max_time_seconds", 240)
    solver.parameters.num_search_workers = options.get("num_workers", 4)
    # Use caller-supplied seed for reproducibility, or a time-based seed so
    # repeated runs with the same data explore different parts of the solution space.
    _seed = options.get("random_seed")
    solver.parameters.random_seed = int(_seed) if _seed is not None else int(time.time()) % (2 ** 31)

    # For large models, stop as soon as any feasible solution is found rather than
    # spending the full time limit proving optimality. The first feasible solution
    # comes quickly (seconds); proving optimality can take minutes.
    stop_after_first = bool(options.get("stop_after_first_solution", auto_large))

    solutions: list[dict[str, Any]] = []
    _t_solve_pure = 0.0
    _t_extract_total = 0.0

    class _FirstSolutionStopper(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self) -> None:
            self.StopSearch()

    while len(solutions) < max_solutions:
        callback = _FirstSolutionStopper() if stop_after_first else None

        _ts = time.monotonic()
        status = solver.Solve(bundle.model, callback)
        _t_solve_pure += time.monotonic() - _ts

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break

        _te = time.monotonic()
        assignments = extract_assignments(solver, data, bundle.vars_)
        soft_eval = evaluate_soft_constraint_violations(data, assignments)
        _t_extract_total += time.monotonic() - _te

        raw_status = solver.StatusName(status)
        quality_status = _derive_quality_status(raw_status, soft_eval["unsatisfied_soft_constraints"])
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

    timing_info["solve_ms"] = round(_t_solve_pure * 1000)
    timing_info["extract_ms"] = round(_t_extract_total * 1000)

    t_post = time.monotonic()

    if solutions:
        best_objective = min(int(solution["objective_value"]) for solution in solutions)
        for solution in solutions:
            objective_value = int(solution["objective_value"])
            solution["objective_delta_from_best"] = objective_value - best_objective

        first_solution = solutions[0]
        response = {
            "status": first_solution["raw_status"],
            "quality_status": first_solution["status"],
            "assignments": first_solution["assignments"],
            "solutions": solutions,
            "solution_count": len(solutions),
            "solutions_limit_reached": max_solutions > 1 and len(solutions) >= max_solutions,
        }
        timing_info["postprocess_ms"] = round((time.monotonic() - t_post) * 1000)
        response["timing_info"] = timing_info
        return response

    last_status = solver.StatusName(status)
    _log.info("CP-SAT last status: %s", last_status)

    # Distinguish timeout (UNKNOWN) from proven infeasibility (INFEASIBLE).
    if last_status == "UNKNOWN":
        timing_info["postprocess_ms"] = round((time.monotonic() - t_post) * 1000)
        return {
            "status": "INFEASIBLE",
            "failed_constraints": [
                {
                    "constraint": "cp_sat_timeout",
                    "reason": (
                        f"Solver did not find a feasible solution within the time limit "
                        f"({solver.parameters.max_time_in_seconds}s). "
                        "Try increasing SOLVER_MAX_TIME_SECONDS or reducing the problem size."
                    ),
                }
            ],
            "timing_info": timing_info,
        }

    conflict_report: list[dict[str, Any]] = []
    if include_conflict_refiner and bundle.assumptions is not None:
        conflict_report = bundle.assumptions.report_from_literals(
            solver.SufficientAssumptionsForInfeasibility()
        )

    timing_info["postprocess_ms"] = round((time.monotonic() - t_post) * 1000)

    if conflict_report:
        return {
            "status": "INFEASIBLE",
            "failed_constraints": conflict_report,
            "timing_info": timing_info,
        }

    return {
        "status": "INFEASIBLE",
        "failed_constraints": [
            {
                "constraint": "cp_sat_solve",
                "reason": "Model has no feasible solution with current hard constraints",
            }
        ],
        "timing_info": timing_info,
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
            var = vars_.x.get((int(professor_id), project_id, role, session_id))
            if var is not None:
                selected_literals.append(var)

    if selected_literals:
        model.Add(sum(selected_literals) <= len(selected_literals) - 1)


def _as_positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _derive_quality_status(raw_status: str, unsatisfied_soft_constraints: list[dict[str, Any]]) -> str:
    normalized = raw_status.upper()
    if normalized not in {"OPTIMAL", "FEASIBLE"}:
        return normalized
    if not unsatisfied_soft_constraints:
        return "SOFT_OPTIMAL"
    return "SOFT_COMPROMISED"
