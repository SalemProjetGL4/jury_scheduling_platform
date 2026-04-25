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

_SUPPORTED_RULES = SUPPORTED_HARD_RULES | SUPPORTED_SOFT_RULES
_WEIGHT_KEYS = {"workload", "expertise", "clustering", "overload", "custom"}
_SUPPORTED_ROLES = {"SUPERVISOR", "PRESIDENT", "EXAMINER"}


def _snapshot_stats(snapshot: dict[str, Any]) -> dict[str, Any]:
    constraint_rules = snapshot.get("constraint_rules", [])
    soft_rules = [rule for rule in constraint_rules if str(rule.get("type", "")).lower() == "soft"]
    hard_rules = [rule for rule in constraint_rules if str(rule.get("type", "")).lower() == "hard"]

    periods = sorted({str(item.get("period", "")) for item in snapshot.get("sessions", []) if item.get("period")})
    session_dates = [str(item.get("date", "")) for item in snapshot.get("sessions", []) if item.get("date")]

    return {
        "professors_count": len(snapshot.get("professors", [])),
        "projects_count": len(snapshot.get("projects", [])),
        "sessions_count": len(snapshot.get("sessions", [])),
        "unavailabilities_count": len(snapshot.get("unavailabilities", [])),
        "conflicts_count": len(snapshot.get("conflicts", [])),
        "constraint_rules_total": len(constraint_rules),
        "constraint_rules_hard": len(hard_rules),
        "constraint_rules_soft": len(soft_rules),
        "session_periods": periods,
        "session_date_min": min(session_dates) if session_dates else None,
        "session_date_max": max(session_dates) if session_dates else None,
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


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any, *, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalized_rule_type_from_name(rule_name: str) -> str | None:
    if rule_name in SUPPORTED_HARD_RULES:
        return "hard"
    if rule_name in SUPPORTED_SOFT_RULES:
        return "soft"
    return None


def _normalize_roles(raw_roles: Any) -> list[str]:
    if isinstance(raw_roles, str):
        items = [raw_roles]
    elif isinstance(raw_roles, list):
        items = [str(role) for role in raw_roles]
    else:
        return []

    normalized = [role.upper().strip() for role in items if role]
    return [role for role in normalized if role in _SUPPORTED_ROLES]


def _rule_signature(rule: dict[str, Any]) -> str:
    return json.dumps(rule, sort_keys=True, ensure_ascii=True)


def _sanitize_rule(
    raw_rule: Any,
    *,
    rule_type: str,
    professor_ids: set[int],
    project_ids: set[int],
    session_ids: set[int],
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw_rule, dict):
        return None, "Rule must be a JSON object"

    name = str(raw_rule.get("rule", "")).strip().lower()
    if name not in _SUPPORTED_RULES:
        return None, "Rule is not supported by solver"

    if rule_type == "hard" and name not in SUPPORTED_HARD_RULES:
        return None, "Rule type mismatch for hard constraints"
    if rule_type == "soft" and name not in SUPPORTED_SOFT_RULES:
        return None, "Rule type mismatch for soft constraints"

    normalized: dict[str, Any] = {"rule": name}

    if name == "prefer_morning":
        if rule_type == "soft":
            normalized["weight"] = _as_float(raw_rule.get("weight", 1.0), default=1.0)
        return normalized, None

    professor_id = _as_int(raw_rule.get("professor_id"))
    project_id = _as_int(raw_rule.get("project_id"))
    session_id = _as_int(raw_rule.get("session_id"))

    if name in {"forbid_professor_session", "avoid_professor_session"}:
        if professor_id not in professor_ids or session_id not in session_ids:
            return None, "professor_id or session_id not found in database snapshot"
        normalized["professor_id"] = professor_id
        normalized["session_id"] = session_id

    elif name in {"require_project_session", "prefer_project_session"}:
        if project_id not in project_ids or session_id not in session_ids:
            return None, "project_id or session_id not found in database snapshot"
        normalized["project_id"] = project_id
        normalized["session_id"] = session_id

    elif name in {"forbid_professor_project", "penalize_professor_project"}:
        if professor_id not in professor_ids or project_id not in project_ids:
            return None, "professor_id or project_id not found in database snapshot"
        normalized["professor_id"] = professor_id
        normalized["project_id"] = project_id
        roles = _normalize_roles(raw_rule.get("roles"))
        if roles:
            normalized["roles"] = roles

    elif name in {"require_professor_role", "prefer_professor_role"}:
        role = str(raw_rule.get("role", "")).upper().strip()
        if professor_id not in professor_ids or project_id not in project_ids:
            return None, "professor_id or project_id not found in database snapshot"
        if role not in _SUPPORTED_ROLES:
            return None, "role must be one of SUPERVISOR, PRESIDENT, EXAMINER"

        normalized["professor_id"] = professor_id
        normalized["project_id"] = project_id
        normalized["role"] = role
        if session_id is not None:
            if session_id not in session_ids:
                return None, "session_id not found in database snapshot"
            normalized["session_id"] = session_id

    if rule_type == "soft":
        normalized["weight"] = _as_float(raw_rule.get("weight", 1.0), default=1.0)

    return normalized, None


def _apply_llm_payload(prompt: str, snapshot: dict[str, Any]) -> dict[str, Any] | None:
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

    raw_output = provider.complete(
        system_prompt=full_system_prompt,
        user_message=user_message,
    )

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


def _merge_llm_constraints(
    *,
    base_payload: dict[str, Any],
    llm_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    merged = json.loads(json.dumps(base_payload, ensure_ascii=True))
    recognized: list[dict[str, str]] = []
    unrecognized: list[dict[str, str]] = []

    professor_ids = {int(item["id"]) for item in merged.get("professors", [])}
    project_ids = {int(item["id"]) for item in merged.get("projects", [])}
    session_ids = {int(item["id"]) for item in merged.get("sessions", [])}

    merged_constraints = merged.setdefault("constraints", {})
    merged_constraints.setdefault("weights", {})
    merged_constraints.setdefault("hard", [])
    merged_constraints.setdefault("soft", [])

    llm_constraints = llm_payload.get("constraints", {}) if isinstance(llm_payload, dict) else {}
    llm_weights = llm_constraints.get("weights", {}) if isinstance(llm_constraints, dict) else {}

    for key, raw_value in llm_weights.items():
        if key not in _WEIGHT_KEYS:
            continue
        value = _as_int(raw_value)
        if value is None or value < 0:
            continue
        current_value = _as_int(merged_constraints["weights"].get(key))
        if current_value == value:
            continue
        merged_constraints["weights"][key] = value
        recognized.append({"name": f"weight_{key}", "source": "llm"})

    hard_seen = {_rule_signature(rule) for rule in merged_constraints["hard"] if isinstance(rule, dict)}
    soft_seen = {_rule_signature(rule) for rule in merged_constraints["soft"] if isinstance(rule, dict)}

    for rule_type in ("hard", "soft"):
        for raw_rule in llm_constraints.get(rule_type, []):
            inferred_type = rule_type
            if isinstance(raw_rule, dict):
                inferred_name = str(raw_rule.get("rule", "")).strip().lower()
                inferred_type = _normalized_rule_type_from_name(inferred_name) or rule_type

            sanitized, reason = _sanitize_rule(
                raw_rule,
                rule_type=inferred_type,
                professor_ids=professor_ids,
                project_ids=project_ids,
                session_ids=session_ids,
            )
            if sanitized is None:
                unrecognized.append(
                    {
                        "raw_text": json.dumps(raw_rule, ensure_ascii=True),
                        "inferred_type": inferred_type,
                        "reason_unrecognized": reason or "Could not sanitize rule",
                    }
                )
                continue

            signature = _rule_signature(sanitized)
            if inferred_type == "hard":
                if signature in hard_seen:
                    continue
                hard_seen.add(signature)
                merged_constraints["hard"].append(sanitized)
            else:
                if signature in soft_seen:
                    continue
                soft_seen.add(signature)
                merged_constraints["soft"].append(sanitized)

            recognized.append({"name": str(sanitized["rule"]), "source": "llm"})

    for raw_rule in llm_payload.get("constraint_rules", []) if isinstance(llm_payload, dict) else []:
        if not isinstance(raw_rule, dict):
            continue
        if not raw_rule.get("enabled", True):
            continue

        declared_type = str(raw_rule.get("type", "")).strip().lower()
        if declared_type not in {"hard", "soft"}:
            continue

        payload = raw_rule.get("payload") if isinstance(raw_rule.get("payload"), dict) else {}
        payload = dict(payload)
        if "rule" not in payload and raw_rule.get("rule"):
            payload["rule"] = raw_rule.get("rule")
        if declared_type == "soft" and "weight" not in payload and "weight" in raw_rule:
            payload["weight"] = raw_rule.get("weight")

        inferred_name = str(payload.get("rule", "")).strip().lower()
        inferred_type = _normalized_rule_type_from_name(inferred_name) or declared_type

        sanitized, reason = _sanitize_rule(
            payload,
            rule_type=inferred_type,
            professor_ids=professor_ids,
            project_ids=project_ids,
            session_ids=session_ids,
        )
        if sanitized is None:
            unrecognized.append(
                {
                    "raw_text": json.dumps(raw_rule, ensure_ascii=True),
                    "inferred_type": inferred_type,
                    "reason_unrecognized": reason or "Could not sanitize constraint_rules entry",
                }
            )
            continue

        signature = _rule_signature(sanitized)
        if inferred_type == "hard":
            if signature not in hard_seen:
                hard_seen.add(signature)
                merged_constraints["hard"].append(sanitized)
                recognized.append({"name": str(sanitized["rule"]), "source": "llm"})
        else:
            if signature not in soft_seen:
                soft_seen.add(signature)
                merged_constraints["soft"].append(sanitized)
                recognized.append({"name": str(sanitized["rule"]), "source": "llm"})

    return merged, recognized, unrecognized


def _heuristic_unrecognized(prompt: str) -> list[dict[str, str]]:
    parts = [item.strip() for item in re.split(r"[.;\n]", prompt) if item.strip()]
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


def translate_prompt(*, request_id: str, prompt: str, user_id: str | None) -> dict[str, Any]:
    print("[translator-service] TRANSLATION REQUEST START")
    print(json.dumps({"request_id": request_id, "user_id": user_id}, ensure_ascii=True))
    print("[translator-service] USER PROMPT START")
    print(prompt)
    print("[translator-service] USER PROMPT END")

    snapshot = build_db_snapshot()
    print("[translator-service] DB SNAPSHOT STATS START")
    print(json.dumps(_snapshot_stats(snapshot), ensure_ascii=True, indent=2))
    print("[translator-service] DB SNAPSHOT STATS END")

    payload = _build_solver_payload_from_snapshot(snapshot)

    recognized = _recognized_from_prompt(prompt)

    for rule in snapshot.get("constraint_rules", []):
        rule_name = str(rule.get("rule") or rule.get("name") or "unknown_rule").strip().lower()
        if not rule_name:
            continue

        if rule_name in _SUPPORTED_RULES:
            recognized.append({"name": rule_name, "source": "database"})

    unrecognized = _heuristic_unrecognized(prompt)
    for rule in snapshot.get("constraint_rules", []):
        rule_name = str(rule.get("rule") or "").strip().lower()
        if rule_name and rule_name not in _SUPPORTED_RULES:
            unrecognized.append(
                {
                    "raw_text": str(rule.get("name") or rule_name),
                    "inferred_type": str(rule.get("type") or "hard"),
                    "reason_unrecognized": "Database rule is not mapped to supported solver rules",
                }
            )

    try:
        llm_payload = _apply_llm_payload(prompt, snapshot)
        if llm_payload:
            payload, llm_recognized, llm_unrecognized = _merge_llm_constraints(
                base_payload=payload,
                llm_payload=llm_payload,
            )
            recognized.extend(llm_recognized)
            unrecognized.extend(llm_unrecognized)
    except Exception:
        # Fallback is intentional: continue with deterministic heuristic extraction.
        pass

    validated_payload, validation_error = validate_solver_payload(payload)
    if validated_payload is None:
        raise ValueError(f"translator_payload_invalid: {validation_error}")

    unique_recognized: dict[str, dict[str, str]] = {}
    for item in recognized:
        name = str(item.get("name", "")).strip()
        source = str(item.get("source", "")).strip()
        if not name or not source:
            continue
        key = f"{name}::{source}"
        unique_recognized[key] = {"name": name, "source": source}

    unique_unrecognized: dict[str, dict[str, str]] = {}
    for item in unrecognized:
        raw_text = str(item.get("raw_text", "")).strip()
        inferred_type = str(item.get("inferred_type", "soft")).strip() or "soft"
        reason = str(item.get("reason_unrecognized", "Unknown reason")).strip()
        if not raw_text or not reason:
            continue
        key = f"{raw_text}::{reason}"
        unique_unrecognized[key] = {
            "raw_text": raw_text,
            "inferred_type": inferred_type,
            "reason_unrecognized": reason,
        }

    return {
        "request_id": request_id,
        "translator_payload": validated_payload.model_dump(mode="json"),
        "recognized_constraints": list(unique_recognized.values()),
        "unrecognized_constraints": list(unique_unrecognized.values()),
        "db_snapshot": snapshot,
    }
