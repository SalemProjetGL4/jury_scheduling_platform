from __future__ import annotations

import json
import time
from typing import Any

from adapters.db_snapshot_adapter import build_db_snapshot
from contracts.translator_output import validate_solver_payload
from services.constraint_merger import merge_llm_constraints
from services.heuristic_parser import heuristic_unrecognized, recognized_from_prompt
from services.llm_extractor import extract_constraints_via_llm
from services.rule_utils import SUPPORTED_RULES
from services.snapshot_builder import build_solver_payload, snapshot_stats

try:
    from log_setup import logger
except Exception:
    import logging
    logger = logging.getLogger("translator")


def translate_prompt(*, request_id: str, prompt: str, user_id: str | None) -> dict[str, Any]:
    logger.info("TRANSLATE REQUEST — request_id=%s user_id=%s", request_id, user_id)
    logger.debug("USER PROMPT — %r", prompt[:200])

    timing_info: dict[str, float] = {}

    # ── Step: database_snapshot_retrieval ────────────────────────────────────
    _t = time.monotonic()
    snapshot = build_db_snapshot()
    timing_info["database_snapshot_retrieval"] = round((time.monotonic() - _t) * 1000)

    stats = snapshot_stats(snapshot)
    logger.info(
        "DB SNAPSHOT — professors=%d projects=%d slots=%d constraint_rules=%d (hard=%d soft=%d)",
        stats["professors_count"],
        stats["projects_count"],
        stats["sessions_count"],
        stats["constraint_rules_total"],
        stats["constraint_rules_hard"],
        stats["constraint_rules_soft"],
    )

    payload = build_solver_payload(snapshot)
    recognized = recognized_from_prompt(prompt)

    for rule in snapshot.get("constraint_rules", []):
        rule_name = str(rule.get("rule") or rule.get("name") or "").strip().lower()
        if rule_name and rule_name in SUPPORTED_RULES:
            recognized.append({"name": rule_name, "source": "database"})

    unrecognized = heuristic_unrecognized(prompt)
    for rule in snapshot.get("constraint_rules", []):
        rule_name = str(rule.get("rule") or "").strip().lower()
        if rule_name and rule_name not in SUPPORTED_RULES:
            unrecognized.append(
                {
                    "raw_text": str(rule.get("name") or rule_name),
                    "inferred_type": str(rule.get("type") or "hard"),
                    "reason_unrecognized": "Database rule is not mapped to supported solver rules",
                }
            )

    # ── Step: llm_structured_output_call ─────────────────────────────────────
    llm_token_usage: dict | None = None
    _t = time.monotonic()
    try:
        llm_payload, llm_token_usage = extract_constraints_via_llm(prompt, snapshot)
        if llm_payload:
            payload, llm_recognized, llm_unrecognized = merge_llm_constraints(
                base_payload=payload,
                llm_payload=llm_payload,
            )
            recognized.extend(llm_recognized)
            unrecognized.extend(llm_unrecognized)
    except Exception:
        # Intentional fallback: continue with deterministic heuristic extraction.
        pass
    timing_info["llm_structured_output_call"] = round((time.monotonic() - _t) * 1000)

    # ── Step: payload_validation ──────────────────────────────────────────────
    _t = time.monotonic()
    validated_payload, validation_error = validate_solver_payload(payload)
    timing_info["payload_validation"] = round((time.monotonic() - _t) * 1000)

    if validated_payload is None:
        raise ValueError(f"translator_payload_invalid: {validation_error}")

    unique_recognized = {
        f"{item['name']}::{item['source']}": {"name": item["name"], "source": item["source"]}
        for item in recognized
        if item.get("name") and item.get("source")
    }

    unique_unrecognized = {
        f"{item['raw_text']}::{item['reason_unrecognized']}": {
            "raw_text": item["raw_text"],
            "inferred_type": item.get("inferred_type") or "soft",
            "reason_unrecognized": item["reason_unrecognized"],
        }
        for item in unrecognized
        if item.get("raw_text") and item.get("reason_unrecognized")
    }

    return_dict = {
        "request_id": request_id,
        "translator_payload": validated_payload.model_dump(mode="json"),
        "recognized_constraints": list(unique_recognized.values()),
        "unrecognized_constraints": list(unique_unrecognized.values()),
        "db_snapshot": snapshot,
        "timing_info": timing_info,
        "token_usage": llm_token_usage,
    }
    logger.info(f"[TOKEN DEBUG] translator_engine return dict token_usage: {return_dict.get('token_usage')}")
    return return_dict
