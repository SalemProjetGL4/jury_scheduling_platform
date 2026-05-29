from __future__ import annotations

import json
import os
import sys
import threading
from uuid import uuid4
from pathlib import Path
from typing import Any

from fastapi import FastAPI, BackgroundTasks, HTTPException
import redis


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from solver.solver_runner import solve

try:
    from log_setup import logger
except Exception:
    import logging
    logger = logging.getLogger("solver")


app = FastAPI(title="Juriq Solver Service", version="0.1.0")

_redis_url = os.getenv("REDIS_URL", "").strip()
_redis_ttl_seconds = int(os.getenv("REDIS_TTL_SECONDS", "0") or "0")
_redis_client = redis.Redis.from_url(_redis_url, decode_responses=True) if _redis_url else None

_STATUS_KEY = "solver:status:{}"
_RESULT_KEY = "solver:result:{}"


def _write_to_redis(key: str, data: dict[str, Any]) -> None:
    if _redis_client is None:
        return
    payload = json.dumps(data, ensure_ascii=True)
    if _redis_ttl_seconds > 0:
        _redis_client.setex(key, _redis_ttl_seconds, payload)
    else:
        _redis_client.set(key, payload)


def _do_solve(request_id: str, payload: dict[str, Any]) -> None:
    projects = payload.get("projects") or []
    professors = payload.get("professors") or []
    sessions = payload.get("sessions") or []
    logger.info(
        "SOLVE START — request_id=%s projects=%d professors=%d slots=%d",
        request_id, len(projects), len(professors), len(sessions),
    )
    logger.debug(
        "SOLVE INPUT — hard_rules=%s soft_rules=%s unavailabilities=%s conflicts=%s",
        len((payload.get("constraints") or {}).get("hard") or []),
        len((payload.get("constraints") or {}).get("soft") or []),
        len(payload.get("unavailabilities") or []),
        len(payload.get("conflicts") or []),
    )
    try:
        import json as _json
        with open("/app/logs/solver_payload_debug2.json", "w", encoding="utf-8") as _f:
            _json.dump(payload, _f, indent=2, default=str)
        logger.info("DEBUG payload written to /app/logs/solver_payload_debug2.json")
    except Exception as _e:
        logger.warning("DEBUG payload write failed: %s", _e)

    try:
        result = solve(payload)
        result["request_id"] = request_id
    except Exception as exc:
        logger.exception("SOLVE EXCEPTION — request_id=%s: %s", request_id, exc)
        result = {
            "request_id": request_id,
            "status": "INFEASIBLE",
            "failed_constraints": [{"constraint": "solver_exception", "reason": str(exc)}],
        }

    status = result.get("status", "UNKNOWN")
    failed = result.get("failed_constraints") or []
    solutions = result.get("solutions") or []
    logger.info(
        "SOLVE RESULT — request_id=%s status=%s solutions=%d failed_constraints=%d",
        request_id, status, len(solutions), len(failed),
    )
    for fc in failed:
        logger.warning("FAILED CONSTRAINT — %s: %s", fc.get("constraint"), fc.get("reason"))
        if fc.get("details"):
            logger.warning("  details: %s", json.dumps(fc["details"], ensure_ascii=True))

    try:
        _write_to_redis(_RESULT_KEY.format(request_id), result)
        _write_to_redis(_STATUS_KEY.format(request_id), {"status": "done"})
    except Exception as exc:
        logger.error("REDIS WRITE FAILED — %s", exc)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/solve/async", tags=["solver"])
def solve_async_endpoint(payload: dict[str, Any], background_tasks: BackgroundTasks) -> dict[str, str]:
    """Start a solve in the background, return immediately with request_id."""
    request_id = str(payload.get("request_id") or "").strip() or str(uuid4())
    _write_to_redis(_STATUS_KEY.format(request_id), {"status": "running"})
    background_tasks.add_task(_do_solve, request_id, payload)
    return {"request_id": request_id, "status": "running"}


@app.get("/solve/{request_id}/result", tags=["solver"])
def get_solve_result(request_id: str) -> dict[str, Any]:
    """Poll for a solve result. Returns {'status': 'running'} while in progress."""
    if _redis_client is None:
        raise HTTPException(status_code=503, detail="Redis not configured")

    raw = _redis_client.get(_RESULT_KEY.format(request_id))
    if raw is None:
        return {"status": "running", "request_id": request_id}
    return json.loads(raw)


@app.post("/solve", tags=["solver"])
def solve_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    """Synchronous solve (kept for compatibility). Prefer /solve/async for large problems."""
    request_id = str(payload.get("request_id") or "").strip() or str(uuid4())
    _do_solve(request_id, payload)

    raw = _redis_client.get(_RESULT_KEY.format(request_id)) if _redis_client else None
    if raw:
        return json.loads(raw)

    result = solve(payload)
    result["request_id"] = request_id
    return result
