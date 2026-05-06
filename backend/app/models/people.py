import datetime as dt

from sqlalchemy import ARRAY, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Professor(Base):
    __tablename__ = "professor"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id"), nullable=False)
    max_juries: Mapped[int] = mapped_column(Integer, nullable=False)
    preferences: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)


class ProfessorDomain(Base):
    __tablename__ = "professor_domain"

    professor_id: Mapped[int] = mapped_column(ForeignKey("professor.id", ondelete="CASCADE"), primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domain.id", ondelete="CASCADE"), primary_key=True)


class Student(Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    promotion: Mapped[dt.date] = mapped_column(Date, nullable=False)
    filiere_id: Mapped[int] = mapped_column(ForeignKey("filiere.id"), nullable=False)
