from __future__ import annotations

from typing import Any

import requests


def api_call(method: str, url: str, timeout: int, payload: dict[str, Any] | None = None) -> tuple[bool, Any]:
    try:
        response = requests.request(method=method, url=url, json=payload, timeout=timeout)
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
        else:
            data = {"text": response.text}
        if response.status_code >= 400:
            return False, {"status_code": response.status_code, "body": data}
        return True, data
    except requests.RequestException as exc:
        return False, {"error": str(exc)}
