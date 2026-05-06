import datetime as dt

from pydantic import BaseModel

from app.schemas.base import ORMBase


class SessionBase(BaseModel):
    status: str
    start_date: dt.date
    end_date: dt.date


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    status: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class SessionOut(SessionBase, ORMBase):
    id: int


class SlotBase(BaseModel):
    date: dt.date
    period: str
    slot_number: int
    room: str
    session_id: int


class SlotCreate(SlotBase):
    pass


class SlotUpdate(BaseModel):
    date: dt.date | None = None
    period: str | None = None
    slot_number: int | None = None
    room: str | None = None
    session_id: int | None = None


class SlotOut(SlotBase, ORMBase):
    id: int


class ProjectBase(BaseModel):
    title: str
    domain_id: int
    supervisor_id: int
    student_id: int


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: str | None = None
    domain_id: int | None = None
    supervisor_id: int | None = None
    student_id: int | None = None


class ProjectOut(ProjectBase, ORMBase):
    id: int


class AssignmentBase(BaseModel):
    examiner_id: int
    project_id: int
    president_id: int
    slot_id: int


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentUpdate(BaseModel):
    examiner_id: int | None = None
    project_id: int | None = None
    president_id: int | None = None
    slot_id: int | None = None


class AssignmentOut(AssignmentBase, ORMBase):
    id: int
