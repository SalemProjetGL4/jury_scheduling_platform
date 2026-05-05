from __future__ import annotations

from fastapi import APIRouter, HTTPException

from contracts.api_models import ReflectRequest, ReflectResponse
from services.reflector_engine import reflect_solver_output


router = APIRouter(tags=["reflector"])


@router.post("/reflect", response_model=ReflectResponse)
def reflect(payload: ReflectRequest):
    try:
        result = reflect_solver_output(payload)
        return ReflectResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"reflector_service_error: {exc}") from exc
