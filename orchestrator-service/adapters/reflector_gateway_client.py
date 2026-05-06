from __future__ import annotations

from typing import Any

import requests

from config import settings


def reflect_via_gateway(
    *,
    request_id: str,
    solver_result: dict[str, Any],
    solver_payload: dict[str, Any] | None,
    db_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    response = requests.post(
        f"{settings.reflector_service_url.rstrip('/')}/reflect",
        json={
            "request_id": request_id,
            "solver_result": solver_result,
            "solver_payload": solver_payload,
            "db_snapshot": db_snapshot,
        },
        timeout=settings.llm_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()
