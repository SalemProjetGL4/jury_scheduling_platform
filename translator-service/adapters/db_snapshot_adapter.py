from __future__ import annotations

import datetime
import json
import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal
import re
from typing import Any

from sqlalchemy import create_engine, text

from adapters.llm_provider_adapter import get_provider
from contracts.orchestrator_output import extract_json_object
from config import settings


logger = logging.getLogger("translator")


def _iso(value: Any) -> str | Any:
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _decimal_to_float(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def build_db_snapshot(session_id: int | None = None) -> dict[str, Any]:
    engine = create_engine(settings.database_url, future=True)

    with engine.connect() as conn:
        professor_rows = conn.execute(
            text(
                """
                SELECT
                    p.id,
                    p.name,
                    p.email,
                    p.preferences,
                    p.max_juries,
                    COALESCE(
                        ARRAY_AGG(DISTINCT pd.domain_id) FILTER (WHERE pd.domain_id IS NOT NULL),
                        ARRAY[]::bigint[]
                    ) AS domain_ids,
                    MIN(pd.domain_id) AS domain_id,
                    COALESCE(
                        ARRAY_AGG(DISTINCT d.name) FILTER (WHERE d.name IS NOT NULL),
                        ARRAY[]::text[]
                    ) AS domain_names
                FROM professor p
                LEFT JOIN professor_domain pd ON pd.professor_id = p.id
                LEFT JOIN domain d ON d.id = pd.domain_id
                GROUP BY p.id, p.name, p.email, p.preferences, p.max_juries
                ORDER BY p.id
                """
            )
        ).mappings().all()

        if session_id is not None:
            project_rows = conn.execute(
                text(
                    """
                      SELECT pr.id, pr.title, pr.domain_id AS domain_id, d.name AS domain_name,
                           pr.supervisor_id, pr.student_id, st.name AS student_name
                    FROM project pr
                      LEFT JOIN domain d ON d.id = pr.domain_id
                    LEFT JOIN student st ON st.id = pr.student_id
                    WHERE pr.session_id = :session_id
                    ORDER BY pr.id
                    """
                ),
                {"session_id": session_id},
            ).mappings().all()
        else:
                        raise ValueError("session_id is required for snapshot building")

        if session_id is not None:
            slot_rows = conn.execute(
                text(
                    """
                    SELECT s.id, s.session_id, s.start_time, s.end_time, s.slot_number, r.name AS room
                    FROM slot s
                    JOIN room r ON r.id = s.room_id
                    WHERE s.session_id = :session_id
                    ORDER BY s.id
                    """
                ),
                {"session_id": session_id},
            ).mappings().all()
        else:
            raise ValueError("session_id is required for snapshot building")

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
            "date": _iso(row["start_time"].date()) if row["start_time"] else None,
            "period": "morning" if row["start_time"] and row["start_time"].hour < 12 else "afternoon",
            "start_time": _iso(row["start_time"]),
            "end_time": _iso(row["end_time"]),
            "slot_number": int(row["slot_number"]),
            "room": str(row["room"]),
        }
        for row in slot_rows
    ]

    project_keywords_by_id = _extract_project_keywords(project_rows)
    projects: list[dict[str, Any]] = []
    for row in project_rows:
        title = str(row["title"] or "")
        domain_name = str(row["domain_name"] or "")
        project_id = int(row["id"])
        keywords = _merge_keywords(
            _extract_domain_keywords(domain_name),
            project_keywords_by_id.get(project_id, _extract_title_keywords(title)),
        )
        logger.info(
            "PROJECT KEYWORDS — id=%s domain_id=%s title=%r keywords=%s",
            project_id,
            int(row["domain_id"]),
            title,
            keywords,
        )
        projects.append(
            {
                "id": project_id,
                "title": title,
                "domain_id": int(row["domain_id"]),
                "domain_name": domain_name,
                "domain_keywords": keywords,
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
                "specialities": list(row["preferences"] or []),
                "max_juries": int(row["max_juries"]),
                "domain_ids": [int(value) for value in (row["domain_ids"] or [])],
                "domain_id": int(row["domain_id"] or 0),
                "domain_name": (list(row["domain_names"] or [""])[0] if list(row["domain_names"] or []) else ""),
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
            "expertise": 15,
            "clustering": 3,
            "overload": 20,
            "custom": int(weights["custom"]),
        },
    }


_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "de",
    "des",
    "du",
    "d",
    "en",
    "et",
    "for",
    "from",
    "in",
    "into",
    "le",
    "les",
    "of",
    "on",
    "or",
    "pour",
    "the",
    "to",
    "un",
    "une",
    "using",
    "via",
    "with",
    "based",
    "building",
    "conception",
    "creation",
    "develop",
    "developing",
    "development",
    "design",
    "enhanced",
    "improvement",
    "implementation",
    "improve",
    "integrating",
    "integration",
    "migration",
    "migration",
    "optimization",
    "optimisation",
    "platform",
    "project",
    "solution",
    "solutions",
    "system",
    "systems",
}


def _extract_title_keywords(title: str) -> list[str]:
    tokens = re.findall(r"[\w]+", title.lower(), flags=re.UNICODE)
    keywords: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        normalized = token.strip("_-'")
        if len(normalized) < 2:
            continue
        if normalized in _TITLE_STOPWORDS:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(normalized)

    return keywords


def _extract_domain_keywords(domain_name: str) -> list[str]:
    tokens = re.findall(r"[\w]+", domain_name.lower(), flags=re.UNICODE)
    keywords: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        normalized = token.strip("_-'")
        if len(normalized) < 2:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(normalized)

    return keywords


def _extract_project_keywords(project_rows: list[dict[str, Any]]) -> dict[int, list[str]]:
    fallback_keywords = {
        int(row["id"]): _extract_title_keywords(str(row["title"] or ""))
        for row in project_rows
    }

    llm_keywords = _extract_project_keywords_with_llm(project_rows)
    if not llm_keywords:
        return {
            int(row["id"]): _generalize_keywords(fallback_keywords.get(int(row["id"]), []))
            for row in project_rows
        }

    merged_keywords: dict[int, list[str]] = {}
    for row in project_rows:
        project_id = int(row["id"])
        merged_keywords[project_id] = _generalize_keywords(
            _merge_keywords(
                llm_keywords.get(project_id, []),
                fallback_keywords.get(project_id, []),
            )
        )

    return merged_keywords


def _extract_project_keywords_with_llm(project_rows: list[dict[str, Any]]) -> dict[int, list[str]]:
    try:
        provider = get_provider()
    except Exception:
        return {}

    payload = [
        {
            "id": int(row["id"]),
            "title": str(row["title"] or ""),
            "domain_id": int(row["domain_id"]),
            "domain_name": str(row["domain_name"] or ""),
        }
        for row in project_rows
    ]

    system_prompt = (
        "You extract concise general technical keywords from project titles. "
        "Return strict JSON only in this exact shape: "
        '{"keywords_by_project_id": {"1": ["keyword1", "keyword2"]}}. '
        "Use 2 to 4 lowercase keywords per project. Prefer broad themes such as ai, cloud, devops, data, security, web, mobile, infrastructure, blockchain, health, and finance. "
        "Avoid long phrases, avoid too many keywords, and avoid generic words like project, platform, system, development, implementation, solution, and using. "
        "The domain_id/domain_name are only context for disambiguation, not the main source."
    )
    user_message = json.dumps({"projects": payload}, ensure_ascii=False)

    try:
        raw_output = provider.complete(system_prompt=system_prompt, user_message=user_message)
        candidate = json.loads(extract_json_object(raw_output))
    except Exception:
        return {}

    raw_mapping = candidate.get("keywords_by_project_id")
    if not isinstance(raw_mapping, dict):
        return {}

    extracted: dict[int, list[str]] = {}
    for project_id_raw, keywords in raw_mapping.items():
        try:
            project_id = int(project_id_raw)
        except (TypeError, ValueError):
            continue

        extracted[project_id] = _normalize_keyword_list(keywords)

    return extracted


def _merge_keywords(primary: list[str], fallback: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for keyword in list(primary) + list(fallback):
        normalized = str(keyword).strip().lower()
        if len(normalized) < 2:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)

    return merged


def _normalize_keyword_list(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []

    return _merge_keywords(values, [])


def _generalize_keywords(keywords: list[str], *, limit: int = 4) -> list[str]:
    generalized: list[str] = []

    for keyword in keywords:
        bucket = _keyword_bucket(keyword)
        if bucket is None or bucket in generalized:
            continue
        generalized.append(bucket)
        if len(generalized) >= limit:
            return generalized

    if generalized:
        return generalized

    fallback: list[str] = []
    for keyword in keywords:
        normalized = str(keyword).strip().lower()
        if len(normalized) < 2 or normalized in fallback:
            continue
        fallback.append(normalized)
        if len(fallback) >= limit:
            break

    return fallback


def _keyword_bucket(keyword: str) -> str | None:
    normalized = str(keyword).strip().lower()
    if not normalized:
        return None

    bucket_rules = [
        (r"\b(ai|llm|nlp|rag|ml|machine learning|deep learning|computer vision|vision|prediction|model|models)\b", "ai"),
        (r"\b(cloud|aws|azure|gcp|kubernetes|k8s|docker|devops|cicd|ci/cd|openshift|terraform|infra|infrastructure)\b", "cloud"),
        (r"\b(data|etl|pipeline|analytics|streaming|warehouse|lake|bi|datadog|grafana)\b", "data"),
        (r"\b(security|secure|cyber|cybersecurity|vulnerability|vulnerabilities|attack|rootkit|cryptographic|encryption|offensive)\b", "security"),
        (r"\b(web|frontend|front-end|backend|back-end|api|application|app|ui|ux|full-stack|fullstack)\b", "web"),
        (r"\b(mobile|android|ios)\b", "mobile"),
        (r"\b(iot|embedded|edge|fog|network|networks|telecom|telecommunications|container|containers)\b", "infrastructure"),
        (r"\b(blockchain|crypto|cryptography|ledger)\b", "blockchain"),
        (r"\b(health|healthcare|medical|clinical|genetics|bio|biology|histopathological)\b", "health"),
        (r"\b(finance|financial|bank|insurance|risk|transaction|transactions|accounting)\b", "finance"),
    ]

    for pattern, bucket in bucket_rules:
        if re.search(pattern, normalized):
            return bucket

    return None
