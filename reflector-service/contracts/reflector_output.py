from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


class CompromisedSolutionReview(BaseModel):
    solution_index: int
    rating: int
    violations_count: int
    total_penalty: float
    violated_soft_constraints: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str


class RelaxationSuggestion(BaseModel):
    constraint: str
    action: str
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)
    patch: dict[str, Any] | None = None


class ReflectorOutput(BaseModel):
    status: Literal["INFEASIBLE", "COMPROMISED", "OPTIMAL", "FEASIBLE"]
    summary: str
    ranking_basis: str | None = None
    recommended_solution_index: int | None = None
    compromised_solutions: list[CompromisedSolutionReview] = Field(default_factory=list)
    relaxation_suggestions: list[RelaxationSuggestion] = Field(default_factory=list)
    timing_info: dict[str, float] | None = None
    token_usage: dict[str, int] | None = None


def extract_json_object(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")

    return match.group(0)


def parse_reflector_output(raw_text: str) -> ReflectorOutput:
    payload = json.loads(extract_json_object(raw_text))
    return ReflectorOutput.model_validate(payload)


def safe_parse_reflector_output(raw_text: str) -> tuple[ReflectorOutput | None, str | None]:
    try:
        return parse_reflector_output(raw_text), None
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)
