from __future__ import annotations

from fastapi import APIRouter, HTTPException

from contracts.api_models import TranslateRequest, TranslateResponse
from services.translator_engine import translate_prompt


router = APIRouter(tags=["translator"])


@router.post("/translate", response_model=TranslateResponse)
def translate(payload: TranslateRequest):
    try:
        result = translate_prompt(
            request_id=payload.request_id,
            prompt=payload.prompt,
            user_id=payload.user_id,
        )
        return TranslateResponse.model_validate(result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"translator_service_error: {exc}") from exc
