from __future__ import annotations

import re

_KNOWN_KEYWORDS: dict[str, str] = {
    "unavailable": "declared_unavailability",
    "conflict": "conflict_of_interest",
    "balance": "role_balance",
    "expertise": "expertise_alignment",
    "cluster": "same_day_clustering",
    "morning": "prefer_morning",
    "session": "session_structure",
    "role": "role_uniqueness",
}

_CONSTRAINT_TOKENS = ("must", "should", "avoid", "prefer", "cannot", "can't", "only", "no ")


def recognized_from_prompt(prompt: str) -> list[dict[str, str]]:
    lowered = prompt.lower()
    return [
        {"name": name, "source": "prompt"}
        for key, name in _KNOWN_KEYWORDS.items()
        if key in lowered
    ]


def heuristic_unrecognized(prompt: str) -> list[dict[str, str]]:
    parts = [item.strip() for item in re.split(r"[.;\n]", prompt) if item.strip()]
    unknown: list[dict[str, str]] = []

    for part in parts:
        lowered = part.lower()
        if not any(token in lowered for token in _CONSTRAINT_TOKENS):
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
