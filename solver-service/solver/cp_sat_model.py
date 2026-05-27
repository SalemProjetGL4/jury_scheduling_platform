from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model

from solver.constraints.assumptions import AssumptionRegistry
from solver.constraints.hard_constraints import apply_hard_constraints
from solver.constraints.soft_constraints import SoftTerms, build_soft_terms
from solver.objective import apply_objective
from solver.variables import VariableBundle, build_variables


@dataclass
class ModelBundle:
    model: cp_model.CpModel
    vars_: VariableBundle
    soft_terms: SoftTerms
    assumptions: AssumptionRegistry | None


def build_model(data: dict[str, Any], *, include_conflict_refiner: bool = True) -> ModelBundle:
    import time
    import logging
    _log = logging.getLogger("solver")

    model = cp_model.CpModel()
    assumptions = AssumptionRegistry(model) if include_conflict_refiner else None

    t = time.monotonic()
    vars_ = build_variables(model, data)
    _log.info("TIMING build_variables: %.2fs  vars_x=%d vars_y=%d", time.monotonic() - t, len(vars_.x), len(vars_.y))

    t = time.monotonic()
    session_load_vars = apply_hard_constraints(model, data, vars_, assumption_registry=assumptions)
    _log.info("TIMING apply_hard_constraints: %.2fs", time.monotonic() - t)

    t = time.monotonic()
    _add_greedy_hints(model, data, vars_)
    _log.info("TIMING greedy_hints: %.2fs", time.monotonic() - t)

    t = time.monotonic()
    soft_terms = build_soft_terms(model, data, vars_, session_load_vars)
    _log.info("TIMING build_soft_terms: %.2fs", time.monotonic() - t)

    t = time.monotonic()
    apply_objective(model, data, soft_terms)
    _log.info("TIMING apply_objective: %.2fs", time.monotonic() - t)

    return ModelBundle(model=model, vars_=vars_, soft_terms=soft_terms, assumptions=assumptions)


def _add_greedy_hints(
    model: cp_model.CpModel,
    data: dict[str, Any],
    vars_: VariableBundle,
) -> None:
    """Compute a greedy feasible assignment and add it as CP-SAT hints.

    A near-feasible starting point lets CP-SAT find the first solution in seconds
    rather than spending its full time budget in blind search.
    """
    professors = data.get("professors", [])
    projects = data.get("projects", [])
    sessions = data.get("sessions", [])
    if not (professors and projects and sessions):
        return

    # Per-professor tracking structures
    prof_session_busy: dict[int, set[int]] = defaultdict(set)   # sessions where prof has an assignment
    prof_day_period: dict[tuple[int, str], str] = {}            # (prof, date) → "morning"|"afternoon"
    prof_load: dict[int, int] = {p["id"]: 0 for p in professors}
    prof_max: dict[int, int] = {p["id"]: p.get("max_juries", 15) for p in professors}

    session_proj_count: dict[int, int] = defaultdict(int)

    for project in projects:
        proj_id = project["id"]
        sup_id = project["supervisor_id"]

        # Pick session: fewest other projects, supervisor must be free.
        # Fall back to any session if supervisor is fully booked.
        def _session_score(s: dict[str, Any]) -> tuple:
            sid = s["id"]
            sup_busy = sid in prof_session_busy[sup_id]
            sup_day_conflict = prof_day_period.get((sup_id, str(s.get("date", ""))), s.get("period", "")) != s.get("period", "")
            return (int(sup_busy), int(sup_day_conflict), session_proj_count[sid])

        best = min(sessions, key=_session_score)
        sess_id = best["id"]
        sess_date = str(best.get("date", ""))
        sess_period = str(best.get("period", "morning"))

        # Hint y: project → session
        model.AddHint(vars_.y[(proj_id, sess_id)], 1)

        # Hint SUPERVISOR x (forced by constraint anyway, but hint speeds up propagation)
        sv_var = vars_.x.get((sup_id, proj_id, "SUPERVISOR", sess_id))
        if sv_var is not None:
            model.AddHint(sv_var, 1)
        prof_session_busy[sup_id].add(sess_id)
        prof_day_period.setdefault((sup_id, sess_date), sess_period)
        session_proj_count[sess_id] += 1

        # Pick PRESIDENT — not supervisor, not busy this session, respects half-day
        def _prof_eligible(p: dict[str, Any], exclude_ids: set[int]) -> bool:
            pid = p["id"]
            if pid in exclude_ids:
                return False
            if sess_id in prof_session_busy[pid]:
                return False
            existing_period = prof_day_period.get((pid, sess_date))
            if existing_period is not None and existing_period != sess_period:
                return False
            return prof_load[pid] < prof_max[pid]

        candidates = [p for p in professors if _prof_eligible(p, {sup_id})]
        pres_id: int | None = None
        if candidates:
            president = min(candidates, key=lambda p: prof_load[p["id"]])
            pres_id = president["id"]
            px = vars_.x.get((pres_id, proj_id, "PRESIDENT", sess_id))
            if px is not None:
                model.AddHint(px, 1)
            prof_session_busy[pres_id].add(sess_id)
            prof_day_period.setdefault((pres_id, sess_date), sess_period)
            prof_load[pres_id] += 1

        # Pick EXAMINER — not supervisor, not president, not busy
        exclude = {sup_id} | ({pres_id} if pres_id else set())
        candidates2 = [p for p in professors if _prof_eligible(p, exclude)]
        if candidates2:
            examiner = min(candidates2, key=lambda p: prof_load[p["id"]])
            exam_id = examiner["id"]
            ex = vars_.x.get((exam_id, proj_id, "EXAMINER", sess_id))
            if ex is not None:
                model.AddHint(ex, 1)
            prof_session_busy[exam_id].add(sess_id)
            prof_day_period.setdefault((exam_id, sess_date), sess_period)
            prof_load[exam_id] += 1
