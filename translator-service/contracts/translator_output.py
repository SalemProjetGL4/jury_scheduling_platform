from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


SUPPORTED_HARD_RULES = {
    "forbid_professor_session",
    "forbid_professor_project",
    "require_professor_role",
    "require_project_session",
}

SUPPORTED_SOFT_RULES = {
    "prefer_project_session",
    "prefer_professor_role",
    "avoid_professor_session",
    "penalize_professor_project",
    "prefer_morning",
}


class ProfessorPayload(BaseModel):
    id: int
    domain_id: int
    domain_ids: list[int] = Field(default_factory=list)
    specialities: list[str] = Field(default_factory=list)
    max_juries: int


class ProjectPayload(BaseModel):
    id: int
    domain_id: int = 0
    domain_ids: list[int] = Field(default_factory=list)
    domain_keywords: list[str] = Field(default_factory=list)
    supervisor_id: int


class SessionPayload(BaseModel):
    id: int
    date: date | str
    period: Literal["morning", "afternoon"]
    slot_number: int | None = None
    start_time: str | None = None
    end_time: str | None = None


class UnavailabilityPayload(BaseModel):
    professor_id: int
    date: date | str
    period: str


class ConflictPayload(BaseModel):
    professor_a: int
    professor_b: int


class ConstraintsPayload(BaseModel):
    hard_max_juries: int = 2
    weights: dict[str, int] = Field(default_factory=lambda: {
        "workload": 10,
        "expertise": 15,
        "clustering": 3,
        "overload": 20,
        "custom": 1,
    })
    hard: list[dict[str, Any]] = Field(default_factory=list)
    soft: list[dict[str, Any]] = Field(default_factory=list)


class ConstraintRulePayload(BaseModel):
    name: str
    rule: str
    type: Literal["hard", "soft"]
    weight: float
    payload: dict[str, Any]
    enabled: bool = True


class SolverPayload(BaseModel):
    professors: list[ProfessorPayload]
    projects: list[ProjectPayload]
    sessions: list[SessionPayload]
    constraints: ConstraintsPayload
    unavailabilities: list[UnavailabilityPayload] = Field(default_factory=list)
    conflicts: list[ConflictPayload] = Field(default_factory=list)
    constraint_rules: list[ConstraintRulePayload] = Field(default_factory=list)


class RecognizedConstraint(BaseModel):
    name: str
    source: Literal["prompt", "database", "llm"]


class UnrecognizedConstraint(BaseModel):
    raw_text: str
    inferred_type: str
    reason_unrecognized: str


class TranslatorAnalysis(BaseModel):
    recognized_constraints: list[RecognizedConstraint] = Field(default_factory=list)
    unrecognized_constraints: list[UnrecognizedConstraint] = Field(default_factory=list)
    weight_overrides: dict[str, int] = Field(default_factory=dict)


def validate_solver_payload(payload: dict[str, Any]) -> tuple[SolverPayload | None, str | None]:
    try:
        return SolverPayload.model_validate(payload), None
    except ValidationError as exc:
        return None, str(exc)
