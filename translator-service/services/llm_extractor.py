from __future__ import annotations

import json
import logging
from typing import Any

from adapters.llm_provider_adapter import get_provider
from adapters.prompt_registry import prompt_registry
from contracts.orchestrator_output import extract_json_object

_log = logging.getLogger("translator")


def _slim_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return only the fields the LLM needs for name-to-ID matching and delta context."""
    return {
        "professors": [
            {"id": p["id"], "name": p.get("name", "")}
            for p in snapshot.get("professors", [])
        ],
        "projects": [
            {"id": p["id"], "title": p.get("title", "")}
            for p in snapshot.get("projects", [])
        ],
        "sessions": [
            {"id": s["id"], "date": s.get("date", ""), "period": s.get("period", "")}
            for s in snapshot.get("sessions", [])
        ],
        "unavailabilities": snapshot.get("unavailabilities", []),
        "conflicts": snapshot.get("conflicts", []),
        "constraint_rules": snapshot.get("constraint_rules", []),
        "default_weights": snapshot.get("default_weights", {}),
    }


def extract_constraints_via_llm(prompt: str, snapshot: dict[str, Any]) -> dict[str, Any] | None:
    system_prompt, _ = prompt_registry.get_with_hash("translator.system.txt")
    schema_prompt, _ = prompt_registry.get_with_hash("translator.schema.txt")

    provider = get_provider()
    full_system_prompt = f"{system_prompt}\n\nReturn strict JSON only.\n{schema_prompt}"
    user_message = json.dumps(
        {"prompt": prompt, "db_snapshot": _slim_snapshot(snapshot)},
        ensure_ascii=True,
    )

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

    # The LLM now returns a constraint delta, not a full payload.
    # Extract only the recognised constraint-related keys.
    delta: dict[str, Any] = {}
    for key in ("constraints", "unavailabilities", "conflicts", "constraint_rules"):
        if key in candidate and candidate[key] is not None:
            delta[key] = candidate[key]

    if not delta:
        _log.warning("LLM returned no constraint fields — ignoring response")
        return None

    _log.info(
        "LLM delta extracted — hard=%d soft=%d unavailabilities=%d conflicts=%d constraint_rules=%d",
        len((delta.get("constraints") or {}).get("hard") or []),
        len((delta.get("constraints") or {}).get("soft") or []),
        len(delta.get("unavailabilities") or []),
        len(delta.get("conflicts") or []),
        len(delta.get("constraint_rules") or []),
    )
    return delta
