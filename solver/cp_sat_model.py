from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model

from solver.constraints.hard_constraints import apply_hard_constraints
from solver.constraints.soft_constraints import SoftTerms, build_soft_terms
from solver.objective import apply_objective
from solver.variables import VariableBundle, build_variables


@dataclass
class ModelBundle:
    model: cp_model.CpModel
    vars_: VariableBundle
    soft_terms: SoftTerms


def build_model(data: dict[str, Any]) -> ModelBundle:
    model = cp_model.CpModel()
    vars_ = build_variables(model, data)
    apply_hard_constraints(model, data, vars_)
    soft_terms = build_soft_terms(model, data, vars_)
    apply_objective(model, data, soft_terms)
    return ModelBundle(model=model, vars_=vars_, soft_terms=soft_terms)
