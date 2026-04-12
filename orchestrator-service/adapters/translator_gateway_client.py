from __future__ import annotations

from typing import Any

import requests

from config import settings


def translate_via_gateway(*, request_id: str, prompt: str, user_id: str | None) -> dict[str, Any]:
    response = requests.post(
        f"{settings.translator_service_url.rstrip('/')}/translate",
        json={
            "request_id": request_id,
            "prompt": prompt,
            "user_id": user_id,
        },
        timeout=settings.llm_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()
