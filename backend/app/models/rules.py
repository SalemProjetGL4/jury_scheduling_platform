import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


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
