from __future__ import annotations

from typing import Any

import requests

from config import settings


def update_via_gateway(
    *,
    request_id: str,
    old_solver_result: dict[str, Any],
    translator_payload: dict[str, Any],
    db_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    response = requests.post(
        f"{settings.updater_service_url.rstrip('/')}/update",
        json={
            "request_id": request_id,
            "old_solver_result": old_solver_result,
            "translator_payload": translator_payload,
            "db_snapshot": db_snapshot,
        },
        timeout=settings.gateway_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()
