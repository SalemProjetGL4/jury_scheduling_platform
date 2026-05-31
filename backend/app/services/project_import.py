from __future__ import annotations

import csv
from io import BytesIO, StringIO
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.domain_mapping import infer_domain_ids


_COLUMN_ALIASES = {
    "project_title": "title",
    "project": "title",
    "domain": "domain_names",
    "domain_name": "domain_names",
    "domain_names": "domain_names",
    "domains": "domain_names",
    "supervisor": "supervisor_email",
    "supervisor_email": "supervisor_email",
    "professor_email": "supervisor_email",
    "encadrant_email": "supervisor_email",
    "student": "student_email",
    "student_email": "student_email",
}

_REQUIRED_FIELDS = {"title"}


def _normalize_header(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _COLUMN_ALIASES.get(normalized, normalized)


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    text: str
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV file has no header row")

    normalized_headers = [_normalize_header(header) for header in reader.fieldnames]
    rows: list[dict[str, Any]] = []

    for raw_row in reader:
        row: dict[str, Any] = {}
        for source_header, normalized in zip(reader.fieldnames, normalized_headers, strict=False):
            row[normalized] = raw_row.get(source_header)
        rows.append(row)

    return rows


def _parse_xlsx(content: bytes) -> list[dict[str, Any]]:
    workbook = load_workbook(filename=BytesIO(content), read_only=True, data_only=True)
    worksheet = workbook.active

    raw_rows = list(worksheet.iter_rows(values_only=True))
    if not raw_rows:
        raise ValueError("XLSX file is empty")

    first_row = raw_rows[0]
    headers = [
        _normalize_header(str(cell).strip()) if cell is not None else ""
        for cell in first_row
    ]

    if not any(headers):
        raise ValueError("XLSX file header row is empty")

    rows: list[dict[str, Any]] = []
    for values in raw_rows[1:]:
        if values is None:
            continue
        row: dict[str, Any] = {}
        for idx, header in enumerate(headers):
            if not header:
                continue
            value = values[idx] if idx < len(values) else None
            row[header] = value
        if any(v is not None and str(v).strip() != "" for v in row.values()):
            rows.append(row)

    return rows


def _load_rows(file_name: str, content: bytes) -> list[dict[str, Any]]:
    lowered = file_name.lower()
    if lowered.endswith(".csv"):
        return _parse_csv(content)
    if lowered.endswith(".xlsx"):
        return _parse_xlsx(content)
    raise ValueError("Unsupported file format. Upload .csv or .xlsx")


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _to_clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_domain_ids(
    raw_names: str | None,
    raw_ids: str | None,
    domain_name_map: dict[str, int],
    all_domain_ids: set[int],
    default_domain_id: int | None,
) -> tuple[list[int], str | None]:
    """Return (resolved_ids, error_message). Supports comma-separated names/ids."""
    resolved: list[int] = []

    # Parse comma-separated IDs from a domain_id column if present
    if raw_ids:
        for part in str(raw_ids).split(","):
            did = _to_int(part.strip())
            if did is not None:
                resolved.append(did)

    # Parse comma-separated names from domain_name/domain_names column
    if raw_names:
        for part in str(raw_names).split(","):
            name = part.strip().lower()
            if name:
                did = domain_name_map.get(name)
                if did is not None and did not in resolved:
                    resolved.append(did)

    # Fall back to default
    if not resolved and default_domain_id is not None:
        resolved.append(default_domain_id)

    if not resolved:
        return [], "Missing domain_id or domain_name"

    unknown = [d for d in resolved if d not in all_domain_ids]
    if unknown:
        return [], f"Unknown domain id(s): {unknown}"

    return resolved, None


def import_projects(
    *,
    db: Session,
    file_name: str,
    content: bytes,
    default_domain_id: int | None,
    default_supervisor_id: int | None,
    dry_run: bool,
) -> dict[str, Any]:
    rows = _load_rows(file_name=file_name, content=content)

    if not rows:
        raise ValueError("Uploaded file has no project rows")

    missing_required = [field for field in _REQUIRED_FIELDS if all(field not in row for row in rows)]
    if missing_required:
        raise ValueError(f"Missing required column(s): {', '.join(sorted(missing_required))}")

    domains = db.execute(select(models.Domain)).scalars().all()
    all_domain_ids = {domain.id for domain in domains}
    domain_name_map = {domain.name.strip().lower(): domain.id for domain in domains}

    professors = db.execute(select(models.Professor)).scalars().all()
    supervisor_ids = {prof.id for prof in professors}
    supervisor_email_map = {prof.email.strip().lower(): prof.id for prof in professors if prof.email}

    students = db.execute(select(models.Student)).scalars().all()
    student_ids = {student.id for student in students}
    student_email_map = {student.email.strip().lower(): student.id for student in students if student.email}

    existing_student_ids = set(db.execute(select(models.Project.student_id)).scalars().all())
    imported_student_ids: set[int] = set()

    issues: list[dict[str, Any]] = []
    projects_to_insert: list[models.Project] = []
    skipped_duplicates = 0

    for idx, row in enumerate(rows, start=2):
        title = _to_clean_str(row.get("title"))
        student_ref = _to_clean_str(row.get("student_email"))

        if not title:
            issues.append({"row_number": idx, "student": student_ref, "reason": "Missing title"})
            continue

        resolved_domain_ids, domain_err = _resolve_domain_ids(
            raw_names=_to_clean_str(row.get("domain_names")),
            raw_ids=_to_clean_str(row.get("domain_id")),
            domain_name_map=domain_name_map,
            all_domain_ids=all_domain_ids,
            default_domain_id=default_domain_id,
        )
        if domain_err:
            # Fall back to auto-mapping from the project title
            resolved_domain_ids = infer_domain_ids(title, db)

        supervisor_id = _to_int(row.get("supervisor_id"))
        supervisor_email = _to_clean_str(row.get("supervisor_email"))
        if supervisor_id is None and supervisor_email:
            supervisor_id = supervisor_email_map.get(supervisor_email.lower())
        if supervisor_id is None and default_supervisor_id is not None:
            supervisor_id = default_supervisor_id
        if supervisor_id is None:
            issues.append(
                {
                    "row_number": idx,
                    "student": student_ref,
                    "reason": "Missing supervisor_id or supervisor_email",
                }
            )
            continue
        if supervisor_id not in supervisor_ids:
            issues.append(
                {
                    "row_number": idx,
                    "student": student_ref,
                    "reason": f"Unknown supervisor_id: {supervisor_id}",
                }
            )
            continue

        student_id = _to_int(row.get("student_id"))
        if student_id is None and student_ref:
            student_id = student_email_map.get(student_ref.lower())
        if student_id is None:
            issues.append(
                {
                    "row_number": idx,
                    "student": student_ref,
                    "reason": "Missing student_id or student_email",
                }
            )
            continue
        if student_id not in student_ids:
            issues.append(
                {
                    "row_number": idx,
                    "student": student_ref or str(student_id),
                    "reason": f"Unknown student_id: {student_id}",
                }
            )
            continue

        if student_id in existing_student_ids or student_id in imported_student_ids:
            skipped_duplicates += 1
            continue

        imported_student_ids.add(student_id)
        projects_to_insert.append(
            models.Project(
                title=title,
                domain_ids=resolved_domain_ids,
                supervisor_id=supervisor_id,
                student_id=student_id,
            )
        )

    if not dry_run and projects_to_insert:
        db.add_all(projects_to_insert)
        db.commit()

    return {
        "file_name": file_name,
        "dry_run": dry_run,
        "total_rows": len(rows),
        "inserted_count": len(projects_to_insert),
        "skipped_duplicates": skipped_duplicates,
        "invalid_rows": len(issues),
        "issues": issues,
    }
