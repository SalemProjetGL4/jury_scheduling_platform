from __future__ import annotations

from typing import Any

from ortools.sat.python import cp_model

from solver.constraints.rule_utils import normalize_weight
from solver.constraints.soft_constraints import SoftTerms


def apply_objective(model: cp_model.CpModel, data: dict[str, Any], terms: SoftTerms) -> None:
    weights = data.get("constraints", {}).get("weights", {})

    workload_w = normalize_weight(weights.get("workload", 10), default=10)
    expertise_w = normalize_weight(weights.get("expertise", 5), default=5)
    clustering_w = normalize_weight(weights.get("clustering", 3), default=3)
    overload_w = normalize_weight(weights.get("overload", 20), default=20)

    try:
        custom_w = max(0, int(float(weights.get("custom", 1))))
    except (TypeError, ValueError):
        custom_w = 1

    model.Minimize(
        workload_w * terms.workload_balance
        + expertise_w * terms.expertise_penalty
        + clustering_w * terms.clustering_penalty
        + overload_w * terms.overload_penalty
        + custom_w * terms.custom_penalty
    )
