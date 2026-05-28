import datetime as dt

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Room(Base):
    __tablename__ = "room"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class Session(Base):
    __tablename__ = "session"
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'in_progress', 'completed')", name="ck_session_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)


class Slot(Base):
    __tablename__ = "slot"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    start_time: Mapped[dt.datetime] = mapped_column(nullable=False)
    end_time: Mapped[dt.datetime] = mapped_column(nullable=False)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("room.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("session.id", ondelete="CASCADE"), nullable=False)

    room_obj: Mapped[Room] = relationship("Room", lazy="joined")

    @property
    def room(self) -> str:
        return self.room_obj.name if self.room_obj else ""


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domain.id"), nullable=False)
    supervisor_id: Mapped[int] = mapped_column(ForeignKey("professor.id", ondelete="RESTRICT"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)


class Assignment(Base):
    __tablename__ = "assignment"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    examiner_id: Mapped[int] = mapped_column(ForeignKey("professor.id", ondelete="RESTRICT"), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), nullable=False)
    president_id: Mapped[int] = mapped_column(ForeignKey("professor.id", ondelete="RESTRICT"), nullable=False)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slot.id", ondelete="CASCADE"), nullable=False)
