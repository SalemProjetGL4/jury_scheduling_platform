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


def build_db_snapshot() -> dict[str, Any]:
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
                    p.department_id,
                    COALESCE(
                        ARRAY_AGG(DISTINCT d.name) FILTER (WHERE d.name IS NOT NULL),
                        ARRAY[]::text[]
                    ) AS domain_names
                FROM professor p
                LEFT JOIN professor_domain pd ON pd.professor_id = p.id
                LEFT JOIN domain d ON d.id = pd.domain_id
                GROUP BY p.id, p.name, p.email, p.preferences, p.max_juries, p.department_id
                ORDER BY p.id
                """
            )
        ).mappings().all()

        project_rows = conn.execute(
            text(
                """
                SELECT pr.id, pr.title,
                       pr.domain_ids[1] AS domain_id,
                       d.name AS domain_name,
                       pr.supervisor_id, pr.student_id, st.name AS student_name,
                       st.filiere_id AS student_filiere_id,
                       f.department_id AS filiere_department_id,
                       pr.domain_ids,
                       CASE WHEN d.name IS NOT NULL THEN ARRAY[d.name]::text[] ELSE ARRAY[]::text[] END AS domain_names
                FROM project pr
                LEFT JOIN domain d ON d.id = pr.domain_ids[1]
                LEFT JOIN student st ON st.id = pr.student_id
                LEFT JOIN filiere f ON f.id = st.filiere_id
                ORDER BY pr.id
                """
            )
        ).mappings().all()

        slot_rows = conn.execute(
            text(
                """
                SELECT s.id, s.session_id, s.start_time, s.end_time, s.slot_number, r.name AS room
                FROM slot s
                JOIN room r ON r.id = s.room_id
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

        # load canonical domain rows for keyword mapping
        domain_rows = conn.execute(text("SELECT id, name FROM domain ORDER BY id")).mappings().all()

        dept_domain_rows = conn.execute(
            text("SELECT department_id, domain_id FROM department_domain ORDER BY department_id, domain_id")
        ).mappings().all()

    dept_to_domain_ids: dict[int, list[int]] = {}
    for row in dept_domain_rows:
        dept_id = int(row["department_id"])
        dept_to_domain_ids.setdefault(dept_id, []).append(int(row["domain_id"]))

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

    def map_keywords_to_domain_ids(keywords: list[str], domain_rows: list[dict[str, Any]], limit: int = 3) -> list[int]:
        """Map normalized keywords to domain ids using exact, token, bucket and substring heuristics.
        Returns a list of domain ids (deduplicated, preserving order) limited to `limit`.
        """
        if not keywords:
            return []

        # prepare lookups
        name_to_id: dict[str, int] = {str(d["name"]).strip().lower(): int(d["id"]) for d in domain_rows}
        token_map: dict[int, set[str]] = {}
        for d in domain_rows:
            toks = set(re.findall(r"[\w]+", str(d["name"]).lower()))
            token_map[int(d["id"])]=toks

        results: list[int] = []

        for kw in keywords:
            k = str(kw).strip().lower()
            if not k:
                continue

            # 1) exact domain name
            if k in name_to_id:
                did = name_to_id[k]
                if did not in results:
                    results.append(did)
                if len(results) >= limit:
                    break
                continue

            # 2) token/substring match with domain tokens
            for did, toks in token_map.items():
                if k in toks or any(k == t or k in t or t in k for t in toks):
                    if did not in results:
                        results.append(did)
                    if len(results) >= limit:
                        break
            if len(results) >= limit:
                break

            # 3) bucket mapping
            bucket = _keyword_bucket(k)
            if bucket:
                # exact bucket match to domain name
                if bucket in name_to_id:
                    did = name_to_id[bucket]
                    if did not in results:
                        results.append(did)
                # substring match on domain names
                for d in domain_rows:
                    if bucket in str(d["name"]).lower() and int(d["id"]) not in results:
                        results.append(int(d["id"]))
                if len(results) >= limit:
                    break

        return results[:limit]
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
            (int(row["domain_id"]) if row.get("domain_id") is not None else None),
            title,
            keywords,
        )
        # derive domain_ids: prefer DB-provided, then filiere department, then keywords
        raw_domain_ids = list(row.get("domain_ids") or [])
        domain_ids = [int(d) for d in raw_domain_ids if d is not None]
        if not domain_ids:
            filiere_dept_id = int(row.get("filiere_department_id") or 0)
            if filiere_dept_id:
                domain_ids = dept_to_domain_ids.get(filiere_dept_id, [])
        if not domain_ids:
            domain_ids = map_keywords_to_domain_ids(keywords, domain_rows)

        projects.append(
            {
                "id": project_id,
                "title": title,
                "domain_id": int(row["domain_id"] or 0) if row.get("domain_id") is not None else 0,
                "domain_ids": domain_ids,
                "domain_name": domain_name,
                "domain_keywords": keywords,
                "supervisor_id": int(row["supervisor_id"]),
                "student_name": str(row["student_name"] or ""),
                "student_filiere_id": int(row["student_filiere_id"] or 0),
                "filiere_department_id": int(row["filiere_department_id"] or 0),
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
                "max_juries": int(row["max_juries"]),
                "domain_id": int(row["domain_id"] or 0),
                "domain_ids": [int(d) for d in (row.get("domain_ids") or []) if d is not None],
                "department_id": int(row["department_id"] or 0),
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

    try:
        payload = [
            {
                "id": int(row["id"]),
                "title": str(row["title"] or ""),
                "domain_id": int(row["domain_id"] or 0),
                "domain_name": str(row["domain_name"] or ""),
            }
            for row in project_rows
        ]
    except Exception:
        return {}

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
