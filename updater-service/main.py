from __future__ import annotations

import json
import os
import sys
from uuid import uuid4
from pathlib import Path
from typing import Any

from fastapi import FastAPI
import redis
import requests


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Ensure both the repository root and this service dir are on sys.path so
# imports like `solver.solver_runner` and the local `updater` module work.
SERVICE_DIR = Path(__file__).resolve().parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.append(str(SERVICE_DIR))

from solver.solver_runner import solve
# The updater implementation lives inside this service (updater.py). Import
# it as a local module rather than expecting it under the `solver` package.
from updater import update


app = FastAPI(title="Juriq Solver Service", version="0.1.0")

_redis_url = os.getenv("REDIS_URL", "").strip()
_redis_ttl_seconds = int(os.getenv("REDIS_TTL_SECONDS", "0") or "0")
_redis_client = redis.Redis.from_url(_redis_url, decode_responses=True) if _redis_url else None
_reflector_service_url = os.getenv("REFLECTOR_SERVICE_URL", "http://reflector-service:8013").strip()
_reflector_timeout_seconds = float(os.getenv("REFLECTOR_TIMEOUT_SECONDS", "30") or "30")


def _write_result_to_redis(request_id: str, result: dict[str, Any]) -> None:
    if _redis_client is None:
        return

    key = f"solver:result:{request_id}"
    payload = json.dumps(result, ensure_ascii=True)

    if _redis_ttl_seconds > 0:
        _redis_client.setex(key, _redis_ttl_seconds, payload)
    else:
        _redis_client.set(key, payload)


def _trigger_reflector(
    request_id: str,
    solver_payload: dict[str, Any],
    solver_result: dict[str, Any],
    db_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not _reflector_service_url:
        return None
    response = requests.post(
        f"{_reflector_service_url.rstrip('/')}/reflect",
        json={
            "request_id": request_id,
            "solver_result": solver_result,
            "solver_payload": solver_payload,
            "db_snapshot": db_snapshot,
        },
        timeout=_reflector_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _derive_overrides_from_unavailabilities(
    solver_data: dict[str, Any],
    assignments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Auto-generate unpin_project overrides for every assignment whose locked
    session conflicts with a professor unavailability in solver_data.

    Without this, empty overrides cause all assignments to be hard-locked, and
    the solver becomes INFEASIBLE when a new unavailability blocks a pinned slot.
    """
    unavailabilities = solver_data.get("unavailabilities") or []
    sessions = solver_data.get("sessions") or []
    if not unavailabilities or not assignments:
        return []

    session_map = {int(s["id"]): s for s in sessions}
    blocked: set[tuple[int, str, str]] = {
        (int(u["professor_id"]), str(u["date"]), str(u["period"]))
        for u in unavailabilities
    }

    free_projects: set[int] = set()
    for asgn in assignments:
        session = session_map.get(int(asgn["session_id"]))
        if not session:
            continue
        date = str(session["date"])
        period = str(session["period"])
        for prof_id in asgn.get("roles", {}).values():
            if prof_id is not None and (int(prof_id), date, period) in blocked:
                free_projects.add(int(asgn["project_id"]))
                break

    return [{"type": "unpin_project", "project_id": pid} for pid in free_projects]


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


@app.post("/update", tags=["solver"])
def update_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Update an existing solution by applying override operations, then
    re-solving with the rest of the schedule locked in place.

    Expected body
    -------------
    {
      // Everything you'd normally send to /solve:
      "professors": [...],
      "projects": [...],
      "sessions": [...],
      "constraints": {...},
      "unavailabilities": [...],
      "conflicts": [...],

      // The previous solver result's ``assignments`` list:
      "existing_assignments": [...],

      // One or more override operations:
      "overrides": [
        // Move professor 5 to be PRESIDENT on project 101
        { "type": "move_professor", "professor_id": 5, "project_id": 101, "role": "PRESIDENT" },

        // Move professor 5 to PRESIDENT on project 101 AND into session 3002
        { "type": "move_professor", "professor_id": 5, "project_id": 101, "role": "PRESIDENT", "session_id": 3002 },

        // Reschedule project 102 to session 3004 (re-solves all roles)
        { "type": "move_project", "project_id": 102, "session_id": 3004 },

        // Swap professor 3 and professor 7 wherever they currently sit
        { "type": "swap_professors", "professor_a": 3, "professor_b": 7 },

        // Swap only on a specific project / role
        { "type": "swap_professors", "professor_a": 3, "professor_b": 7,
          "project_a": 101, "role_a": "PRESIDENT", "project_b": 103, "role_b": "PRESIDENT" },

        // Free up project 100 entirely for re-scheduling
        { "type": "unpin_project", "project_id": 100 },

        // Free up only professor assignment for one role
        { "type": "unpin_professor_role", "project_id": 100, "role": "EXAMINER" }
      ],

      // Optional
      "request_id": "...",
      "solver_options": { "max_solutions": 1, "include_soft_diagnostics": true }
    }
    """
    print("[solver-service] UPDATE INPUT START")
    print(__import__("json").dumps(payload, ensure_ascii=True, indent=2))
    print("[solver-service] UPDATE INPUT END")

    request_id = str(payload.get("request_id") or "").strip() or str(uuid4())

    # Allow callers to point to a previous solver result stored in Redis
    # using one of these keys: `source_request_id`, `existing_request_id`,
    # or `session_id` (some clients call it session_id).
    source_request_id = payload.get("source_request_id") or payload.get(
        "existing_request_id"
    ) or payload.get("session_id")

    # The orchestrator sends a structured envelope: extract the actual solver
    # payload (translator_payload) and the previous result separately.
    old_solver_result = payload.pop("old_solver_result", None) or {}
    translator_payload = payload.pop("translator_payload", None)
    payload.pop("db_snapshot", None)

    # Use translator_payload as the solver data when available (orchestrator path).
    # Fall back to the raw payload for direct /update calls (legacy / test path).
    original_data = translator_payload if translator_payload else payload

    existing_assignments = payload.pop("existing_assignments", None)
    overrides = payload.pop("overrides", [])

    # Prefer assignments carried in the old_solver_result envelope (orchestrator
    # path), then fall back to Redis, then to an empty list.
    if not existing_assignments:
        existing_assignments = old_solver_result.get("assignments") or []

    # If still empty, try loading the previous solver result from Redis.
    if not existing_assignments and _redis_client and source_request_id:
        try:
            key = f"solver:result:{source_request_id}"
            raw = _redis_client.get(key)
            if raw:
                prev = json.loads(raw)
                existing_assignments = prev.get("assignments", []) or []
                print(f"[solver-service] Loaded existing_assignments from Redis key={key}")
        except Exception as exc:
            print(f"[solver-service] REDIS READ FAILED: {exc}")

    # When no explicit overrides were provided, derive them automatically from
    # unavailabilities in the new payload so that affected pinned assignments
    # are freed for re-solving instead of causing INFEASIBLE.
    if not overrides:
        overrides = _derive_overrides_from_unavailabilities(original_data, existing_assignments)
        if overrides:
            print(f"[solver-service] Auto-derived {len(overrides)} overrides from unavailabilities")

    result = update(original_data, existing_assignments, overrides)
    result["request_id"] = request_id

    try:
        reflector_result = _trigger_reflector(
            request_id,
            original_data,
            result,
            db_snapshot=payload.get("db_snapshot"),
        )
        if reflector_result is not None:
            result["reflector_result"] = reflector_result
    except Exception as exc:
        print(f"[solver-service] REFLECTOR CALL FAILED: {exc}")
        result["reflector_error"] = str(exc)

    try:
        _write_result_to_redis(request_id, result)
    except Exception as exc:
        print(f"[solver-service] REDIS WRITE FAILED: {exc}")

    print("[solver-service] UPDATE RESULT STATUS")
    print(str(result.get("status", "UNKNOWN")))

    return result
