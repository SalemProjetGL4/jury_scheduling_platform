from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from solver.cp_sat_model import build_model
from solver.extractor import build_infeasibility_report, extract_assignments


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

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0

    status = solver.Solve(bundle.model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": solver.StatusName(status),
            "assignments": extract_assignments(solver, data, bundle.vars_),
        }

    return {
        "status": "INFEASIBLE",
        "failed_constraints": [
            {
                "constraint": "cp_sat_solve",
                "reason": "Model has no feasible solution with current hard constraints",
            }
        ],
    }
