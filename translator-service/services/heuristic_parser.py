from __future__ import annotations

import re
from typing import Literal

_KNOWN_KEYWORDS: dict[str, str] = {
    # --- payload-based constraints (conflicts list / unavailabilities list) ---
    "conflict":          "conflict_of_interest",
    "conflit":           "conflict_of_interest",
    "conflits":          "conflict_of_interest",
    "incompatible":      "conflict_of_interest",
    "unavailable":       "declared_unavailability",
    "indisponible":      "declared_unavailability",
    "indisponibilité":   "declared_unavailability",

    # --- hard custom rules (solver: hard_constraints.py apply_custom_hard_constraints) ---
    "forbid":            "forbid_professor_session",
    "interdit":          "forbid_professor_session",
    "interdire":         "forbid_professor_session",
    "require":           "require_professor_role",
    "exiger":            "require_professor_role",

    # --- soft custom rules (solver: soft_constraints.py build_custom_soft_penalty) ---
    "morning":           "prefer_morning",
    "matin":             "prefer_morning",
    "matinée":           "prefer_morning",
    "avoid":             "avoid_professor_session",
    "éviter":            "avoid_professor_session",
    "penalize":          "penalize_professor_project",
    "pénaliser":         "penalize_professor_project",
    "prefer":            "prefer_professor_role",
    "préférer":          "prefer_professor_role",

    # --- weight knobs (constraints.weights in solver payload) ---
    "balance":           "workload",
    "équilibrer":        "workload",
    "charge":            "workload",
    "expertise":         "expertise",
    "domaine":           "expertise",
    "cluster":           "clustering",
    "regrouper":         "clustering",
    "overload":          "overload",
    "surcharge":         "overload",
}

_CONSTRAINT_TOKENS = (
    "must", "should", "avoid", "prefer", "cannot", "can't", "only", "no ",
    "éviter", "ne pas", "doit", "doivent", "préférer", "limiter", "interdire",
    "impossible", "obligatoire",
)

# Keywords that signal a hard constraint
_HARD_MARKERS = ("hard", "dur", "obligatoire", "absolument", "interdit", "impossible", "strictement")
# Keywords that signal a soft constraint
_SOFT_MARKERS = ("soft", "souple", "préférable", "préférablement", "de préférence", "si possible", "idéalement")


def detect_conflict_type(prompt: str) -> Literal["hard", "soft"]:
    """Detect whether the prompt describes a hard or soft conflict."""
    lowered = prompt.lower()
    for marker in _SOFT_MARKERS:
        if marker in lowered:
            return "soft"
    for marker in _HARD_MARKERS:
        if marker in lowered:
            return "hard"
    return "hard"  # conflicts default to hard


def recognized_from_prompt(prompt: str) -> list[dict[str, str]]:
    lowered = prompt.lower()
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for key, name in _KNOWN_KEYWORDS.items():
        if key in lowered and name not in seen:
            seen.add(name)
            result.append({"name": name, "source": "prompt"})
    return result


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
