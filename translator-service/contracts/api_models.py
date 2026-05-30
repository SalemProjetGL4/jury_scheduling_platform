from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TranslateRequest(BaseModel):
    request_id: str
    prompt: str
    user_id: str | None = None


class TranslateResponse(BaseModel):
    request_id: str
    translator_payload: dict[str, Any]
    recognized_constraints: list[dict[str, str]]
    unrecognized_constraints: list[dict[str, str]]
    db_snapshot: dict[str, Any]
    timing_info: dict[str, float] | None = None
    token_usage: dict[str, int] | None = None
