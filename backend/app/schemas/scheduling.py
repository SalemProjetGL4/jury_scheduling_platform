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


# ── Room ──────────────────────────────────────────────────────────────────────

class RoomBase(BaseModel):
    name: str


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: str | None = None


class RoomOut(RoomBase, ORMBase):
    id: int


# ── Slot ──────────────────────────────────────────────────────────────────────

class SlotBase(BaseModel):
    start_time: dt.datetime
    end_time: dt.datetime
    slot_number: int
    room_id: int
    session_id: int


class SlotCreate(SlotBase):
    pass


class SlotUpdate(BaseModel):
    start_time: dt.datetime | None = None
    end_time: dt.datetime | None = None
    slot_number: int | None = None
    room_id: int | None = None
    session_id: int | None = None


class SlotOut(SlotBase, ORMBase):
    id: int
    room: str   # resolved from room_obj.name via the model property


# ── Project ───────────────────────────────────────────────────────────────────

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


# ── Assignment ────────────────────────────────────────────────────────────────

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


class ProjectImportIssue(BaseModel):
    row_number: int
    student: str | None = None
    reason: str


class ProjectImportReport(BaseModel):
    file_name: str
    dry_run: bool
    total_rows: int
    inserted_count: int
    skipped_duplicates: int
    invalid_rows: int
    issues: list[ProjectImportIssue]


# ── Slot generation ───────────────────────────────────────────────────────────

class GenerateSlotsRequest(BaseModel):
    start_date: dt.date
    end_date: dt.date
    room_id: int


class GenerateSlotsResponse(BaseModel):
    session_id: int
    slots_created: int
    days_covered: int
