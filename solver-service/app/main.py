from __future__ import annotations

import json
import os
import sys
from uuid import uuid4
from pathlib import Path
from typing import Any

from fastapi import FastAPI
import redis


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from solver.solver_runner import solve


app = FastAPI(title="Juriq Solver Service", version="0.1.0")

_redis_url = os.getenv("REDIS_URL", "").strip()
_redis_ttl_seconds = int(os.getenv("REDIS_TTL_SECONDS", "0") or "0")
_redis_client = redis.Redis.from_url(_redis_url, decode_responses=True) if _redis_url else None


def _write_result_to_redis(request_id: str, result: dict[str, Any]) -> None:
    if _redis_client is None:
        return

    key = f"solver:result:{request_id}"
    payload = json.dumps(result, ensure_ascii=True)

    if _redis_ttl_seconds > 0:
        _redis_client.setex(key, _redis_ttl_seconds, payload)
    else:
        _redis_client.set(key, payload)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/solve", tags=["solver"])
def solve_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    print("[solver-service] SOLVER INPUT START")
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    print("[solver-service] SOLVER INPUT END")

    request_id = str(payload.get("request_id") or "").strip() or str(uuid4())
    result = solve(payload)
    result["request_id"] = request_id

    try:
        _write_result_to_redis(request_id, result)
    except Exception as exc:
        print(f"[solver-service] REDIS WRITE FAILED: {exc}")

    print("[solver-service] SOLVER RESULT STATUS")
    print(str(result.get("status", "UNKNOWN")))

    return result
