from __future__ import annotations

from typing import Any

from contracts.translator_output import SUPPORTED_HARD_RULES, SUPPORTED_SOFT_RULES


def snapshot_stats(snapshot: dict[str, Any]) -> dict[str, Any]:
    constraint_rules = snapshot.get("constraint_rules", [])
    soft_rules = [r for r in constraint_rules if str(r.get("type", "")).lower() == "soft"]
    hard_rules = [r for r in constraint_rules if str(r.get("type", "")).lower() == "hard"]

    periods = sorted({str(s.get("period", "")) for s in snapshot.get("sessions", []) if s.get("period")})
    session_dates = [str(s.get("date", "")) for s in snapshot.get("sessions", []) if s.get("date")]

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


def build_solver_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    professors = [
        {
            "id": p["id"],
            "domain_id": p["domain_id"],
            "domain_ids": list(p.get("domain_ids") or []),
            "department_id": p.get("department_id", 0),
            "max_juries": p["max_juries"],
        }
        for p in snapshot.get("professors", [])
    ]
    projects = [
        {
            "id": p["id"],
            "domain_ids": list(p.get("domain_ids") or []),
            "domain_id": (p.get("domain_ids") or [0])[0],
            "domain_keywords": list(p.get("domain_keywords") or []),
            "supervisor_id": p["supervisor_id"],
            "student_filiere_id": p.get("student_filiere_id", 0),
            "filiere_department_id": p.get("filiere_department_id", 0),
        }
        for p in snapshot.get("projects", [])
    ]
    sessions = [
        {
            "id": s["id"],
            "date": s["date"],
            "period": s["period"],
            "slot_number": s.get("slot_number"),
            "start_time": s.get("start_time"),
            "end_time": s.get("end_time"),
        }
        for s in snapshot.get("sessions", [])
    ]
    assert all(s["start_time"] is not None for s in sessions), \
        f"sessions missing start_time: {[s for s in sessions if s['start_time'] is None]}"

    global_cap = max((p["max_juries"] for p in professors), default=2)

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
