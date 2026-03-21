import argparse
import datetime as dt
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Assignment,
    Conflict,
    ConstraintRule,
    Domain,
    Filiere,
    Professor,
    Project,
    Session as JurySession,
    Slot,
    Student,
    Unavailability,
)


def clear_all(db: Session) -> None:
    # Delete in reverse dependency order to satisfy FK constraints.
    db.execute(delete(Assignment))
    db.execute(delete(Conflict))
    db.execute(delete(Unavailability))
    db.execute(delete(Slot))
    db.execute(delete(Project))
    db.execute(delete(ConstraintRule))
    db.execute(delete(JurySession))
    db.execute(delete(Student))
    db.execute(delete(Professor))
    db.execute(delete(Domain))
    db.execute(delete(Filiere))


def already_seeded(db: Session) -> bool:
    first_filiere = db.execute(select(Filiere.id).limit(1)).scalar_one_or_none()
    return first_filiere is not None


def seed(db: Session) -> None:
    filiere_cs = Filiere(name="Computer Science")
    filiere_ds = Filiere(name="Data Science")
    db.add_all([filiere_cs, filiere_ds])
    db.flush()

    domain_ai = Domain(name="Artificial Intelligence", filiere_id=filiere_cs.id)
    domain_se = Domain(name="Software Engineering", filiere_id=filiere_cs.id)
    domain_da = Domain(name="Data Analytics", filiere_id=filiere_ds.id)
    db.add_all([domain_ai, domain_se, domain_da])
    db.flush()

    prof_a = Professor(
        name="Dr. Amina Rami",
        email="amina.rami@example.com",
        specialities=["optimization", "scheduling"],
        max_juries=4,
        domain_id=domain_ai.id,
    )
    prof_b = Professor(
        name="Dr. Karim Haddad",
        email="karim.haddad@example.com",
        specialities=["machine-learning", "data-mining"],
        max_juries=3,
        domain_id=domain_da.id,
    )
    prof_c = Professor(
        name="Dr. Salma Idrissi",
        email="salma.idrissi@example.com",
        specialities=["software-architecture", "testing"],
        max_juries=5,
        domain_id=domain_se.id,
    )
    db.add_all([prof_a, prof_b, prof_c])
    db.flush()

    student_a = Student(
        name="Youssef Benali",
        email="youssef.benali@example.com",
        promotion_year=2026,
        filiere_id=filiere_cs.id,
    )
    student_b = Student(
        name="Lina Amrani",
        email="lina.amrani@example.com",
        promotion_year=2026,
        filiere_id=filiere_ds.id,
    )
    db.add_all([student_a, student_b])
    db.flush()

    session_1 = JurySession(status="planned", date=dt.date(2026, 6, 20))
    session_2 = JurySession(status="planned", date=dt.date(2026, 6, 21))
    db.add_all([session_1, session_2])
    db.flush()

    project_a = Project(
        title="Adaptive Jury Scheduling",
        domain_id=domain_ai.id,
        supervisor_id=prof_a.id,
        student_id=student_a.id,
    )
    project_b = Project(
        title="Learning Analytics Dashboard",
        domain_id=domain_da.id,
        supervisor_id=prof_b.id,
        student_id=student_b.id,
    )
    db.add_all([project_a, project_b])
    db.flush()

    slot_1 = Slot(
        date=dt.date(2026, 6, 20),
        period="morning",
        slot_number=1,
        room="A-101",
        session_id=session_1.id,
    )
    slot_2 = Slot(
        date=dt.date(2026, 6, 21),
        period="afternoon",
        slot_number=2,
        room="B-204",
        session_id=session_2.id,
    )
    db.add_all([slot_1, slot_2])
    db.flush()

    db.add_all(
        [
            Unavailability(
                professor_id=prof_a.id,
                date=dt.date(2026, 6, 21),
                period="afternoon",
            ),
            Unavailability(
                professor_id=prof_b.id,
                date=dt.date(2026, 6, 20),
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
    parser = argparse.ArgumentParser(description="Seed database with sample data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing data before seeding.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            clear_all(db)
            db.commit()

        if not args.reset and already_seeded(db):
            print("Seed skipped: database already contains data. Use --reset to reseed.")
            return

        seed(db)
        db.commit()

    print("Database seed completed successfully.")


if __name__ == "__main__":
    main()
