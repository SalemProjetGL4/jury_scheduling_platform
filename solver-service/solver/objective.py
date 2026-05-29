from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from solver.constraints.soft_constraints import SoftTerms


def apply_objective(model: cp_model.CpModel, data: dict[str, Any], terms: SoftTerms) -> None:
    # All penalties were consolidated into `terms.custom_penalty` (already
    # scaled by their respective weights). Minimize that combined expression.
    model.Minimize(terms.custom_penalty)
