import datetime as dt
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.schemas.base import ORMBase


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
