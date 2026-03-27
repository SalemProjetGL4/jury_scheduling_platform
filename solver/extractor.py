from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from solver.variables import ROLES, VariableBundle


def extract_assignments(
    solver: cp_model.CpSolver,
    data: dict[str, Any],
    vars_: VariableBundle,
) -> list[dict[str, Any]]:
    projects = data["projects"]
    sessions = data["sessions"]

    assignments: list[dict[str, Any]] = []

    for project in projects:
        project_id = project["id"]
        active_session = next(
            (session for session in sessions if solver.Value(vars_.y[(project_id, session["id"])]) == 1),
            None,
        )
        if active_session is None:
            continue

        role_assignments: dict[str, int] = {}
        for role in ROLES:
            assigned_professor = None
            for professor in data["professors"]:
                pid = professor["id"]
                if solver.Value(vars_.x[(pid, project_id, role, active_session["id"])]) == 1:
                    assigned_professor = pid
                    break
            if assigned_professor is not None:
                role_assignments[role.lower()] = assigned_professor

        assignments.append(
            {
                "project_id": project_id,
                "session_id": active_session["id"],
                "date": active_session.get("date"),
                "period": active_session.get("period"),
                "roles": role_assignments,
            }
        )

    return assignments


def build_infeasibility_report(data: dict[str, Any]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []

    sessions = data.get("sessions", [])
    projects = data.get("projects", [])
    professors = data.get("professors", [])

    if not sessions:
        violations.append({"constraint": "sessions_non_empty", "reason": "No sessions provided"})
    if not projects:
        violations.append({"constraint": "projects_non_empty", "reason": "No projects provided"})
    if not professors:
        violations.append({"constraint": "professors_non_empty", "reason": "No professors provided"})

    # Quick static checks to return useful diagnostics before model solve.
    professor_ids = {p["id"] for p in professors}
    for project in projects:
        if project.get("supervisor_id") not in professor_ids:
            violations.append(
                {
                    "constraint": "supervisor_exists",
                    "reason": f"Project {project.get('id')} has unknown supervisor {project.get('supervisor_id')}",
                }
            )

    if len(sessions) < len(projects):
        violations.append(
            {
                "constraint": "project_slot_capacity",
                "reason": "Number of sessions is less than number of projects",
            }
        )

    return violations
