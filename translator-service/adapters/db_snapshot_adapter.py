from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, text

from config import settings


def _iso(value: Any) -> str | Any:
    if isinstance(value, date):
        return value.isoformat()
    return value


def _decimal_to_float(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def build_db_snapshot() -> dict[str, Any]:
    engine = create_engine(settings.database_url, future=True)

    with engine.connect() as conn:
        professor_rows = conn.execute(
            text(
                """
                SELECT p.id, p.name, p.email, p.specialities, p.max_juries, p.domain AS domain_id, d.name AS domain_name
                FROM professor p
                LEFT JOIN domain d ON d.id = p.domain
                ORDER BY p.id
                """
            )
        ).mappings().all()

        project_rows = conn.execute(
            text(
                """
                SELECT pr.id, pr.title, pr.domain AS domain_id, d.name AS domain_name,
                       pr.supervisor_id, pr.student_id, st.name AS student_name
                FROM project pr
                LEFT JOIN domain d ON d.id = pr.domain
                LEFT JOIN student st ON st.id = pr.student_id
                ORDER BY pr.id
                """
            )
        ).mappings().all()

        slot_rows = conn.execute(
            text(
                """
                SELECT s.id, s.session_id, s.date, s.period, s.slot_number, s.room
                FROM slot s
                ORDER BY s.id
                """
            )
        ).mappings().all()

        unavailability_rows = conn.execute(
            text(
                """
                SELECT professor_id, date, period
                FROM unavailability
                ORDER BY id
                """
            )
        ).mappings().all()

        conflict_rows = conn.execute(
            text(
                """
                SELECT professor_a, professor_b
                FROM conflict
                ORDER BY id
                """
            )
        ).mappings().all()

        rule_rows = conn.execute(
            text(
                """
                SELECT name, type, weight, payload, enabled
                FROM constraint_rule
                WHERE enabled = true
                ORDER BY id
                """
            )
        ).mappings().all()

    sessions = [
        {
            "id": int(row["id"]),
            "session_id": int(row["session_id"]),
            "date": _iso(row["date"]),
            "period": str(row["period"]),
            "slot_number": int(row["slot_number"]),
            "room": str(row["room"]),
        }
        for row in slot_rows
    ]

    projects: list[dict[str, Any]] = []
    for row in project_rows:
        domain_name = str(row["domain_name"] or "")
        projects.append(
            {
                "id": int(row["id"]),
                "title": str(row["title"]),
                "domain_id": int(row["domain_id"]),
                "domain_name": domain_name,
                "domain_keywords": [part.strip().lower() for part in domain_name.split() if part.strip()],
                "supervisor_id": int(row["supervisor_id"]),
                "student_name": str(row["student_name"] or ""),
            }
        )

    rules: list[dict[str, Any]] = []
    for row in rule_rows:
        payload = dict(row["payload"] or {})
        rule_name = str(payload.get("rule") or "")
        rules.append(
            {
                "name": str(row["name"]),
                "rule": rule_name,
                "type": str(row["type"]),
                "weight": float(_decimal_to_float(row["weight"])),
                "payload": payload,
                "enabled": bool(row["enabled"]),
            }
        )

    weights = defaultdict(lambda: 1)
    for rule in rules:
        if rule["type"] == "soft":
            weights["custom"] = 1

    return {
        "professors": [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "email": str(row["email"]),
                "specialities": list(row["specialities"] or []),
                "max_juries": int(row["max_juries"]),
                "domain_id": int(row["domain_id"]),
                "domain_name": str(row["domain_name"] or ""),
            }
            for row in professor_rows
        ],
        "projects": projects,
        "sessions": sessions,
        "unavailabilities": [
            {
                "professor_id": int(row["professor_id"]),
                "date": _iso(row["date"]),
                "period": str(row["period"]),
            }
            for row in unavailability_rows
        ],
        "conflicts": [
            {
                "professor_a": int(row["professor_a"]),
                "professor_b": int(row["professor_b"]),
            }
            for row in conflict_rows
        ],
        "constraint_rules": rules,
        "default_weights": {
            "workload": 10,
            "expertise": 5,
            "clustering": 3,
            "overload": 20,
            "custom": int(weights["custom"]),
        },
    }
