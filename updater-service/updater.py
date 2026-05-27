"""
updater.py
----------
Takes an existing solution (a list of assignments) and a list of
"override" operations, locks the untouched assignments in place as hard
constraints, injects the overrides as hard constraints, then re-runs the
CP-SAT solver on the whole model.

Supported override operations
──────────────────────────────
  move_professor          – reassign professor P to role R on project PR
                            (and optionally pin it to a specific session S)
  move_project            – reschedule project PR to a specific session S
  swap_professors         – swap the roles of professor A and professor B
                            on the same project (or across two projects for
                            the same role)
  unpin_project           – let the solver freely reschedule project PR
  unpin_professor_role    – let the solver freely reassign professor P's
                            role on project PR
"""

from __future__ import annotations

import copy
from typing import Any

from solver.solver_runner import solve
from solver.variables import ROLES


# ──────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ──────────────────────────────────────────────────────────────────────────────

def update(
    original_data: dict[str, Any],
    existing_assignments: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Parameters
    ----------
    original_data          : the same JSON payload that was sent to /solve
    existing_assignments   : the ``assignments`` list from the previous result
    overrides              : list of override operations (see module docstring)

    Returns
    -------
    A solve-result dict identical in shape to what /solve returns, plus an
    extra ``update_summary`` key describing what was locked / changed.
    """
    data = copy.deepcopy(original_data)
    assignments = copy.deepcopy(existing_assignments)

    # Validate all override operations before touching anything.
    validation_errors = _validate_overrides(data, assignments, overrides)
    if validation_errors:
        return {
            "status": "UPDATE_INVALID",
            "errors": validation_errors,
        }

    # Apply overrides to the in-memory assignment list so we know the
    # *intended* target state, then build hard-constraint pins from it.
    assignments_after, change_log = _apply_overrides_to_assignments(
        data, assignments, overrides
    )

    # Determine which (project, role) pairs are "free" (touched by an override
    # that requires re-solving) vs "pinned" (everything else).
    free_pairs = _collect_free_pairs(overrides, assignments, assignments_after)

    # Build lock constraints for every pair that is NOT free.
    lock_rules = _build_lock_rules(assignments_after, free_pairs)

    # Inject the lock rules into the data payload's constraint_rules.
    data = _inject_rules(data, lock_rules)

    # Solve the enriched model.
    result = solve(data)
    result["update_summary"] = {
        "overrides_applied": change_log,
        "pinned_assignments": len(lock_rules),
        "free_pairs": [
            {"project_id": pr, "role": role} for pr, role in sorted(free_pairs)
        ],
    }
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────────────

def _validate_overrides(
    data: dict[str, Any],
    assignments: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    professor_ids = {p["id"] for p in data.get("professors", [])}
    project_ids = {p["id"] for p in data.get("projects", [])}
    session_ids = {s["id"] for s in data.get("sessions", [])}
    assignment_project_ids = {a["project_id"] for a in assignments}

    for idx, op in enumerate(overrides):
        op_type = op.get("type")
        loc = f"overrides[{idx}]"

        if op_type == "move_professor":
            _check_required(errors, op, loc, ["professor_id", "project_id", "role"])
            _check_ids(errors, op, loc, "professor_id", professor_ids)
            _check_ids(errors, op, loc, "project_id", project_ids)
            _check_in_assignments(errors, op, loc, "project_id", assignment_project_ids)
            _check_role(errors, op, loc)
            if "session_id" in op:
                _check_ids(errors, op, loc, "session_id", session_ids)

        elif op_type == "move_project":
            _check_required(errors, op, loc, ["project_id", "session_id"])
            _check_ids(errors, op, loc, "project_id", project_ids)
            _check_in_assignments(errors, op, loc, "project_id", assignment_project_ids)
            _check_ids(errors, op, loc, "session_id", session_ids)

        elif op_type == "swap_professors":
            _check_required(errors, op, loc, ["professor_a", "professor_b"])
            _check_ids(errors, op, loc, "professor_a", professor_ids)
            _check_ids(errors, op, loc, "professor_b", professor_ids)
            if op.get("professor_a") == op.get("professor_b"):
                errors.append({"location": loc, "error": "professor_a and professor_b must differ"})

        elif op_type in ("unpin_project", "unpin_professor_role"):
            _check_required(errors, op, loc, ["project_id"])
            _check_ids(errors, op, loc, "project_id", project_ids)
            _check_in_assignments(errors, op, loc, "project_id", assignment_project_ids)
            if op_type == "unpin_professor_role":
                _check_role(errors, op, loc)

        else:
            errors.append({"location": loc, "error": f"Unknown override type: {op_type!r}"})

    return errors


# ──────────────────────────────────────────────────────────────────────────────
# Apply overrides to the assignment list (produces the *intended* state)
# ──────────────────────────────────────────────────────────────────────────────

def _apply_overrides_to_assignments(
    data: dict[str, Any],
    assignments: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Returns (mutated_assignments, change_log).
    The mutated list reflects what the caller *wants*; the solver still has
    to verify feasibility.
    """
    by_project: dict[int, dict[str, Any]] = {a["project_id"]: a for a in assignments}
    sessions_by_id = {s["id"]: s for s in data.get("sessions", [])}
    change_log: list[dict[str, Any]] = []

    for op in overrides:
        op_type = op["type"]

        if op_type == "move_professor":
            project_id = int(op["project_id"])
            professor_id = int(op["professor_id"])
            role = str(op["role"]).upper()
            target_session_id = op.get("session_id")

            assignment = by_project[project_id]
            old_professor = assignment["roles"].get(role.lower())
            old_session = assignment["session_id"]

            # Update role assignment.
            assignment["roles"][role.lower()] = professor_id

            # Optionally move session too.
            if target_session_id is not None:
                target_session_id = int(target_session_id)
                session = sessions_by_id[target_session_id]
                assignment["session_id"] = target_session_id
                assignment["date"] = session.get("date")
                assignment["period"] = session.get("period")

            change_log.append({
                "type": op_type,
                "project_id": project_id,
                "role": role,
                "old_professor_id": old_professor,
                "new_professor_id": professor_id,
                "old_session_id": old_session,
                "new_session_id": assignment["session_id"],
            })

        elif op_type == "move_project":
            project_id = int(op["project_id"])
            session_id = int(op["session_id"])
            session = sessions_by_id[session_id]
            assignment = by_project[project_id]
            old_session = assignment["session_id"]

            assignment["session_id"] = session_id
            assignment["date"] = session.get("date")
            assignment["period"] = session.get("period")

            change_log.append({
                "type": op_type,
                "project_id": project_id,
                "old_session_id": old_session,
                "new_session_id": session_id,
            })

        elif op_type == "swap_professors":
            prof_a = int(op["professor_a"])
            prof_b = int(op["professor_b"])
            project_a_id = op.get("project_a")
            project_b_id = op.get("project_b")
            role_a = str(op.get("role_a", "")).upper() or None
            role_b = str(op.get("role_b", "")).upper() or None

            swaps = _resolve_swap(by_project, prof_a, prof_b, project_a_id, project_b_id, role_a, role_b)
            for swap in swaps:
                asgn = by_project[swap["project_id"]]
                asgn["roles"][swap["role"].lower()] = swap["new_professor_id"]
            change_log.append({"type": op_type, "swaps": swaps})

        elif op_type == "unpin_project":
            # No change to assignments — the free_pairs logic will exclude
            # this project's session pin from the lock rules.
            change_log.append({"type": op_type, "project_id": int(op["project_id"])})

        elif op_type == "unpin_professor_role":
            change_log.append({
                "type": op_type,
                "project_id": int(op["project_id"]),
                "role": str(op["role"]).upper(),
            })

    return list(by_project.values()), change_log


def _resolve_swap(
    by_project: dict[int, dict[str, Any]],
    prof_a: int,
    prof_b: int,
    project_a_id: Any,
    project_b_id: Any,
    role_a: str | None,
    role_b: str | None,
) -> list[dict[str, Any]]:
    """
    Finds where prof_a and prof_b currently sit (across all assignments if
    project/role are not specified) and swaps them.
    """
    # Build a lookup: professor_id -> [(project_id, role)]
    loc: dict[int, list[tuple[int, str]]] = {prof_a: [], prof_b: []}
    for asgn in by_project.values():
        for role, pid in asgn["roles"].items():
            if pid == prof_a:
                loc[prof_a].append((asgn["project_id"], role.upper()))
            elif pid == prof_b:
                loc[prof_b].append((asgn["project_id"], role.upper()))

    # If caller specified projects/roles, narrow the swap.
    seats_a = loc[prof_a]
    seats_b = loc[prof_b]

    if project_a_id:
        seats_a = [(p, r) for p, r in seats_a if p == int(project_a_id)]
    if project_b_id:
        seats_b = [(p, r) for p, r in seats_b if p == int(project_b_id)]
    if role_a:
        seats_a = [(p, r) for p, r in seats_a if r == role_a]
    if role_b:
        seats_b = [(p, r) for p, r in seats_b if r == role_b]

    swaps: list[dict[str, Any]] = []
    for (pa, ra), (pb, rb) in zip(seats_a, seats_b):
        swaps.append({"project_id": pa, "role": ra, "new_professor_id": prof_b})
        swaps.append({"project_id": pb, "role": rb, "new_professor_id": prof_a})

    return swaps


# ──────────────────────────────────────────────────────────────────────────────
# Determine which (project_id, role) pairs are "free" (not locked)
# ──────────────────────────────────────────────────────────────────────────────

def _collect_free_pairs(
    overrides: list[dict[str, Any]],
    original_assignments: list[dict[str, Any]],
    updated_assignments: list[dict[str, Any]],
) -> set[tuple[int, str]]:
    """
    A (project, role) pair is free if it was *directly targeted* by a
    move/swap/unpin override, meaning the solver should figure out the
    best feasible assignment there rather than having it locked.

    For move_professor: the *old* holder of that role on nearby projects
    also becomes free (the professor just lost a seat, the solver must
    place them somewhere else).
    For unpin_project: all roles on that project are free.
    For unpin_professor_role: just the specific role.
    For swap: both seats are free.
    For move_project: session pin on that project is free (handled
    separately via project-session locks).
    """
    free: set[tuple[int, str]] = set()
    orig_by_project = {a["project_id"]: a for a in original_assignments}

    for op in overrides:
        op_type = op["type"]

        if op_type == "move_professor":
            project_id = int(op["project_id"])
            role = str(op["role"]).upper()
            professor_id = op.get("professor_id")
            try:
                professor_id = int(professor_id) if professor_id is not None else None
            except (TypeError, ValueError):
                professor_id = None

            # The target slot should be considered for re-solving.
            free.add((project_id, role))

            # The professor being moved vacates any previous seats they held;
            # mark those seats free so the solver can place them elsewhere.
            if professor_id is not None:
                for asgn in original_assignments:
                    for r, pid in asgn.get("roles", {}).items():
                        if pid == professor_id:
                            free.add((asgn["project_id"], r.upper()))

        elif op_type == "move_project":
            project_id = int(op["project_id"])
            # All roles on a moved project are re-solved.
            for role in ROLES:
                free.add((project_id, role))

        elif op_type == "swap_professors":
            prof_a = int(op["professor_a"])
            prof_b = int(op["professor_b"])
            for asgn in original_assignments:
                for role, pid in asgn["roles"].items():
                    if pid in (prof_a, prof_b):
                        free.add((asgn["project_id"], role.upper()))

        elif op_type == "unpin_project":
            project_id = int(op["project_id"])
            for role in ROLES:
                free.add((project_id, role))

        elif op_type == "unpin_professor_role":
            project_id = int(op["project_id"])
            role = str(op["role"]).upper()
            free.add((project_id, role))

    return free


# ──────────────────────────────────────────────────────────────────────────────
# Build lock (hard-pin) rules for every assignment NOT in free_pairs
# ──────────────────────────────────────────────────────────────────────────────

def _build_lock_rules(
    assignments: list[dict[str, Any]],
    free_pairs: set[tuple[int, str]],
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []

    # Track which projects have had their session pinned already.
    session_pinned: set[int] = set()

    for asgn in assignments:
        project_id = int(asgn["project_id"])
        session_id = int(asgn["session_id"])

        # Pin project-session unless the whole project is free (move_project /
        # unpin_project touches all roles, which implies the session is also free).
        all_roles_free = all((project_id, r) in free_pairs for r in ROLES)
        if not all_roles_free and project_id not in session_pinned:
            rules.append({
                "name": f"_lock_session_pr{project_id}",
                "rule": "require_project_session",
                "type": "hard",
                "weight": 1,
                "payload": {"project_id": project_id, "session_id": session_id},
                "enabled": True,
            })
            session_pinned.add(project_id)

        # Pin each role that is not free.
        for role in ROLES:
            if (project_id, role) in free_pairs:
                continue
            professor_id = asgn["roles"].get(role.lower())
            if professor_id is None:
                continue
            rules.append({
                "name": f"_lock_{role.lower()}_pr{project_id}",
                "rule": "require_professor_role",
                "type": "hard",
                "weight": 1,
                "payload": {
                    "professor_id": int(professor_id),
                    "project_id": project_id,
                    "role": role,
                    "session_id": session_id,
                },
                "enabled": True,
            })

    return rules


# ──────────────────────────────────────────────────────────────────────────────
# Inject generated rules into the data payload
# ──────────────────────────────────────────────────────────────────────────────

def _inject_rules(
    data: dict[str, Any],
    lock_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    existing = data.get("constraint_rules", [])
    # Remove any previously injected lock rules (names start with "_lock_").
    cleaned = [r for r in existing if not str(r.get("name", "")).startswith("_lock_")]
    data["constraint_rules"] = cleaned + lock_rules
    return data


# ──────────────────────────────────────────────────────────────────────────────
# Small validation helpers
# ──────────────────────────────────────────────────────────────────────────────

def _check_required(errors: list, op: dict, loc: str, keys: list[str]) -> None:
    for k in keys:
        if k not in op or op[k] is None:
            errors.append({"location": loc, "error": f"Missing required field: {k!r}"})


def _check_ids(errors: list, op: dict, loc: str, key: str, valid_ids: set) -> None:
    val = op.get(key)
    if val is not None:
        try:
            if int(val) not in valid_ids:
                errors.append({"location": loc, "error": f"{key}={val!r} not found"})
        except (TypeError, ValueError):
            errors.append({"location": loc, "error": f"{key}={val!r} is not a valid integer"})


def _check_in_assignments(
    errors: list, op: dict, loc: str, key: str, assignment_project_ids: set
) -> None:
    val = op.get(key)
    if val is not None:
        try:
            if int(val) not in assignment_project_ids:
                errors.append({
                    "location": loc,
                    "error": f"{key}={val!r} is not present in existing assignments",
                })
        except (TypeError, ValueError):
            pass


def _check_role(errors: list, op: dict, loc: str) -> None:
    role = str(op.get("role", "")).upper()
    if role not in ROLES:
        errors.append({"location": loc, "error": f"role={op.get('role')!r} must be one of {ROLES}"})
