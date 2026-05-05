from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from contracts.reflector_output import ReflectorOutput


class ReflectRequest(BaseModel):
    request_id: str | None = None
    solver_result: dict[str, Any]
    solver_payload: dict[str, Any] | None = None
    db_snapshot: dict[str, Any] | None = None


class ReflectResponse(ReflectorOutput):
    pass
