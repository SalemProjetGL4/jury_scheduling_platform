from __future__ import annotations

import json
from typing import Any

from services.rule_sanitizer import sanitize_rule
from services.rule_utils import (
    WEIGHT_KEYS,
    as_int,
    normalized_rule_type,
    rule_signature,
)


def merge_llm_constraints(
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
        if key not in WEIGHT_KEYS:
            continue
        value = as_int(raw_value)
        if value is None or value < 0:
            continue
        if as_int(merged_constraints["weights"].get(key)) == value:
            continue
        merged_constraints["weights"][key] = value
        recognized.append({"name": f"weight_{key}", "source": "llm"})

    hard_seen = {rule_signature(r) for r in merged_constraints["hard"] if isinstance(r, dict)}
    soft_seen = {rule_signature(r) for r in merged_constraints["soft"] if isinstance(r, dict)}

    id_sets = dict(professor_ids=professor_ids, project_ids=project_ids, session_ids=session_ids)

    for rule_type in ("hard", "soft"):
        for raw_rule in llm_constraints.get(rule_type, []):
            inferred_type = rule_type
            if isinstance(raw_rule, dict):
                inferred_name = str(raw_rule.get("rule", "")).strip().lower()
                inferred_type = normalized_rule_type(inferred_name) or rule_type

            sanitized, reason = sanitize_rule(raw_rule, rule_type=inferred_type, **id_sets)
            if sanitized is None:
                unrecognized.append(
                    {
                        "raw_text": json.dumps(raw_rule, ensure_ascii=True),
                        "inferred_type": inferred_type,
                        "reason_unrecognized": reason or "Could not sanitize rule",
                    }
                )
                continue

            sig = rule_signature(sanitized)
            if inferred_type == "hard":
                if sig not in hard_seen:
                    hard_seen.add(sig)
                    merged_constraints["hard"].append(sanitized)
            else:
                if sig not in soft_seen:
                    soft_seen.add(sig)
                    merged_constraints["soft"].append(sanitized)

            recognized.append({"name": str(sanitized["rule"]), "source": "llm"})

    for raw_rule in llm_payload.get("constraint_rules", []) if isinstance(llm_payload, dict) else []:
        if not isinstance(raw_rule, dict) or not raw_rule.get("enabled", True):
            continue

        declared_type = str(raw_rule.get("type", "")).strip().lower()
        if declared_type not in {"hard", "soft"}:
            continue

        payload = dict(raw_rule.get("payload") or {})
        if "rule" not in payload and raw_rule.get("rule"):
            payload["rule"] = raw_rule.get("rule")
        if declared_type == "soft" and "weight" not in payload and "weight" in raw_rule:
            payload["weight"] = raw_rule.get("weight")

        inferred_name = str(payload.get("rule", "")).strip().lower()
        inferred_type = normalized_rule_type(inferred_name) or declared_type

        sanitized, reason = sanitize_rule(payload, rule_type=inferred_type, **id_sets)
        if sanitized is None:
            unrecognized.append(
                {
                    "raw_text": json.dumps(raw_rule, ensure_ascii=True),
                    "inferred_type": inferred_type,
                    "reason_unrecognized": reason or "Could not sanitize constraint_rules entry",
                }
            )
            continue

        sig = rule_signature(sanitized)
        if inferred_type == "hard":
            if sig not in hard_seen:
                hard_seen.add(sig)
                merged_constraints["hard"].append(sanitized)
                recognized.append({"name": str(sanitized["rule"]), "source": "llm"})
        else:
            if sig not in soft_seen:
                soft_seen.add(sig)
                merged_constraints["soft"].append(sanitized)
                recognized.append({"name": str(sanitized["rule"]), "source": "llm"})

    return merged, recognized, unrecognized
