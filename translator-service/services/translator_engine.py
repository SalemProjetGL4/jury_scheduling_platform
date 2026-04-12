from __future__ import annotations

import json
import re
from typing import Any

from adapters.db_snapshot_adapter import build_db_snapshot
from adapters.llm_provider_adapter import get_provider
from adapters.prompt_registry import prompt_registry
from contracts.orchestrator_output import extract_json_object
from contracts.translator_output import (
    SUPPORTED_HARD_RULES,
    SUPPORTED_SOFT_RULES,
    TranslatorAnalysis,
    validate_solver_payload,
)


_KNOWN_KEYWORDS = {
    "unavailable": "declared_unavailability",
    "conflict": "conflict_of_interest",
    "balance": "role_balance",
    "expertise": "expertise_alignment",
    "cluster": "same_day_clustering",
    "morning": "prefer_morning",
    "session": "session_structure",
    "role": "role_uniqueness",
}


def _build_solver_payload_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    professors = [
        {"id": p["id"], "domain_id": p["domain_id"], "max_juries": p["max_juries"]}
        for p in snapshot.get("professors", [])
    ]
    projects = [
        {"id": p["id"], "domain_id": p["domain_id"], "supervisor_id": p["supervisor_id"]}
        for p in snapshot.get("projects", [])
    ]
    sessions = [
        {"id": s["id"], "date": s["date"], "period": s["period"]}
        for s in snapshot.get("sessions", [])
    ]

    max_juries_values = [p["max_juries"] for p in professors] or [2]
    global_cap = max(max_juries_values)

    hard_rules: list[dict[str, Any]] = []
    soft_rules: list[dict[str, Any]] = []
    passthrough_rules: list[dict[str, Any]] = []

    for rule in snapshot.get("constraint_rules", []):
        payload = dict(rule.get("payload") or {})
        if "rule" not in payload and rule.get("rule"):
            payload["rule"] = rule["rule"]

        rule_name = str(payload.get("rule", ""))
        if rule.get("type") == "hard" and rule_name in SUPPORTED_HARD_RULES:
            hard_rules.append(payload)
        elif rule.get("type") == "soft" and rule_name in SUPPORTED_SOFT_RULES:
            payload.setdefault("weight", float(rule.get("weight", 1.0)))
            soft_rules.append(payload)

        passthrough_rules.append(
            {
                "name": str(rule.get("name", "")),
                "rule": str(rule_name),
                "type": str(rule.get("type", "soft")),
                "weight": float(rule.get("weight", 1.0)),
                "payload": payload,
                "enabled": bool(rule.get("enabled", True)),
            }
        )

    return {
        "professors": professors,
        "projects": projects,
        "sessions": sessions,
        "constraints": {
            "hard_max_juries": global_cap,
            "weights": dict(snapshot.get("default_weights", {})),
            "hard": hard_rules,
            "soft": soft_rules,
        },
        "unavailabilities": list(snapshot.get("unavailabilities", [])),
        "conflicts": list(snapshot.get("conflicts", [])),
        "constraint_rules": passthrough_rules,
    }


def _heuristic_unrecognized(prompt: str) -> list[dict[str, str]]:
    parts = [item.strip() for item in re.split(r"[.;\\n]", prompt) if item.strip()]
    unknown: list[dict[str, str]] = []

    for part in parts:
        lowered = part.lower()
        mentions_constraint = any(
            token in lowered for token in ("must", "should", "avoid", "prefer", "cannot", "can't", "only", "no ")
        )
        if not mentions_constraint:
            continue
        if any(key in lowered for key in _KNOWN_KEYWORDS):
            continue
        unknown.append(
            {
                "raw_text": part,
                "inferred_type": "soft",
                "reason_unrecognized": "No mapping found to supported solver rules",
            }
        )

    return unknown


def _recognized_from_prompt(prompt: str) -> list[dict[str, str]]:
    lowered = prompt.lower()
    results: list[dict[str, str]] = []
    for key, name in _KNOWN_KEYWORDS.items():
        if key in lowered:
            results.append({"name": name, "source": "prompt"})
    return results


def _apply_llm_analysis(prompt: str, snapshot: dict[str, Any]) -> TranslatorAnalysis | None:
    system_prompt, _ = prompt_registry.get_with_hash("translator.system.txt")
    schema_prompt, _ = prompt_registry.get_with_hash("translator.schema.txt")

    provider = get_provider()
    user_message = json.dumps({"prompt": prompt, "db_snapshot": snapshot}, ensure_ascii=True)
    raw_output = provider.complete(
        system_prompt=f"{system_prompt}\n\nReturn strict JSON only.\n{schema_prompt}",
        user_message=user_message,
    )

    payload = json.loads(extract_json_object(raw_output))
    return TranslatorAnalysis.model_validate(payload)


def translate_prompt(*, request_id: str, prompt: str, user_id: str | None) -> dict[str, Any]:
    _ = request_id
    _ = user_id

    snapshot = build_db_snapshot()
    payload = _build_solver_payload_from_snapshot(snapshot)

    recognized = _recognized_from_prompt(prompt)
    recognized.extend(
        {
            "name": str(rule.get("rule") or rule.get("name") or "unknown_rule"),
            "source": "database",
        }
        for rule in snapshot.get("constraint_rules", [])
        if rule.get("rule")
    )
    unrecognized = _heuristic_unrecognized(prompt)

    try:
        analysis = _apply_llm_analysis(prompt, snapshot)
        if analysis:
            recognized.extend(item.model_dump() for item in analysis.recognized_constraints)
            unrecognized.extend(item.model_dump() for item in analysis.unrecognized_constraints)
            payload["constraints"]["weights"].update(analysis.weight_overrides)
    except Exception:
        # Fallback is intentional: continue with deterministic heuristic extraction.
        pass

    validated_payload, validation_error = validate_solver_payload(payload)
    if validated_payload is None:
        raise ValueError(f"translator_payload_invalid: {validation_error}")

    unique_recognized: dict[str, dict[str, str]] = {}
    for item in recognized:
        key = f"{item['name']}::{item['source']}"
        unique_recognized[key] = item

    unique_unrecognized: dict[str, dict[str, str]] = {}
    for item in unrecognized:
        key = f"{item['raw_text']}::{item['reason_unrecognized']}"
        unique_unrecognized[key] = item

    return {
        "request_id": request_id,
        "translator_payload": validated_payload.model_dump(mode="json"),
        "recognized_constraints": list(unique_recognized.values()),
        "unrecognized_constraints": list(unique_unrecognized.values()),
        "db_snapshot": snapshot,
    }
