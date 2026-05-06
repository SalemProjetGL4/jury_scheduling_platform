from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Department(Base):
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class Filiere(Base):
    __tablename__ = "filiere"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id"), nullable=False)


class Domain(Base):
    __tablename__ = "domain"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class DepartmentDomain(Base):
    __tablename__ = "department_domain"

    department_id: Mapped[int] = mapped_column(ForeignKey("department.id", ondelete="CASCADE"), primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domain.id", ondelete="CASCADE"), primary_key=True)
