from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from contracts.api_models import ReflectRequest, ReflectResponse
from services.reflector_engine import reflect_solver_output


router = APIRouter(tags=["reflector"])

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


@router.post("/reflect", response_model=ReflectResponse)
async def reflect(request: Request):
    try:
        # Capture raw request body first so we can inspect the exact inbound payload.
        raw_body_bytes = await request.body()
        raw_body_text = raw_body_bytes.decode("utf-8", errors="replace")

        try:
            raw_body_json = json.loads(raw_body_text) if raw_body_text else None
        except json.JSONDecodeError:
            raw_body_json = None

        payload = ReflectRequest.model_validate(raw_body_json or {})

        # Dump full reflector input as received (raw + parsed).
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        request_id = payload.request_id or "no_id"
        safe_request_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(request_id))
        dump_file = LOGS_DIR / f"reflector_input_{safe_request_id}_{timestamp}.json"

        dump_data = {
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url.path),
            "query": dict(request.query_params),
            "headers": dict(request.headers),
            "raw_body_text": raw_body_text,
            "raw_body_json": raw_body_json,
            "parsed_payload": payload.model_dump(mode="json"),
        }

        with open(dump_file, "w", encoding="utf-8") as f:
            json.dump(dump_data, f, indent=2, default=str)
        
        print(f"✓ Reflector input dumped to: {dump_file}")

        result = reflect_solver_output(payload)
        return ReflectResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"reflector_service_error: {exc}") from exc
