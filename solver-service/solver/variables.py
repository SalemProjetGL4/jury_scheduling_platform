from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model


ROLES = ("SUPERVISOR", "PRESIDENT", "EXAMINER")


@dataclass
class VariableBundle:
    x: dict[tuple[int, int, str, int], cp_model.IntVar]
    y: dict[tuple[int, int], cp_model.IntVar]


NON_SUPERVISOR_ROLES = ("PRESIDENT", "EXAMINER")


def build_variables(model: cp_model.CpModel, data: dict[str, Any]) -> VariableBundle:
    professors = data["professors"]
    projects = data["projects"]
    sessions = data["sessions"]

    x: dict[tuple[int, int, str, int], cp_model.IntVar] = {}
    y: dict[tuple[int, int], cp_model.IntVar] = {}

    # y variables: one per (project, slot)
    for project in projects:
        project_id = project["id"]
        for session in sessions:
            session_id = session["id"]
            y[(project_id, session_id)] = model.NewBoolVar(f"y{project_id}_{session_id}")

    # SUPERVISOR variables: only for the project's actual supervisor.
    # The supervisor is hard-fixed — creating variables for other professors wastes memory
    # and balloons the model to millions of variables that are trivially forced to 0.
    for project in projects:
        project_id = project["id"]
        supervisor_id = project["supervisor_id"]
        for session in sessions:
            session_id = session["id"]
            x[(supervisor_id, project_id, "SUPERVISOR", session_id)] = model.NewBoolVar(
                f"xs{supervisor_id}_{project_id}_{session_id}"
            )

    # PRESIDENT / EXAMINER variables: all professors are eligible (domain is a soft preference).
    # Names omitted to avoid 5M string-format calls during model build.
    for professor in professors:
        professor_id = professor["id"]
        for project in projects:
            project_id = project["id"]
            for role in NON_SUPERVISOR_ROLES:
                for session in sessions:
                    session_id = session["id"]
                    x[(professor_id, project_id, role, session_id)] = model.NewBoolVar("")

    return VariableBundle(x=x, y=y)
