from __future__ import annotations

from collections import defaultdict
from typing import Any

from ortools.sat.python import cp_model

from solver.constraints.assumptions import AssumptionRegistry
from solver.constraints.rule_utils import collect_rule_specs
from solver.variables import ROLES, VariableBundle


def apply_hard_constraints(
    model: cp_model.CpModel,
    data: dict[str, Any],
    vars_: VariableBundle,
    *,
    assumption_registry: AssumptionRegistry | None = None,
) -> dict[tuple[int, int], cp_model.IntVar]:
    professors = data["professors"]
    projects = data["projects"]
    sessions = data["sessions"]

    professor_ids = [p["id"] for p in professors]
    project_ids = [p["id"] for p in projects]
    session_ids = [s["id"] for s in sessions]

    max_juries_per_professor = _as_int(data.get("constraints", {}).get("hard_max_juries", 2))
    if max_juries_per_professor is None or max_juries_per_professor < 0:
        max_juries_per_professor = 2

    from solver.variables import NON_SUPERVISOR_ROLES

    # Precompute supervisor map: prof_id → list of project_ids they supervise.
    # Used to look up SUPERVISOR variables without expensive .get() calls.
    supervisor_by_prof: dict[int, list[int]] = defaultdict(list)
    for project in projects:
        supervisor_by_prof[project["supervisor_id"]].append(project["id"])

    # Every project is scheduled in exactly one session.
    for project in projects:
        project_id = project["id"]
        assumption = _new_assumption(
            assumption_registry,
            key="project_scheduled_once",
            reason="Project must be scheduled in exactly one session",
            details={"project_id": project_id},
        )
        _add_constraint(
            model,
            sum(vars_.y[(project_id, session["id"])] for session in sessions) == 1,
            assumption,
        )

    # Each session holds at most 1 project.
    for session in sessions:
        session_id = session["id"]
        assumption_cap = _new_assumption(
            assumption_registry,
            key="one_project_per_session",
            reason="Each session slot can host at most one project defense",
            details={"session_id": session_id},
        )
        _add_constraint(
            model,
            sum(vars_.y[(project["id"], session_id)] for project in projects) <= 1,
            assumption_cap,
        )

    # Role uniqueness and role/session linkage.
    # SUPERVISOR: only one variable exists per (project, session) — for the actual supervisor.
    # PRESIDENT/EXAMINER: all professor variables exist.
    for project in projects:
        project_id = project["id"]
        supervisor_id = project["supervisor_id"]

        # --- SUPERVISOR role ---
        assumption_sv = _new_assumption(
            assumption_registry,
            key="role_unique_per_project",
            reason="Each project must have exactly one professor for the role",
            details={"project_id": project_id, "role": "SUPERVISOR"},
        )
        _add_constraint(
            model,
            sum(vars_.x[(supervisor_id, project_id, "SUPERVISOR", s["id"])] for s in sessions) == 1,
            assumption_sv,
        )
        for session in sessions:
            session_id = session["id"]
            assumption_link = _new_assumption(
                assumption_registry,
                key="role_session_link",
                reason="Supervisor assignment must match the session where the project is scheduled",
                details={"project_id": project_id, "role": "SUPERVISOR", "session_id": session_id},
            )
            _add_constraint(
                model,
                vars_.x[(supervisor_id, project_id, "SUPERVISOR", session_id)]
                == vars_.y[(project_id, session_id)],
                assumption_link,
            )

        # --- PRESIDENT / EXAMINER roles ---
        for role in NON_SUPERVISOR_ROLES:
            assumption = _new_assumption(
                assumption_registry,
                key="role_unique_per_project",
                reason="Each project must have exactly one professor for the role",
                details={"project_id": project_id, "role": role},
            )
            _add_constraint(
                model,
                sum(vars_.x[(pid, project_id, role, s["id"])] for pid in professor_ids for s in sessions) == 1,
                assumption,
            )
            for session in sessions:
                session_id = session["id"]
                assumption_link = _new_assumption(
                    assumption_registry,
                    key="role_session_link",
                    reason="Role assignments must match the session where the project is scheduled",
                    details={"project_id": project_id, "role": role, "session_id": session_id},
                )
                _add_constraint(
                    model,
                    sum(vars_.x[(pid, project_id, role, session_id)] for pid in professor_ids)
                    == vars_.y[(project_id, session_id)],
                    assumption_link,
                )

    # One role per professor per session + max juries cap.
    #
    # Optimisation: instead of a single giant sum over all projects × roles × sessions
    # (which creates 91 K-term OR-Tools expressions), we introduce a per-(prof, slot)
    # IntVar `session_load` that captures the number of role-assignments in that slot.
    # - session_load ≤ 1  →  one_role_per_professor_session
    # - Σ session_load ≤ max_juries  →  max_juries_per_professor (194-term sum instead of 92 K)
    #
    # For PRESIDENT/EXAMINER: all professor × project combinations have variables — direct access.
    # For SUPERVISOR: only the actual supervisor has a variable — looked up from supervisor_by_prof.
    session_load_vars: dict[tuple[int, int], cp_model.IntVar] = {}

    for pid in professor_ids:
        supervised_project_ids = supervisor_by_prof.get(pid, [])
        for session in sessions:
            session_id = session["id"]
            # PRESIDENT/EXAMINER: direct access, no .get() needed
            role_terms = [
                vars_.x[(pid, pr_id, role, session_id)]
                for pr_id in project_ids
                for role in NON_SUPERVISOR_ROLES
            ]
            # SUPERVISOR: only the projects this professor supervises
            for pr_id in supervised_project_ids:
                role_terms.append(vars_.x[(pid, pr_id, "SUPERVISOR", session_id)])

            session_load = model.NewIntVar(0, len(role_terms), f"sl_{pid}_{session_id}")
            model.Add(session_load == sum(role_terms))

            assumption = _new_assumption(
                assumption_registry,
                key="one_role_per_professor_session",
                reason="Professor can hold at most one role per session",
                details={"professor_id": pid, "session_id": session_id},
            )
            _add_constraint(model, session_load <= 1, assumption)
            session_load_vars[(pid, session_id)] = session_load
    # session_load_vars is returned so soft constraints can reuse it without recomputing.

    # Max juries cap applies only to voluntary (PRESIDENT/EXAMINER) assignments.
    # Supervisor-role assignments are mandatory — a professor must attend every project they supervise,
    # so those do not count against their voluntary jury quota.
    for pid in professor_ids:
        total_load = sum(session_load_vars[(pid, s["id"])] for s in sessions)
        # Sum of mandatory SUPERVISOR assignments for this professor across all sessions.
        mandatory_supervisor_load = sum(
            vars_.x[(pid, pr_id, "SUPERVISOR", s["id"])]
            for pr_id in supervisor_by_prof.get(pid, [])
            for s in sessions
        )
        assumption = _new_assumption(
            assumption_registry,
            key="max_juries_per_professor",
            reason="Professor cannot exceed the maximum number of voluntary (non-supervisor) jury assignments",
            details={"professor_id": pid, "max_juries": max_juries_per_professor},
        )
        _add_constraint(model, total_load <= max_juries_per_professor + mandatory_supervisor_load, assumption)

    # Half-day exclusivity per professor/day.
    # (supervisor_fixed already enforced above via role_session_link for SUPERVISOR role)
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

            assumption = _new_assumption(
                assumption_registry,
                key="half_day_exclusivity",
                reason="Professor cannot serve both morning and afternoon on the same day",
                details={"professor_id": pid, "date": day},
            )

            morning_sessions = sessions_by_day_period.get((day, "morning"), [])
            afternoon_sessions = sessions_by_day_period.get((day, "afternoon"), [])

            # Reuse session_load_vars (already computed above) — avoids re-summing all role terms.
            morning_sum = sum(session_load_vars[(pid, sid)] for sid in morning_sessions) if morning_sessions else 0
            afternoon_sum = sum(session_load_vars[(pid, sid)] for sid in afternoon_sessions) if afternoon_sessions else 0

            _add_constraint(model, morning_sum <= max(1, len(morning_sessions)) * morning_b, assumption)
            _add_constraint(model, afternoon_sum <= max(1, len(afternoon_sessions)) * afternoon_b, assumption)
            _add_constraint(model, morning_sum >= morning_b, assumption)
            _add_constraint(model, afternoon_sum >= afternoon_b, assumption)
            _add_constraint(model, morning_b + afternoon_b <= 1, assumption)

    # Unavailability exclusions.
    unavailability_by_prof: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for item in data.get("unavailabilities", []):
        unavailability_by_prof[item["professor_id"]].append((str(item["date"]), str(item["period"]).lower()))

    for professor in professors:
        pid = professor["id"]
        for blocked_day, blocked_period in unavailability_by_prof.get(pid, []):
            assumption = _new_assumption(
                assumption_registry,
                key="professor_unavailable",
                reason="Professor is unavailable during the specified period",
                details={"professor_id": pid, "date": blocked_day, "period": blocked_period},
            )
            for session in sessions:
                if str(session["date"]) != blocked_day:
                    continue
                session_period = str(session.get("period", "morning")).lower()
                if blocked_period == "full_day" or blocked_period == session_period:
                    for project in projects:
                        for role in ROLES:
                            v = vars_.x.get((pid, project["id"], role, session["id"]))
                            if v is not None:
                                _add_constraint(model, v == 0, assumption)

    # Conflict of interest: conflicting professors cannot both be on same project/session.
    for pair in data.get("conflicts", []):
        p1 = pair["professor_a"]
        p2 = pair["professor_b"]
        for project in projects:
            project_id = project["id"]
            for session in sessions:
                session_id = session["id"]
                assumption = _new_assumption(
                    assumption_registry,
                    key="conflict_of_interest",
                    reason="Conflicting professors cannot serve on the same project/session",
                    details={
                        "professor_a": p1,
                        "professor_b": p2,
                        "project_id": project_id,
                        "session_id": session_id,
                    },
                )
                p1_vars = [v for role in ROLES if (v := vars_.x.get((p1, project_id, role, session_id))) is not None]
                p2_vars = [v for role in ROLES if (v := vars_.x.get((p2, project_id, role, session_id))) is not None]
                if p1_vars or p2_vars:
                    _add_constraint(model, sum(p1_vars + p2_vars) <= 1, assumption)

    apply_custom_hard_constraints(model, data, vars_, assumption_registry=assumption_registry)
    return session_load_vars


def apply_custom_hard_constraints(
    model: cp_model.CpModel,
    data: dict[str, Any],
    vars_: VariableBundle,
    *,
    assumption_registry: AssumptionRegistry | None = None,
) -> None:
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
        assumption = _new_assumption(
            assumption_registry,
            key=f"custom_hard_{name}",
            reason="Custom hard rule",
            details={"rule": name, "payload": payload},
        )

        if name == "forbid_professor_session":
            professor_id = _as_int(payload.get("professor_id"))
            session_id = _as_int(payload.get("session_id"))
            if professor_id not in professor_ids or session_id not in session_id_set:
                continue

            for project in projects:
                project_id = project["id"]
                for role in ROLES:
                    v = vars_.x.get((professor_id, project_id, role, session_id))
                    if v is not None:
                        _add_constraint(model, v == 0, assumption)

        elif name == "forbid_professor_project":
            professor_id = _as_int(payload.get("professor_id"))
            project_id = _as_int(payload.get("project_id"))
            if professor_id not in professor_ids or project_id not in project_ids:
                continue

            for role in _normalize_roles(payload.get("roles")):
                for session_id in session_ids:
                    v = vars_.x.get((professor_id, project_id, role, session_id))
                    if v is not None:
                        _add_constraint(model, v == 0, assumption)

        elif name == "require_professor_role":
            professor_id = _as_int(payload.get("professor_id"))
            project_id = _as_int(payload.get("project_id"))
            role = str(payload.get("role", "")).upper()
            session_id = _as_int(payload.get("session_id"))

            if professor_id not in professor_ids or project_id not in project_ids or role not in ROLES:
                continue

            if session_id is not None and session_id in session_id_set:
                v = vars_.x.get((professor_id, project_id, role, session_id))
                if v is not None:
                    _add_constraint(model, v == 1, assumption)
            else:
                role_vars = [
                    v for sid in session_ids
                    if (v := vars_.x.get((professor_id, project_id, role, sid))) is not None
                ]
                if role_vars:
                    _add_constraint(model, sum(role_vars) == 1, assumption)

        elif name == "require_project_session":
            project_id = _as_int(payload.get("project_id"))
            session_id = _as_int(payload.get("session_id"))
            if project_id not in project_ids or session_id not in session_id_set:
                continue
            _add_constraint(model, vars_.y[(project_id, session_id)] == 1, assumption)


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


def _add_constraint(
    model: cp_model.CpModel,
    expr: cp_model.BoundedLinearExpression,
    assumption: cp_model.BoolVar | None,
) -> None:
    constraint = model.Add(expr)
    if assumption is not None:
        constraint.OnlyEnforceIf(assumption)


def _new_assumption(
    assumption_registry: AssumptionRegistry | None,
    *,
    key: str,
    reason: str,
    details: dict[str, Any] | None = None,
) -> cp_model.BoolVar | None:
    if assumption_registry is None:
        return None
    return assumption_registry.register(key=key, reason=reason, details=details)
