from __future__ import annotations

import json
from typing import Any

from adapters.llm_provider_adapter import get_provider
from adapters.prompt_registry import prompt_registry
from contracts.orchestrator_output import extract_json_object
from contracts.translator_output import validate_solver_payload


def extract_constraints_via_llm(prompt: str, snapshot: dict[str, Any]) -> dict[str, Any] | None:
    system_prompt, _ = prompt_registry.get_with_hash("translator.system.txt")
    schema_prompt, _ = prompt_registry.get_with_hash("translator.schema.txt")

    provider = get_provider()
    full_system_prompt = f"{system_prompt}\n\nReturn strict JSON only.\n{schema_prompt}"
    user_message = json.dumps({"prompt": prompt, "db_snapshot": snapshot}, ensure_ascii=True)

    print("[translator-service] LLM SYSTEM PROMPT START")
    print(full_system_prompt)
    print("[translator-service] LLM SYSTEM PROMPT END")
    print("[translator-service] LLM USER MESSAGE START")
    print(user_message)
    print("[translator-service] LLM USER MESSAGE END")

    raw_output = provider.complete(system_prompt=full_system_prompt, user_message=user_message)

    print("[translator-service] LLM RAW OUTPUT START")
    print(raw_output)
    print("[translator-service] LLM RAW OUTPUT END")

    candidate = json.loads(extract_json_object(raw_output))
    print("[translator-service] LLM PARSED JSON START")
    print(json.dumps(candidate, ensure_ascii=True, indent=2))
    print("[translator-service] LLM PARSED JSON END")

    validated_payload, _ = validate_solver_payload(candidate)
    if validated_payload is None:
        return None
    return validated_payload.model_dump(mode="json")
