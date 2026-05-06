from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ScheduleRequest(BaseModel):
    prompt: str
    user_id: str | None = None
    old_solver_result: dict[str, Any] | None = None


class ScheduleAcceptedResponse(BaseModel):
    request_id: str
    status: str


class StatusResponse(BaseModel):
    request_id: str
    final_status: str
    current_node: str | None
    node_history: list[dict[str, Any]]
    errors: list[str]
    unrecognized_constraints: list[dict[str, Any]]
