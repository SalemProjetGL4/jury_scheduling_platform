from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model


ROLES = ("SUPERVISOR", "PRESIDENT", "EXAMINER")


@dataclass
class VariableBundle:
    x: dict[tuple[int, int, str, int], cp_model.IntVar]
    y: dict[tuple[int, int], cp_model.IntVar]


def build_variables(model: cp_model.CpModel, data: dict[str, Any]) -> VariableBundle:
    professors = data["professors"]
    projects = data["projects"]
    sessions = data["sessions"]

    x: dict[tuple[int, int, str, int], cp_model.IntVar] = {}
    y: dict[tuple[int, int], cp_model.IntVar] = {}

    for project in projects:
        project_id = project["id"]
        for session in sessions:
            session_id = session["id"]
            y[(project_id, session_id)] = model.NewBoolVar(f"y_pr{project_id}_s{session_id}")

    for professor in professors:
        professor_id = professor["id"]
        for project in projects:
            project_id = project["id"]
            for role in ROLES:
                for session in sessions:
                    session_id = session["id"]
                    x[(professor_id, project_id, role, session_id)] = model.NewBoolVar(
                        f"x_p{professor_id}_pr{project_id}_{role}_s{session_id}"
                    )

    return VariableBundle(x=x, y=y)
