from __future__ import annotations

import time
from typing import Any

import requests

from config import settings

try:
    from log_setup import logger
except Exception:
    import logging
    logger = logging.getLogger("orchestrator")

_POLL_INTERVAL = 5  # seconds between polls


def solve_via_gateway(payload: dict[str, Any]) -> dict[str, Any]:
    """Submit a solve job and poll until done."""
    base = settings.solver_service_url.rstrip("/")

    # Submit async job — returns immediately with request_id
    start_resp = requests.post(
        f"{base}/solve/async",
        json=payload,
        timeout=15,
    )
    start_resp.raise_for_status()
    job = start_resp.json()
    request_id = job.get("request_id", payload.get("request_id", "?"))
    logger.info("SOLVER JOB submitted — request_id=%s", request_id)

    # Poll for result
    deadline = time.monotonic() + settings.solver_timeout_seconds
    while time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL)
        poll_resp = requests.get(
            f"{base}/solve/{request_id}/result",
            timeout=10,
        )
        poll_resp.raise_for_status()
        result = poll_resp.json()
        if result.get("status") != "running":
            logger.info(
                "SOLVER JOB done — request_id=%s status=%s elapsed=%.1fs",
                request_id, result.get("status"), settings.solver_timeout_seconds - (deadline - time.monotonic()),
            )
            return result
        logger.debug("SOLVER POLL — request_id=%s still running...", request_id)

    raise TimeoutError(
        f"Solver did not complete within {settings.solver_timeout_seconds}s for request_id={request_id}"
    )
