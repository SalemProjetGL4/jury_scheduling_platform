import datetime as dt
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FiliereBase(BaseModel):
    name: str
    department_id: int


class FiliereCreate(FiliereBase):
    pass


class FiliereUpdate(BaseModel):
    name: str | None = None
    department_id: int | None = None


class FiliereOut(FiliereBase, ORMBase):
    id: int


class DomainBase(BaseModel):
    name: str


class DomainCreate(DomainBase):
    pass


class DomainUpdate(BaseModel):
    name: str | None = None


class DomainOut(DomainBase, ORMBase):
    id: int


class ProfessorBase(BaseModel):
    name: str
    email: EmailStr
    department_id: int
    max_juries: int
    preferences: list[str] | None = None


class ProfessorCreate(ProfessorBase):
    pass


class ProfessorUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    department_id: int | None = None
    max_juries: int | None = None
    preferences: list[str] | None = None


class ProfessorOut(ProfessorBase, ORMBase):
    id: int


class StudentBase(BaseModel):
    name: str
    email: EmailStr
    promotion: dt.date
    filiere_id: int


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    promotion: dt.date | None = None
    filiere_id: int | None = None


class StudentOut(StudentBase, ORMBase):
    id: int


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


class UnavailabilityBase(BaseModel):
    professor_id: int
    date: dt.date
    period: str


class UnavailabilityCreate(UnavailabilityBase):
    pass


class UnavailabilityUpdate(BaseModel):
    professor_id: int | None = None
    date: dt.date | None = None
    period: str | None = None


class UnavailabilityOut(UnavailabilityBase, ORMBase):
    id: int


class ConflictBase(BaseModel):
    professor_a: int
    professor_b: int


class ConflictCreate(ConflictBase):
    pass


class ConflictUpdate(BaseModel):
    professor_a: int | None = None
    professor_b: int | None = None


class ConflictOut(ConflictBase, ORMBase):
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


class ConstraintRuleBase(BaseModel):
    name: str
    type: str
    weight: Decimal
    payload: dict[str, Any]
    enabled: bool = True


class ConstraintRuleCreate(ConstraintRuleBase):
    pass


class ConstraintRuleUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    weight: Decimal | None = None
    payload: dict[str, Any] | None = None
    enabled: bool | None = None


class ConstraintRuleOut(ConstraintRuleBase, ORMBase):
    id: int


class StudentImportIssue(BaseModel):
    row_number: int
    email: str | None = None
    reason: str


class StudentImportReport(BaseModel):
    file_name: str
    dry_run: bool
    total_rows: int
    inserted_count: int
    skipped_duplicates: int
    invalid_rows: int
    issues: list[StudentImportIssue]
