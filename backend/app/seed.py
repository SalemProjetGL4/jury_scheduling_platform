import argparse
import datetime as dt
import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import (
    Assignment,
    Conflict,
    ConstraintRule,
    Department,
    DepartmentDomain,
    Domain,
    Filiere,
    Professor,
    ProfessorDomain,
    Project,
    Room,
    Session as JurySession,
    Slot,
    Student,
    Unavailability,
)

CANONICAL_DOMAINS = [
    "Artificial Intelligence",
    "Machine Learning",
    "Data Science",
    "Data Engineering",
    "Internet of Things",
    "Security",
    "Cloud",
    "DevOps",
    "Web Development",
    "Mobile",
    "Blockchain",
    "Networking",
    "Embedded Systems",
    "Natural Language Processing",
    "Computer Vision",
    "Databases",
    "Human-Computer Interaction",
    "Bioinformatics",
    "Finance",
    "Healthcare",
    "Robotics",
    "Distributed Systems",
    "Software Engineering",
    "Deep Learning",
    "Big Data",
    "MLOps",
    "Edge Computing",
    "Quantum Computing",
    "Computer Graphics",
    "Augmented Reality",
    "Virtual Reality",
    "Game Development",
    "Information Retrieval",
    "Operating Systems",
    "Compilers",
    "Formal Methods",
    "Algorithm Design",
    "Digital Twins",
    "Simulation",
    "Autonomous Systems",
    "FinTech",
]


def create_tables() -> None:
    Base.metadata.create_all(engine)


def clear_all(db: Session) -> None:
    # Delete in reverse dependency order to satisfy FK constraints.
    db.execute(delete(Assignment))
    db.execute(delete(Conflict))
    db.execute(delete(Unavailability))
    db.execute(delete(ProfessorDomain))
    db.execute(delete(DepartmentDomain))
    db.execute(delete(Slot))
    db.execute(delete(Project))
    db.execute(delete(ConstraintRule))
    db.execute(delete(JurySession))
    db.execute(delete(Student))
    db.execute(delete(Professor))
    db.execute(delete(Domain))
    db.execute(delete(Filiere))
    db.execute(delete(Department))


def already_seeded(db: Session) -> bool:
    first_filiere = db.execute(select(Filiere.id).limit(1)).scalar_one_or_none()
    return first_filiere is not None


def seed_canonical_domains(db: Session) -> dict[str, Domain]:
    """Insert canonical domains (idempotent) and return name -> Domain mapping."""
    domains: dict[str, Domain] = {}
    for name in CANONICAL_DOMAINS:
        existing = db.execute(select(Domain).where(Domain.name == name)).scalar_one_or_none()
        if existing:
            domains[name] = existing
        else:
            domain = Domain(name=name)
            db.add(domain)
            db.flush()
            domains[name] = domain
    db.flush()
    return domains


_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _slugify_name(value: str) -> str:
    text = _strip_accents(value).lower()
    text = re.sub(r"[^a-z0-9]+", ".", text).strip(".")
    return text or "user"


def _build_unique_email(name: str, domain: str, used: set[str]) -> str:
    base = _slugify_name(name)
    candidate = f"{base}@{domain}"
    counter = 2
    while candidate in used:
        candidate = f"{base}.{counter}@{domain}"
        counter += 1
    used.add(candidate)
    return candidate


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    numeric = re.search(r"(\d{1,2})[\/-](\d{1,2})[\/-](\d{2,4})", text)
    if numeric:
        day, month, year = (int(numeric.group(1)), int(numeric.group(2)), int(numeric.group(3)))
        if year < 100:
            year += 2000
        try:
            return dt.date(year, month, day)
        except ValueError:
            return None

    normalized = _strip_accents(text.lower())
    text_match = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", normalized)
    if text_match:
        day = int(text_match.group(1))
        month_name = text_match.group(2)
        year = int(text_match.group(3))
        month = _MONTHS.get(month_name)
        if month is None:
            return None
        try:
            return dt.date(year, month, day)
        except ValueError:
            return None
    return None


def _normalize_time(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip().lower().replace("h", ":")
    match = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _time_to_minutes(time_value: str | None) -> int:
    if not time_value:
        return 0
    hour, minute = time_value.split(":")
    return int(hour) * 60 + int(minute)


def _time_to_datetime(
    date: dt.date, time_value: str | None, duration_hours: int = 1
) -> tuple[dt.datetime, dt.datetime]:
    if time_value:
        hour, minute = time_value.split(":")
        start = dt.datetime(date.year, date.month, date.day, int(hour), int(minute))
    else:
        start = dt.datetime(date.year, date.month, date.day, 8, 0)
    end = start + dt.timedelta(hours=duration_hours)
    return start, end


# Permitted jury hours: 08:00–11:59 (morning) and 13:00–16:59 (afternoon).
# Lunch break (12:xx) and outside-hours (<08:00, ≥17:00) are never allowed.
_MORNING_START = 8 * 60    # 08:00 in minutes
_MORNING_END   = 12 * 60   # 12:00 exclusive
_AFTERNOON_START = 13 * 60 # 13:00
_AFTERNOON_END   = 17 * 60 # 17:00 exclusive


def _is_valid_slot(date: dt.date | None, time_value: str | None) -> bool:
    """True only when (date, time) falls inside an allowed jury window:
    - Sunday (weekday 6): never.
    - Saturday (weekday 5): morning window only (08:00–11:59).
    - Monday–Friday: morning OR afternoon window.
    """
    if date is None or time_value is None:
        return False
    weekday = date.weekday()  # 0 = Monday … 6 = Sunday
    if weekday == 6:
        return False
    minutes = _time_to_minutes(time_value)
    in_morning = _MORNING_START <= minutes < _MORNING_END
    in_afternoon = _AFTERNOON_START <= minutes < _AFTERNOON_END
    if weekday == 5:            # Saturday — morning only
        return in_morning
    return in_morning or in_afternoon


def _promotion_from_session(label: str | None) -> dt.date | None:
    if not label:
        return None
    match = re.search(r"\b(20\d{2})\b", label)
    if not match:
        return None
    return dt.date(int(match.group(1)), 1, 1)


def _load_pfe_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"PFE data file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("PFE data JSON must be a list of records")
    return data


def seed_from_pfe_data(
    db: Session,
    records: list[dict[str, Any]],
    student_email_domain: str,
    professor_email_domain: str,
) -> None:
    departments = {}
    filieres = {}

    for record in records:
        dept_code = (record.get("department") or "").strip().upper()
        if not dept_code:
            continue
        if dept_code not in departments:
            department = Department(name=dept_code)
            db.add(department)
            db.flush()
            departments[dept_code] = department

            filiere_name = f"{dept_code}5"
            filiere = Filiere(name=filiere_name, department_id=department.id)
            db.add(filiere)
            db.flush()
            filieres[dept_code] = filiere

    domains: dict[str, Domain] = {}
    for record in records:
        domain_name = (record.get("domain") or "").strip()
        if not domain_name:
            continue
        key = domain_name.lower()
        if key not in domains:
            existing = db.execute(select(Domain).where(Domain.name == domain_name)).scalar_one_or_none()
            if existing:
                domains[key] = existing
            else:
                domain = Domain(name=domain_name)
                db.add(domain)
                db.flush()
                domains[key] = domain
    if "pfe" not in domains:
        existing = db.execute(select(Domain).where(Domain.name == "PFE")).scalar_one_or_none()
        if existing:
            domains["pfe"] = existing
        else:
            domain = Domain(name="PFE")
            db.add(domain)
            db.flush()
            domains["pfe"] = domain

    session_ranges: dict[str, dict[str, dt.date]] = {}
    for record in records:
        session_label = (record.get("session") or "").strip()
        date_value = _parse_date(record.get("date"))
        if not session_label or not date_value:
            continue
        entry = session_ranges.setdefault(session_label, {"min": date_value, "max": date_value})
        entry["min"] = min(entry["min"], date_value)
        entry["max"] = max(entry["max"], date_value)

    sessions = {}
    for label, entry in session_ranges.items():
        session = JurySession(status="planned", start_date=entry["min"], end_date=entry["max"])
        db.add(session)
        db.flush()
        sessions[label] = session

    professor_emails: set[str] = set()
    student_emails: set[str] = set()
    professors = {}
    students = {}
    projects = {}
    slots = {}
    slot_counters: dict[tuple[int, dt.date, str], int] = {}
    room_cache: dict[str, Room] = {}
    department_domain_pairs: set[tuple[int, int]] = set()
    professor_domain_pairs: set[tuple[int, int]] = set()

    def get_or_create_room(name: str) -> Room:
        if name in room_cache:
            return room_cache[name]
        existing = db.execute(select(Room).where(Room.name == name)).scalar_one_or_none()
        if existing:
            room_cache[name] = existing
            return existing
        room = Room(name=name)
        db.add(room)
        db.flush()
        room_cache[name] = room
        return room

    def get_professor(name: str | None, dept_code: str) -> Professor | None:
        if not name:
            return None
        key = name.strip().lower()
        if key in professors:
            return professors[key]
        department = departments.get(dept_code)
        if department is None:
            return None
        email = _build_unique_email(name, professor_email_domain, professor_emails)
        professor = Professor(
            name=name.strip(),
            email=email,
            department_id=department.id,
            max_juries=8,
            preferences=None,
        )
        db.add(professor)
        db.flush()
        professors[key] = professor
        return professor

    normalized_records = []
    for record in records:
        session_label = (record.get("session") or "").strip()
        dept_code = (record.get("department") or "").strip().upper()
        date_value = _parse_date(record.get("date"))
        time_value = _normalize_time(record.get("time"))
        room = (record.get("salle") or "").strip() or "Unknown"
        normalized_records.append(
            {
                "raw": record,
                "session_label": session_label,
                "dept_code": dept_code,
                "date": date_value,
                "time": time_value,
                "room": room,
                "time_order": _time_to_minutes(time_value),
            }
        )

    normalized_records.sort(key=lambda item: (item["date"] or dt.date.min, item["room"], item["time_order"]))

    for item in normalized_records:
        record = item["raw"]
        session_label = item["session_label"]
        dept_code = item["dept_code"]
        session = sessions.get(session_label)
        if not dept_code or dept_code not in filieres or session is None:
            continue

        student_name = (record.get("student_name") or "").strip()
        if not student_name:
            continue

        student_key = student_name.lower()
        if student_key not in students:
            promotion = _promotion_from_session(session_label) or item["date"] or dt.date.today()
            email = _build_unique_email(student_name, student_email_domain, student_emails)
            student = Student(
                name=student_name,
                email=email,
                promotion=promotion,
                filiere_id=filieres[dept_code].id,
            )
            db.add(student)
            db.flush()
            students[student_key] = student
        student = students[student_key]

        supervisor_name = (record.get("insat_supervisor") or "").strip() or None
        examiner_name = (record.get("examiner") or "").strip() or None
        president_name = (record.get("jury_president") or "").strip() or None

        supervisor = get_professor(supervisor_name, dept_code) or get_professor(president_name, dept_code) or get_professor(examiner_name, dept_code)
        examiner = get_professor(examiner_name, dept_code)
        president = get_professor(president_name, dept_code)

        if supervisor is None:
            continue

        domain_name = (record.get("domain") or "").strip()
        domain_key = domain_name.lower() if domain_name else "pfe"
        domain = domains.get(domain_key) or domains.get("pfe")
        if domain is None:
            continue

        department = departments.get(dept_code)
        if department is not None:
            dept_domain_key = (department.id, domain.id)
            if dept_domain_key not in department_domain_pairs:
                db.add(DepartmentDomain(department_id=department.id, domain_id=domain.id))
                department_domain_pairs.add(dept_domain_key)

        project_title = (record.get("project_title") or "").strip()
        if not project_title:
            continue
        project_key = f"{student.id}:{project_title.lower()}"
        if project_key not in projects:
            project = Project(
                title=project_title,
                domain_ids=[domain.id],
                supervisor_id=supervisor.id,
                student_id=student.id,
            )
            db.add(project)
            db.flush()
            projects[project_key] = project
        project = projects[project_key]

        for professor in (supervisor, examiner, president):
            if professor is None:
                continue
            prof_domain_key = (professor.id, domain.id)
            if prof_domain_key not in professor_domain_pairs:
                db.add(ProfessorDomain(professor_id=professor.id, domain_id=domain.id))
                professor_domain_pairs.add(prof_domain_key)

        # Enforce allowed windows: 08:00–12:00 morning / 13:00–17:00 afternoon,
        # no Sunday, no Saturday afternoon.
        if not _is_valid_slot(item["date"], item["time"]):
            continue

        slot_key = (session.id, item["date"], item["room"], item["time"])
        slot = slots.get(slot_key)
        if slot is None:
            counter_key = (session.id, item["date"], item["room"])
            slot_number = slot_counters.get(counter_key, 0) + 1
            slot_counters[counter_key] = slot_number
            start_dt, end_dt = _time_to_datetime(item["date"], item["time"])
            slot = Slot(
                start_time=start_dt,
                end_time=end_dt,
                slot_number=slot_number,
                room_id=get_or_create_room(item["room"]).id,
                session_id=session.id,
            )
            db.add(slot)
            db.flush()
            slots[slot_key] = slot

        if examiner is None or president is None:
            continue

        db.add(
            Assignment(
                examiner_id=examiner.id,
                project_id=project.id,
                president_id=president.id,
                slot_id=slot.id,
            )
        )


def seed(db: Session) -> None:
    dep_cs = Department(name="Computer Science Department")
    dep_ds = Department(name="Data Science Department")
    db.add_all([dep_cs, dep_ds])
    db.flush()

    filiere_cs = Filiere(name="Computer Science", department_id=dep_cs.id)
    filiere_ds = Filiere(name="Data Science", department_id=dep_ds.id)
    db.add_all([filiere_cs, filiere_ds])
    db.flush()

    # Seed all canonical domains and reference the ones used in sample data.
    domains = seed_canonical_domains(db)
    domain_ai = domains["Artificial Intelligence"]
    domain_ml = domains["Machine Learning"]
    domain_ds = domains["Data Science"]

    db.add_all(
        [
            DepartmentDomain(department_id=dep_cs.id, domain_id=domain_ai.id),
            DepartmentDomain(department_id=dep_cs.id, domain_id=domain_ml.id),
            DepartmentDomain(department_id=dep_ds.id, domain_id=domain_ds.id),
        ]
    )

    prof_a = Professor(
        name="Dr. Amina Rami",
        email="amina.rami@example.com",
        department_id=dep_cs.id,
        max_juries=4,
        preferences=["optimization", "scheduling"],
    )
    prof_b = Professor(
        name="Dr. Karim Haddad",
        email="karim.haddad@example.com",
        department_id=dep_ds.id,
        max_juries=3,
        preferences=["machine-learning", "data-mining"],
    )
    prof_c = Professor(
        name="Dr. Salma Idrissi",
        email="salma.idrissi@example.com",
        department_id=dep_cs.id,
        max_juries=5,
        preferences=["software-architecture", "testing"],
    )
    db.add_all([prof_a, prof_b, prof_c])
    db.flush()

    db.add_all(
        [
            ProfessorDomain(professor_id=prof_a.id, domain_id=domain_ai.id),
            ProfessorDomain(professor_id=prof_b.id, domain_id=domain_ds.id),
            ProfessorDomain(professor_id=prof_c.id, domain_id=domain_ml.id),
        ]
    )

    student_a = Student(
        name="Youssef Benali",
        email="youssef.benali@example.com",
        promotion=dt.date(2026, 1, 1),
        filiere_id=filiere_cs.id,
    )
    student_b = Student(
        name="Lina Amrani",
        email="lina.amrani@example.com",
        promotion=dt.date(2026, 1, 1),
        filiere_id=filiere_ds.id,
    )
    db.add_all([student_a, student_b])
    db.flush()

    # June 22 = Monday, June 23 = Tuesday — both valid working days.
    session_1 = JurySession(status="planned", start_date=dt.date(2026, 6, 22), end_date=dt.date(2026, 6, 22))
    session_2 = JurySession(status="planned", start_date=dt.date(2026, 6, 23), end_date=dt.date(2026, 6, 23))
    db.add_all([session_1, session_2])
    db.flush()

    project_a = Project(
        title="Adaptive Jury Scheduling",
        domain_ids=[domain_ai.id],
        supervisor_id=prof_a.id,
        student_id=student_a.id,
    )
    project_b = Project(
        title="Learning Analytics Dashboard",
        domain_ids=[domain_ds.id],
        supervisor_id=prof_b.id,
        student_id=student_b.id,
    )
    db.add_all([project_a, project_b])
    db.flush()

    room_a = Room(name="2B6-4")
    room_b = Room(name="2B6-3")
    db.add_all([room_a, room_b])
    db.flush()

    # Morning 08:00–09:00 on Monday June 22; afternoon 13:00–14:00 on Tuesday June 23.
    slot_1 = Slot(
        start_time=dt.datetime(2026, 6, 22, 8, 0),
        end_time=dt.datetime(2026, 6, 22, 9, 0),
        slot_number=1,
        room_id=room_a.id,
        session_id=session_1.id,
    )
    slot_2 = Slot(
        start_time=dt.datetime(2026, 6, 23, 13, 0),
        end_time=dt.datetime(2026, 6, 23, 14, 0),
        slot_number=1,
        room_id=room_b.id,
        session_id=session_2.id,
    )
    db.add_all([slot_1, slot_2])
    db.flush()

    db.add_all(
        [
            Unavailability(
                professor_id=prof_a.id,
                date=dt.date(2026, 6, 23),   # Tuesday afternoon
                period="afternoon",
            ),
            Unavailability(
                professor_id=prof_b.id,
                date=dt.date(2026, 6, 22),   # Monday morning
                period="morning",
            ),
        ]
    )

    db.add(
        Conflict(
            professor_a=prof_a.id,
            professor_b=prof_b.id,
        )
    )

    db.add_all(
        [
            Assignment(
                examiner_id=prof_b.id,
                project_id=project_a.id,
                president_id=prof_c.id,
                slot_id=slot_1.id,
            ),
            Assignment(
                examiner_id=prof_a.id,
                project_id=project_b.id,
                president_id=prof_c.id,
                slot_id=slot_2.id,
            ),
        ]
    )

    db.add_all(
        [
            ConstraintRule(
                name="No Double Booking",
                type="hard",
                weight=Decimal("1.00"),
                payload={"rule": "no_overlap_for_professor"},
                enabled=True,
            ),
            ConstraintRule(
                name="Preferred Morning Slots",
                type="soft",
                weight=Decimal("0.50"),
                payload={"rule": "prefer_morning"},
                enabled=True,
            ),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create database tables and seed with data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing data before seeding.",
    )
    parser.add_argument(
        "--pfe-data",
        type=Path,
        default=None,
        help="Seed from a PFE planning JSON file (output of extract_pfe.py).",
    )
    parser.add_argument(
        "--email-domain",
        type=str,
        default="insat.tn",
        help="Domain for generated student/professor emails when seeding PFE data.",
    )
    parser.add_argument(
        "--domains-only",
        action="store_true",
        help="Only create tables and seed canonical domains, skip sample data.",
    )
    args = parser.parse_args()

    print("Creating database tables...")
    create_tables()
    print("Tables created (or already exist).")

    with SessionLocal() as db:
        if args.reset:
            clear_all(db)
            db.commit()
            print("Existing data cleared.")

        if args.domains_only:
            seed_canonical_domains(db)
            db.commit()
            print("Canonical domains seeded.")
            return

        if args.pfe_data:
            if not args.reset and already_seeded(db):
                print("Seed skipped: database already contains data. Use --reset to reseed.")
                return
            records = _load_pfe_records(args.pfe_data)
            seed_from_pfe_data(db, records, args.email_domain, "insat.ucar.tn")
            db.commit()
        else:
            if not args.reset and already_seeded(db):
                print("Seed skipped: database already contains data. Use --reset to reseed.")
                return
            seed(db)
            db.commit()

    print("Database seed completed successfully.")


if __name__ == "__main__":
    main()
