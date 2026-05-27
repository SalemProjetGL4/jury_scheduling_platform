from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model

from solver.constraints.rule_utils import collect_rule_specs
from solver.variables import ROLES, VariableBundle


@dataclass
class SoftTerms:
    workload_balance: cp_model.LinearExpr
    expertise_penalty: cp_model.LinearExpr
    clustering_penalty: cp_model.LinearExpr
    overload_penalty: cp_model.LinearExpr
    custom_penalty: cp_model.LinearExpr


def build_soft_terms(
    model: cp_model.CpModel,
    data: dict[str, Any],
    vars_: VariableBundle,
    session_load_vars: dict[tuple[int, int], cp_model.IntVar],
) -> SoftTerms:
    professors = data["professors"]
    projects = data["projects"]
    sessions = data["sessions"]

    professor_ids = [p["id"] for p in professors]
    project_ids = [p["id"] for p in projects]

    max_total_assignments = len(projects) * len(ROLES)
    load_vars: dict[int, cp_model.IntVar] = {}
    for pid in professor_ids:
        load = model.NewIntVar(0, max_total_assignments, f"load_p{pid}")
        # Reuse session_load_vars computed by hard constraints — avoids recomputing 5M-term sums.
        model.Add(load == sum(session_load_vars[(pid, s["id"])] for s in sessions))
        load_vars[pid] = load

    # Workload balancing with scaled absolute deviation from average.
    # scaled_diff = |load * n_prof - total_assignments|
    total_assignments = len(projects) * len(ROLES)
    n_prof = max(1, len(professors))
    deviation_vars: list[cp_model.IntVar] = []
    for pid in professor_ids:
        dev = model.NewIntVar(0, total_assignments * n_prof, f"workload_dev_p{pid}")
        lhs = load_vars[pid] * n_prof - total_assignments
        model.Add(dev >= lhs)
        model.Add(dev >= -lhs)
        deviation_vars.append(dev)

    workload_balance = sum(deviation_vars)

    # Expertise penalty for president/examiner assignments that do not match project domain.
    professor_by_id = {p["id"]: p for p in professors}
    project_by_id = {p["id"]: p for p in projects}
    expertise_terms: list[cp_model.IntVar] = []
    for pid in professor_ids:
        for pr_id in project_ids:
            professor_domain = professor_by_id[pid].get("domain_id")
            project_domain = project_by_id[pr_id].get("domain_id")
            is_match = professor_domain == project_domain
            if is_match:
                continue
            for role in ("PRESIDENT", "EXAMINER"):
                for session in sessions:
                    expertise_terms.append(vars_.x[(pid, pr_id, role, session["id"])])

    expertise_penalty = sum(expertise_terms) if expertise_terms else 0

    # Same-day clustering: minimize number of active days by professor.
    # Use session_load_vars instead of per-project x-var lists — reduces 5M dict lookups to ~11K.
    sessions_by_day: dict[str, list[int]] = defaultdict(list)
    for session in sessions:
        sessions_by_day[str(session["date"])].append(session["id"])

    max_sessions_per_day = max((len(sids) for sids in sessions_by_day.values()), default=1)

    day_used_terms: list[cp_model.IntVar] = []
    for pid in professor_ids:
        for day, session_ids_for_day in sessions_by_day.items():
            used = model.NewBoolVar(f"day_used_p{pid}_{day}")
            day_load = sum(session_load_vars[(pid, sid)] for sid in session_ids_for_day)
            model.Add(day_load <= max_sessions_per_day * used)
            model.Add(day_load >= used)
            day_used_terms.append(used)

    clustering_penalty = sum(day_used_terms) if day_used_terms else 0

    # Workload cap overrun penalty.
    overload_vars: list[cp_model.IntVar] = []
    for professor in professors:
        pid = professor["id"]
        cap = int(professor.get("max_juries", total_assignments))
        overload = model.NewIntVar(0, total_assignments, f"overload_p{pid}")
        model.Add(overload >= load_vars[pid] - cap)
        overload_vars.append(overload)

    overload_penalty = sum(overload_vars)

    custom_penalty = build_custom_soft_penalty(
        model=model,
        data=data,
        vars_=vars_,
        professor_ids=professor_ids,
        project_ids=project_ids,
        sessions=sessions,
    )

    return SoftTerms(
        workload_balance=workload_balance,
        expertise_penalty=expertise_penalty,
        clustering_penalty=clustering_penalty,
        overload_penalty=overload_penalty,
        custom_penalty=custom_penalty,
    )


def build_custom_soft_penalty(
    model: cp_model.CpModel,
    data: dict[str, Any],
    vars_: VariableBundle,
    professor_ids: list[int],
    project_ids: list[int],
    sessions: list[dict[str, Any]],
) -> cp_model.LinearExpr:
    professor_id_set = set(professor_ids)
    project_id_set = set(project_ids)
    session_ids = [s["id"] for s in sessions]
    session_id_set = set(session_ids)
    session_by_id = {s["id"]: s for s in sessions}

    penalty_terms: list[cp_model.LinearExpr] = []

    for rule in collect_rule_specs(data, "soft"):
        name = rule.name
        payload = rule.payload
        weight = rule.weight

        if name == "prefer_project_session":
            project_id = _as_int(payload.get("project_id"))
            session_id = _as_int(payload.get("session_id"))
            if project_id not in project_id_set or session_id not in session_id_set:
                continue

            miss = model.NewBoolVar(f"soft_miss_project_{project_id}_session_{session_id}")
            model.Add(miss + vars_.y[(project_id, session_id)] == 1)
            penalty_terms.append(weight * miss)

        elif name == "prefer_professor_role":
            professor_id = _as_int(payload.get("professor_id"))
            project_id = _as_int(payload.get("project_id"))
            role = str(payload.get("role", "")).upper()
            session_id = _as_int(payload.get("session_id"))

            if professor_id not in professor_id_set or project_id not in project_id_set or role not in ROLES:
                continue

            if session_id is not None and session_id in session_id_set:
                assigned = vars_.x.get((professor_id, project_id, role, session_id))
                if assigned is None:
                    continue
            else:
                role_vars = [v for sid in session_ids if (v := vars_.x.get((professor_id, project_id, role, sid))) is not None]
                if not role_vars:
                    continue
                assigned = model.NewBoolVar(f"soft_assigned_p{professor_id}_pr{project_id}_{role}")
                model.Add(assigned == sum(role_vars))

            miss = model.NewBoolVar(f"soft_miss_p{professor_id}_pr{project_id}_{role}")
            model.Add(miss + assigned == 1)
            penalty_terms.append(weight * miss)

        elif name == "avoid_professor_session":
            professor_id = _as_int(payload.get("professor_id"))
            session_id = _as_int(payload.get("session_id"))
            if professor_id not in professor_id_set or session_id not in session_id_set:
                continue

            session_load = model.NewIntVar(0, len(project_ids) * len(ROLES), f"soft_avoid_p{professor_id}_s{session_id}")
            model.Add(
                session_load
                == sum(
                    v
                    for project_id in project_ids
                    for role in ROLES
                    if (v := vars_.x.get((professor_id, project_id, role, session_id))) is not None
                )
            )
            penalty_terms.append(weight * session_load)

        elif name == "penalize_professor_project":
            professor_id = _as_int(payload.get("professor_id"))
            project_id = _as_int(payload.get("project_id"))
            roles = _normalize_roles(payload.get("roles"))
            if professor_id not in professor_id_set or project_id not in project_id_set:
                continue

            penalize_vars = [
                v
                for role in roles
                for sid in session_ids
                if (v := vars_.x.get((professor_id, project_id, role, sid))) is not None
            ]
            if not penalize_vars:
                continue
            assignment_count = model.NewIntVar(0, len(penalize_vars), f"soft_penalize_p{professor_id}_pr{project_id}")
            model.Add(assignment_count == sum(penalize_vars))
            penalty_terms.append(weight * assignment_count)

        elif name == "prefer_morning":
            for session_id in session_ids:
                session_period = str(session_by_id[session_id].get("period", "morning")).lower()
                if session_period == "morning":
                    continue
                afternoon_count = model.NewIntVar(
                    0,
                    len(professor_ids) * len(project_ids) * len(ROLES),
                    f"soft_afternoon_count_s{session_id}",
                )
                model.Add(
                    afternoon_count
                    == sum(
                        v
                        for professor_id in professor_ids
                        for project_id in project_ids
                        for role in ROLES
                        if (v := vars_.x.get((professor_id, project_id, role, session_id))) is not None
                    )
                )
                penalty_terms.append(weight * afternoon_count)

    return sum(penalty_terms) if penalty_terms else 0


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
