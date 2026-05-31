from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from solver.constraints.rule_utils import WEIGHT_SCALE, collect_rule_specs, normalize_weight
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
                var = vars_.x.get((pid, project_id, role, active_session["id"]))
                if var is not None and solver.Value(var) == 1:
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

    # Professor capacity check: SUPERVISOR is mandatory (not capped), so only the two voluntary
    # roles — PRESIDENT and EXAMINER — count against max_juries. Each project needs 2 voluntary
    # role-assignments; total voluntary capacity must be ≥ projects × 2.
    if professors:
        total_voluntary_capacity = sum(p.get("max_juries", 2) for p in professors)
        voluntary_roles_needed = len(projects) * 2  # PRESIDENT + EXAMINER only
        if total_voluntary_capacity < voluntary_roles_needed:
            avg_cap = total_voluntary_capacity // len(professors)
            min_cap_needed = -(-voluntary_roles_needed // len(professors))  # ceiling division
            violations.append(
                {
                    "constraint": "professor_capacity",
                    "reason": (
                        f"{len(professors)} professors × avg max_juries={avg_cap} "
                        f"= {total_voluntary_capacity} voluntary jury slots, but "
                        f"{len(projects)} projects × 2 voluntary roles (PRESIDENT+EXAMINER) "
                        f"= {voluntary_roles_needed} needed. "
                        f"Set max_juries ≥ {min_cap_needed} per professor "
                        f"or reduce projects to ≤ {total_voluntary_capacity // 2}."
                    ),
                    "details": {
                        "professors_count": len(professors),
                        "total_voluntary_capacity": total_voluntary_capacity,
                        "projects_count": len(projects),
                        "voluntary_roles_per_project": 2,
                        "voluntary_roles_needed": voluntary_roles_needed,
                        "deficit": voluntary_roles_needed - total_voluntary_capacity,
                        "min_max_juries_needed": min_cap_needed,
                        "max_projects_feasible": total_voluntary_capacity // 2,
                    },
                }
            )

    return violations


def evaluate_soft_constraint_violations(
    data: dict[str, Any],
    assignments: list[dict[str, Any]],
) -> dict[str, Any]:
    sessions_by_id = {session["id"]: session for session in data.get("sessions", [])}
    assignment_by_project = {assignment["project_id"]: assignment for assignment in assignments}
    unsatisfied: list[dict[str, Any]] = []

    for idx, rule in enumerate(collect_rule_specs(data, "soft"), start=1):
        payload = rule.payload
        violation = 0

        if rule.name == "prefer_project_session":
            project_id = _as_int(payload.get("project_id"))
            session_id = _as_int(payload.get("session_id"))
            if project_id is not None and session_id is not None:
                assigned = assignment_by_project.get(project_id)
                violation = 0 if assigned and assigned.get("session_id") == session_id else 1

        elif rule.name == "prefer_professor_role":
            professor_id = _as_int(payload.get("professor_id"))
            project_id = _as_int(payload.get("project_id"))
            role = str(payload.get("role", "")).lower()
            session_id = _as_int(payload.get("session_id"))
            if professor_id is not None and project_id is not None and role:
                assigned = assignment_by_project.get(project_id)
                is_assigned = bool(assigned and assigned.get("roles", {}).get(role) == professor_id)
                if session_id is not None:
                    is_assigned = is_assigned and bool(assigned and assigned.get("session_id") == session_id)
                violation = 0 if is_assigned else 1

        elif rule.name == "avoid_professor_session":
            professor_id = _as_int(payload.get("professor_id"))
            session_id = _as_int(payload.get("session_id"))
            if professor_id is not None and session_id is not None:
                for assignment in assignments:
                    if assignment.get("session_id") != session_id:
                        continue
                    if professor_id in assignment.get("roles", {}).values():
                        violation += 1

        elif rule.name == "penalize_professor_project":
            professor_id = _as_int(payload.get("professor_id"))
            project_id = _as_int(payload.get("project_id"))
            roles = _normalize_roles(payload.get("roles"))
            if professor_id is not None and project_id is not None:
                assigned = assignment_by_project.get(project_id)
                if assigned:
                    assigned_roles = assigned.get("roles", {})
                    for role in roles:
                        if assigned_roles.get(role.lower()) == professor_id:
                            violation += 1

        elif rule.name == "prefer_morning":
            for assignment in assignments:
                session = sessions_by_id.get(assignment.get("session_id"), {})
                period = str(session.get("period", assignment.get("period", "morning"))).lower()
                if period == "morning":
                    continue
                violation += len(ROLES)

        if violation <= 0:
            continue

        penalty = rule.weight * violation
        unsatisfied.append(
            {
                "rule_index": idx,
                "rule": rule.name,
                "payload": payload,
                "weight_scaled": rule.weight,
                "weight": round(rule.weight / WEIGHT_SCALE, 2),
                "violation": violation,
                "penalty": penalty,
                "penalty_weighted": round(penalty / WEIGHT_SCALE, 2),
            }
        )

    # --- Built-in penalties detection (workload, expertise, clustering, overload)
    professors = data.get("professors", [])
    projects = data.get("projects", [])
    sessions = data.get("sessions", [])
    professor_by_id = {p["id"]: p for p in professors}
    project_by_id = {pr["id"]: pr for pr in projects}

    # We will enumerate built-in checks after the user-provided soft rules
    base_idx = len(list(collect_rule_specs(data, "soft")))
    weights = data.get("constraints", {}).get("weights", {})

    # Workload balance: sum |load * n_prof - total_assignments|
    n_prof = max(1, len(professors))
    total_assignments = len(projects) * len(ROLES)
    prof_loads: dict[int, int] = {p["id"]: 0 for p in professors}
    for assignment in assignments:
        for role_key in ("president", "examiner"):
            pid = assignment.get("roles", {}).get(role_key)
            if pid is not None and pid in prof_loads:
                prof_loads[pid] += 1

    workload_violation = 0
    for pid, load in prof_loads.items():
        lhs = load * n_prof - total_assignments
        workload_violation += abs(int(lhs))

    workload_w = normalize_weight(weights.get("workload", 10), default=10)
    if workload_violation > 0:
        penalty = workload_w * workload_violation
        unsatisfied.append(
            {
                "rule_index": base_idx + 1,
                "rule": "workload",
                "payload": {},
                "weight_scaled": workload_w,
                "weight": round(workload_w / WEIGHT_SCALE, 2),
                "violation": workload_violation,
                "penalty": penalty,
                "penalty_weighted": round(penalty / WEIGHT_SCALE, 2),
            }
        )

    # Expertise: count president/examiner assignments that don't match domain/keywords
    def _normalize_keywords(values: list[Any]) -> set[str]:
        tokens: set[str] = set()
        for item in values:
            if not item:
                continue
            raw = str(item)
            for part in raw.replace(",", " ").replace(";", " ").split():
                token = part.strip().lower()
                if token:
                    tokens.add(token)
        return tokens

    expertise_violation = 0
    for assignment in assignments:
        proj_id = assignment.get("project_id")
        proj = project_by_id.get(proj_id)
        if not proj:
            continue
        project_domain_ids = set(proj.get("domain_ids") or ([] if proj.get("domain_id") is None else [proj.get("domain_id")]))
        for role_key in ("president", "examiner"):
            pid = assignment.get("roles", {}).get(role_key)
            if pid is None:
                continue
            prof = professor_by_id.get(pid)
            if not prof:
                continue
            prof_domain = prof.get("domain_id")
            prof_dept = prof.get("department_id")
            proj_filiere_dept = proj.get("filiere_department_id")
            # Domain-first matching: domain mismatch is more severe; if domain matches,
            # prefer professor in same filiere's department.
            if not prof_domain or prof_domain not in project_domain_ids:
                # domain mismatch — count as 2
                expertise_violation += 2
            else:
                # domain matches; penalize if professor's department != student's filière department
                if proj_filiere_dept and prof_dept != proj_filiere_dept:
                    expertise_violation += 1

    expertise_w = normalize_weight(weights.get("expertise", 5), default=5)
    if expertise_violation > 0:
        penalty = expertise_w * expertise_violation
        unsatisfied.append(
            {
                "rule_index": base_idx + 2,
                "rule": "expertise",
                "payload": {},
                "weight_scaled": expertise_w,
                "weight": round(expertise_w / WEIGHT_SCALE, 2),
                "violation": expertise_violation,
                "penalty": penalty,
                "penalty_weighted": round(penalty / WEIGHT_SCALE, 2),
            }
        )

    # Clustering: number of used days per professor (non-zero indicates penalty)
    prof_days: dict[int, set[str]] = {p["id"]: set() for p in professors}
    sessions_by_id = {s["id"]: s for s in sessions}
    for assignment in assignments:
        sid = assignment.get("session_id")
        sess = sessions_by_id.get(sid)
        if not sess:
            continue
        date = str(sess.get("date"))
        for pid in assignment.get("roles", {}).values():
            prof_days.setdefault(pid, set()).add(date)

    clustering_violation = 0
    for pid, days in prof_days.items():
        clustering_violation += len(days)

    clustering_w = normalize_weight(weights.get("clustering", 3), default=3)
    if clustering_violation > 0:
        penalty = clustering_w * clustering_violation
        unsatisfied.append(
            {
                "rule_index": base_idx + 3,
                "rule": "clustering",
                "payload": {},
                "weight_scaled": clustering_w,
                "weight": round(clustering_w / WEIGHT_SCALE, 2),
                "violation": clustering_violation,
                "penalty": penalty,
                "penalty_weighted": round(penalty / WEIGHT_SCALE, 2),
            }
        )

    # Overload: voluntary assignments beyond professor.max_juries
    overload_violation = 0
    for p in professors:
        pid = p["id"]
        cap = int(p.get("max_juries", 2))
        assigned = prof_loads.get(pid, 0)
        if assigned > cap:
            overload_violation += assigned - cap

    overload_w = normalize_weight(weights.get("overload", 20), default=20)
    if overload_violation > 0:
        penalty = overload_w * overload_violation
        unsatisfied.append(
            {
                "rule_index": base_idx + 4,
                "rule": "overload",
                "payload": {},
                "weight_scaled": overload_w,
                "weight": round(overload_w / WEIGHT_SCALE, 2),
                "violation": overload_violation,
                "penalty": penalty,
                "penalty_weighted": round(penalty / WEIGHT_SCALE, 2),
            }
        )

    return {"unsatisfied_soft_constraints": unsatisfied}


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
