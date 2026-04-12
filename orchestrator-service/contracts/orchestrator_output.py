from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ValidationError


class OrchestratorOutput(BaseModel):
    route: Literal["SCHEDULE", "QUERY"]
    intent_summary: str


def extract_json_object(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")

    return match.group(0)


def parse_orchestrator_output(raw_text: str) -> OrchestratorOutput:
    payload = json.loads(extract_json_object(raw_text))
    return OrchestratorOutput.model_validate(payload)


def safe_parse_orchestrator_output(raw_text: str) -> tuple[OrchestratorOutput | None, str | None]:
    try:
        return parse_orchestrator_output(raw_text), None
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)
