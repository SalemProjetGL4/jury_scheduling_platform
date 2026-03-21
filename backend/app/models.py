import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import ARRAY, JSON, Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Professor(Base):
    __tablename__ = "professor"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    specialities: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    max_juries: Mapped[int] = mapped_column(Integer, nullable=False)
    domain_id: Mapped[int] = mapped_column("domain", ForeignKey("domain.id"), nullable=False)


class Filiere(Base):
    __tablename__ = "filiere"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Domain(Base):
    __tablename__ = "domain"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    filiere_id: Mapped[int] = mapped_column(ForeignKey("filiere.id"), nullable=False)


class Student(Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    promotion_year: Mapped[int] = mapped_column(Integer, nullable=False)
    filiere_id: Mapped[int] = mapped_column(ForeignKey("filiere.id"), nullable=False)


class Session(Base):
    __tablename__ = "session"
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'in_progress', 'completed')", name="ck_session_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    domain_id: Mapped[int] = mapped_column("domain", ForeignKey("domain.id"), nullable=False)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("professor.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)


class Slot(Base):
    __tablename__ = "slot"
    __table_args__ = (
        CheckConstraint("period IN ('morning', 'afternoon')", name="ck_slot_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    room: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"), nullable=False)


class Unavailability(Base):
    __tablename__ = "unavailability"
    __table_args__ = (
        CheckConstraint("period IN ('morning', 'afternoon', 'full_day')", name="ck_unavailability_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("professor.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)


class Conflict(Base):
    __tablename__ = "conflict"
    __table_args__ = (
        CheckConstraint("professor_a <> professor_b", name="ck_conflict_professors"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    professor_a: Mapped[int] = mapped_column(ForeignKey("professor.id", ondelete="CASCADE"), nullable=False)
    professor_b: Mapped[int] = mapped_column(ForeignKey("professor.id", ondelete="CASCADE"), nullable=False)


class Assignment(Base):
    __tablename__ = "assignment"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    examiner_id: Mapped[int] = mapped_column(ForeignKey("professor.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    president_id: Mapped[int] = mapped_column(ForeignKey("professor.id"), nullable=False)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slot.id", ondelete="CASCADE"), nullable=False)


class ConstraintRule(Base):
    __tablename__ = "constraint_rule"
    __table_args__ = (
        CheckConstraint("type IN ('hard', 'soft')", name="ck_constraint_rule_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
