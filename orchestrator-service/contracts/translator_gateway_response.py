from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TranslatorGatewayResponse(BaseModel):
    request_id: str
    translator_payload: dict[str, Any]
    recognized_constraints: list[dict[str, str]]
    unrecognized_constraints: list[dict[str, str]]
    db_snapshot: dict[str, Any]
