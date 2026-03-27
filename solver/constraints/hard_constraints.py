from __future__ import annotations

from collections import defaultdict
from typing import Any

from ortools.sat.python import cp_model

from solver.constraints.rule_utils import collect_rule_specs
from solver.variables import ROLES, VariableBundle


def apply_hard_constraints(model: cp_model.CpModel, data: dict[str, Any], vars_: VariableBundle) -> None:
    professors = data["professors"]
    projects = data["projects"]
    sessions = data["sessions"]

    professor_ids = [p["id"] for p in professors]
    max_juries_per_professor = _as_int(data.get("constraints", {}).get("hard_max_juries", 2))
    if max_juries_per_professor is None or max_juries_per_professor < 0:
        max_juries_per_professor = 2

    # Every project is scheduled in exactly one session.
    for project in projects:
        project_id = project["id"]
        model.Add(sum(vars_.y[(project_id, session["id"])] for session in sessions) == 1)

    # Role uniqueness and role/session linkage.
    for project in projects:
        project_id = project["id"]
        for role in ROLES:
            model.Add(
                sum(vars_.x[(pid, project_id, role, s["id"])] for pid in professor_ids for s in sessions) == 1
            )
            for session in sessions:
                session_id = session["id"]
                model.Add(sum(vars_.x[(pid, project_id, role, session_id)] for pid in professor_ids) == vars_.y[(project_id, session_id)])

    # One role per professor per session.
    for pid in professor_ids:
        for session in sessions:
            session_id = session["id"]
            model.Add(
                sum(vars_.x[(pid, project["id"], role, session_id)] for project in projects for role in ROLES) <= 1
            )

    # Base cap: each professor can serve in at most two juries overall.
    for pid in professor_ids:
        model.Add(
            sum(
                vars_.x[(pid, project["id"], role, session["id"])]
                for project in projects
                for role in ROLES
                for session in sessions
            )
            <= max_juries_per_professor
        )

    # Supervisor role is fixed to the project's supervisor only.
    for project in projects:
        project_id = project["id"]
        supervisor_id = project["supervisor_id"]
        for session in sessions:
            session_id = session["id"]
            model.Add(vars_.x[(supervisor_id, project_id, "SUPERVISOR", session_id)] == vars_.y[(project_id, session_id)])
            for pid in professor_ids:
                if pid != supervisor_id:
                    model.Add(vars_.x[(pid, project_id, "SUPERVISOR", session_id)] == 0)

    # Half-day exclusivity per professor/day.
    sessions_by_day_period: dict[tuple[str, str], list[int]] = defaultdict(list)
    day_values: set[str] = set()
    for session in sessions:
        day = str(session["date"])
        period = str(session.get("period", "morning")).lower()
        sessions_by_day_period[(day, period)].append(session["id"])
        day_values.add(day)

    for pid in professor_ids:
        for day in sorted(day_values):
            morning_b = model.NewBoolVar(f"morning_p{pid}_{day}")
            afternoon_b = model.NewBoolVar(f"afternoon_p{pid}_{day}")

            morning_sessions = sessions_by_day_period.get((day, "morning"), [])
            afternoon_sessions = sessions_by_day_period.get((day, "afternoon"), [])

            morning_sum = sum(
                vars_.x[(pid, project["id"], role, sid)]
                for sid in morning_sessions
                for project in projects
                for role in ROLES
            )
            afternoon_sum = sum(
                vars_.x[(pid, project["id"], role, sid)]
                for sid in afternoon_sessions
                for project in projects
                for role in ROLES
            )

            model.Add(morning_sum <= max(1, len(morning_sessions)) * morning_b)
            model.Add(afternoon_sum <= max(1, len(afternoon_sessions)) * afternoon_b)
            model.Add(morning_sum >= morning_b)
            model.Add(afternoon_sum >= afternoon_b)
            model.Add(morning_b + afternoon_b <= 1)

    # Unavailability exclusions.
    unavailability_by_prof: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for item in data.get("unavailabilities", []):
        unavailability_by_prof[item["professor_id"]].append((str(item["date"]), str(item["period"]).lower()))

    for professor in professors:
        pid = professor["id"]
        for blocked_day, blocked_period in unavailability_by_prof.get(pid, []):
            for session in sessions:
                if str(session["date"]) != blocked_day:
                    continue
                session_period = str(session.get("period", "morning")).lower()
                if blocked_period == "full_day" or blocked_period == session_period:
                    for project in projects:
                        for role in ROLES:
                            model.Add(vars_.x[(pid, project["id"], role, session["id"])] == 0)

    # Conflict of interest: conflicting professors cannot both be on same project/session.
    for pair in data.get("conflicts", []):
        p1 = pair["professor_a"]
        p2 = pair["professor_b"]
        for project in projects:
            project_id = project["id"]
            for session in sessions:
                session_id = session["id"]
                model.Add(
                    sum(vars_.x[(p1, project_id, role, session_id)] for role in ROLES)
                    + sum(vars_.x[(p2, project_id, role, session_id)] for role in ROLES)
                    <= 1
                )

    apply_custom_hard_constraints(model, data, vars_)


def apply_custom_hard_constraints(model: cp_model.CpModel, data: dict[str, Any], vars_: VariableBundle) -> None:
    professors = data.get("professors", [])
    projects = data.get("projects", [])
    sessions = data.get("sessions", [])

    professor_ids = {p["id"] for p in professors}
    project_ids = {p["id"] for p in projects}
    session_ids = [s["id"] for s in sessions]
    session_id_set = set(session_ids)

    for rule in collect_rule_specs(data, "hard"):
        name = rule.name
        payload = rule.payload

        if name == "forbid_professor_session":
            professor_id = _as_int(payload.get("professor_id"))
            session_id = _as_int(payload.get("session_id"))
            if professor_id not in professor_ids or session_id not in session_id_set:
                continue

            for project in projects:
                project_id = project["id"]
                for role in ROLES:
                    model.Add(vars_.x[(professor_id, project_id, role, session_id)] == 0)

        elif name == "forbid_professor_project":
            professor_id = _as_int(payload.get("professor_id"))
            project_id = _as_int(payload.get("project_id"))
            if professor_id not in professor_ids or project_id not in project_ids:
                continue

            for role in _normalize_roles(payload.get("roles")):
                for session_id in session_ids:
                    model.Add(vars_.x[(professor_id, project_id, role, session_id)] == 0)

        elif name == "require_professor_role":
            professor_id = _as_int(payload.get("professor_id"))
            project_id = _as_int(payload.get("project_id"))
            role = str(payload.get("role", "")).upper()
            session_id = _as_int(payload.get("session_id"))

            if professor_id not in professor_ids or project_id not in project_ids or role not in ROLES:
                continue

            if session_id is not None and session_id in session_id_set:
                model.Add(vars_.x[(professor_id, project_id, role, session_id)] == 1)
            else:
                model.Add(sum(vars_.x[(professor_id, project_id, role, sid)] for sid in session_ids) == 1)

        elif name == "require_project_session":
            project_id = _as_int(payload.get("project_id"))
            session_id = _as_int(payload.get("session_id"))
            if project_id not in project_ids or session_id not in session_id_set:
                continue
            model.Add(vars_.y[(project_id, session_id)] == 1)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_roles(raw_roles: Any) -> tuple[str, ...]:
    if isinstance(raw_roles, str):
        roles = [raw_roles.upper()]
    elif isinstance(raw_roles, list):
        roles = [str(role).upper() for role in raw_roles]
    else:
        roles = list(ROLES)

    normalized = tuple(role for role in roles if role in ROLES)
    return normalized or ROLES
