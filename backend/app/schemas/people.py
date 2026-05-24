import datetime as dt

from pydantic import BaseModel, EmailStr

from app.schemas.base import ORMBase


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


class ProfessorImportIssue(BaseModel):
    row_number: int
    email: str | None = None
    reason: str


class ProfessorImportReport(BaseModel):
    file_name: str
    dry_run: bool
    total_rows: int
    inserted_count: int
    updated_count: int
    skipped_duplicates: int
    invalid_rows: int
    issues: list[ProfessorImportIssue]
