from pydantic import BaseModel

from app.schemas.base import ORMBase


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
