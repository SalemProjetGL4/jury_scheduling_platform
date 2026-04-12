from __future__ import annotations

from typing import Any

import requests

from config import settings


def solve_via_gateway(payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{settings.solver_service_url.rstrip('/')}/solve",
        json=payload,
        timeout=settings.llm_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()
