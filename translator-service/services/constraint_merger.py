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
        if not isinstance(raw_rule, dict):
            continue

        is_enabled = raw_rule.get("enabled", True)

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

        if not is_enabled:
            # Rule was disabled/removed by the user — purge it from constraints.hard/soft
            # so the solver does not apply it, even if it came from the DB snapshot.
            merged_constraints["hard"] = [
                r for r in merged_constraints["hard"]
                if str(r.get("rule", "")).strip().lower() != inferred_name
            ]
            merged_constraints["soft"] = [
                r for r in merged_constraints["soft"]
                if str(r.get("rule", "")).strip().lower() != inferred_name
            ]
            hard_seen = {rule_signature(r) for r in merged_constraints["hard"]}
            soft_seen = {rule_signature(r) for r in merged_constraints["soft"]}
            recognized.append({"name": f"{inferred_name}_disabled", "source": "llm"})
            continue

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

    # --- Unavailabilities ---
    # The LLM output is the intended final state.  We compare against the snapshot
    # (already in merged) to classify each entry as new / existing / removed.
    snapshot_unavail_keys: set[tuple[int, str, str]] = {
        (int(u["professor_id"]), str(u["date"]), str(u["period"]))
        for u in merged.get("unavailabilities", [])
        if isinstance(u, dict) and "professor_id" in u
    }

    if isinstance(llm_payload, dict) and "unavailabilities" in llm_payload:
        validated_unavails: list[dict[str, Any]] = []
        seen_unavail_keys: set[tuple[int, str, str]] = set()

        for unavail in llm_payload.get("unavailabilities", []):
            if not isinstance(unavail, dict):
                continue
            pid = unavail.get("professor_id")
            date_val = unavail.get("date")
            period_val = unavail.get("period")
            if pid is None or date_val is None or period_val is None:
                continue
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                continue

            if pid not in professor_ids:
                unrecognized.append(
                    {
                        "raw_text": json.dumps(unavail, ensure_ascii=True),
                        "inferred_type": "hard",
                        "reason_unrecognized": f"Professor ID {pid} not found in snapshot",
                    }
                )
                continue

            key = (pid, str(date_val), str(period_val))
            if key in seen_unavail_keys:
                continue
            seen_unavail_keys.add(key)
            validated_unavails.append({"professor_id": pid, "date": str(date_val), "period": str(period_val)})
            is_existing = key in snapshot_unavail_keys
            recognized.append(
                {"name": "declared_unavailability_existing" if is_existing else "declared_unavailability_new", "source": "llm"}
            )

        for key in snapshot_unavail_keys:
            if key not in seen_unavail_keys:
                recognized.append({"name": "declared_unavailability_removed", "source": "llm"})

        merged["unavailabilities"] = validated_unavails

    # --- Conflicts ---
    # Same pattern: LLM output is the intended final state.
    snapshot_conflict_keys: set[tuple[int, int]] = {
        (min(c["professor_a"], c["professor_b"]), max(c["professor_a"], c["professor_b"]))
        for c in merged.get("conflicts", [])
        if isinstance(c, dict) and "professor_a" in c and "professor_b" in c
    }

    if isinstance(llm_payload, dict) and "conflicts" in llm_payload:
        validated_conflicts: list[dict[str, Any]] = []
        seen_conflict_keys: set[tuple[int, int]] = set()

        for conflict in llm_payload.get("conflicts", []):
            if not isinstance(conflict, dict):
                continue
            pa = conflict.get("professor_a")
            pb = conflict.get("professor_b")
            if pa is None or pb is None:
                continue
            try:
                pa, pb = int(pa), int(pb)
            except (TypeError, ValueError):
                continue

            if pa not in professor_ids or pb not in professor_ids:
                unrecognized.append(
                    {
                        "raw_text": json.dumps(conflict, ensure_ascii=True),
                        "inferred_type": "hard",
                        "reason_unrecognized": f"Professor ID {pa} or {pb} not found in snapshot",
                    }
                )
                continue

            key = (min(pa, pb), max(pa, pb))
            if key in seen_conflict_keys:
                continue
            seen_conflict_keys.add(key)
            validated_conflicts.append({"professor_a": pa, "professor_b": pb})
            is_existing = key in snapshot_conflict_keys
            recognized.append(
                {"name": "conflict_of_interest_existing" if is_existing else "conflict_of_interest_new", "source": "llm"}
            )

        for key in snapshot_conflict_keys:
            if key not in seen_conflict_keys:
                recognized.append({"name": "conflict_of_interest_removed", "source": "llm"})

        merged["conflicts"] = validated_conflicts

    return merged, recognized, unrecognized
