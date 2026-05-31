import datetime as dt
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.schemas.rules import ConflictRead

from app.db import get_db
from app import models, schemas
from app.services.professor_import import import_professors
from app.services.project_import import import_projects
from app.services.student_import import import_students


def build_crud_router(
    *,
    model: Any,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    out_schema: type[BaseModel],
    path: str,
    tag: str,
):
    router = APIRouter(prefix=path, tags=[tag])

    @router.post("", response_model=out_schema, status_code=status.HTTP_201_CREATED, name=f"create_{tag}")
    def create_item(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)):
        data = create_schema.model_validate(payload).model_dump()
        obj = model(**data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @router.get("", response_model=list[out_schema], name=f"list_{tag}")
    def list_items(
        skip: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=200),
        db: Session = Depends(get_db),
    ):
        return db.query(model).offset(skip).limit(limit).all()

    @router.get("/{item_id}", response_model=out_schema, name=f"get_{tag}")
    def get_item(item_id: int, db: Session = Depends(get_db)):
        obj = db.query(model).filter(model.id == item_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail=f"{tag} not found")
        return obj

    @router.put("/{item_id}", response_model=out_schema, name=f"update_{tag}")
    def update_item(item_id: int, payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)):
        obj = db.query(model).filter(model.id == item_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail=f"{tag} not found")

        update_data = update_schema.model_validate(payload).model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(obj, field, value)

        db.commit()
        db.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, name=f"delete_{tag}")
    def delete_item(item_id: int, db: Session = Depends(get_db)):
        obj = db.query(model).filter(model.id == item_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail=f"{tag} not found")

        try:
            db.delete(obj)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Impossible de supprimer : ce professeur est lié à des projets ou des affectations existantes."
            )
        return None

    return router


filiere_router = build_crud_router(
    model=models.Filiere,
    create_schema=schemas.FiliereCreate,
    update_schema=schemas.FiliereUpdate,
    out_schema=schemas.FiliereOut,
    path="/filieres",
    tag="filieres",
)

domain_router = build_crud_router(
    model=models.Domain,
    create_schema=schemas.DomainCreate,
    update_schema=schemas.DomainUpdate,
    out_schema=schemas.DomainOut,
    path="/domains",
    tag="domains",
)

professor_router = build_crud_router(
    model=models.Professor,
    create_schema=schemas.ProfessorCreate,
    update_schema=schemas.ProfessorUpdate,
    out_schema=schemas.ProfessorOut,
    path="/professors",
    tag="professors",
)


@professor_router.post(
    "/import",
    response_model=schemas.ProfessorImportReport,
    status_code=status.HTTP_201_CREATED,
    name="import_professors",
)
def import_professors_endpoint(
    file: UploadFile = File(...),
    department_id: int | None = Form(default=None),
    department_name: str | None = Form(default=None),
    default_max_juries: int = Form(default=3),
    dry_run: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    try:
        report = import_professors(
            db=db,
            file_name=file.filename or "professors_upload",
            content=file.file.read(),
            default_department_id=department_id,
            default_department_name=department_name,
            default_max_juries=default_max_juries,
            dry_run=dry_run,
        )
        return schemas.ProfessorImportReport.model_validate(report)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@professor_router.get(
    "/{professor_id}/unavailabilities",
    response_model=list[schemas.UnavailabilityOut],
    name="list_professor_unavailabilities",
)
def list_professor_unavailabilities(professor_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Unavailability)
        .filter(models.Unavailability.professor_id == professor_id)
        .all()
    )


student_router = build_crud_router(
    model=models.Student,
    create_schema=schemas.StudentCreate,
    update_schema=schemas.StudentUpdate,
    out_schema=schemas.StudentOut,
    path="/students",
    tag="students",
)


@student_router.post(
    "/import",
    response_model=schemas.StudentImportReport,
    status_code=status.HTTP_201_CREATED,
    name="import_students",
)
def import_students_endpoint(
    file: UploadFile = File(...),
    promotion: dt.date | None = Form(default=None),
    filiere_id: int | None = Form(default=None),
    filiere_name: str | None = Form(default=None),
    dry_run: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    try:
        report = import_students(
            db=db,
            file_name=file.filename or "students_upload",
            content=file.file.read(),
            default_promotion=promotion,
            default_filiere_id=filiere_id,
            default_filiere_name=filiere_name,
            dry_run=dry_run,
        )
        return schemas.StudentImportReport.model_validate(report)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

session_router = build_crud_router(
    model=models.Session,
    create_schema=schemas.SessionCreate,
    update_schema=schemas.SessionUpdate,
    out_schema=schemas.SessionOut,
    path="/sessions",
    tag="sessions",
)


@session_router.post(
    "/generate-slots",
    response_model=schemas.GenerateSlotsResponse,
    status_code=status.HTTP_201_CREATED,
    name="generate_slots",
)
def generate_slots(
    payload: schemas.GenerateSlotsRequest,
    db: Session = Depends(get_db),
):
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    room = db.query(models.Room).filter(models.Room.id == payload.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    session = models.Session(
        status="planned",
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(session)
    db.flush()

    slots_created = 0
    days_covered = 0
    current = payload.start_date
    while current <= payload.end_date:
        weekday = current.weekday()  # 0=Monday … 6=Sunday
        if weekday == 6:  # skip Sunday
            current += timedelta(days=1)
            continue

        days_covered += 1
        is_saturday = weekday == 5

        for slot_num in range(1, 5):
            start_tm = dt.datetime.combine(current, dt.time(7 + slot_num, 0)) # 8:00 -> 11:00
            end_tm = start_tm + timedelta(hours=1)
            db.add(models.Slot(
                start_time=start_tm,
                end_time=end_tm,
                slot_number=slot_num,
                room_id=payload.room_id,
                session_id=session.id,
            ))
            slots_created += 1

        if not is_saturday:
            for slot_num in range(1, 5):
                start_tm = dt.datetime.combine(current, dt.time(12 + slot_num, 0)) # 13:00 -> 16:00
                end_tm = start_tm + timedelta(hours=1)
                db.add(models.Slot(
                    start_time=start_tm,
                    end_time=end_tm,
                    slot_number=slot_num + 4, # 5 to 8
                    room_id=payload.room_id,
                    session_id=session.id,
                ))
                slots_created += 1

        current += timedelta(days=1)

    db.commit()
    return schemas.GenerateSlotsResponse(
        session_id=session.id,
        slots_created=slots_created,
        days_covered=days_covered,
    )


project_router = build_crud_router(
    model=models.Project,
    create_schema=schemas.ProjectCreate,
    update_schema=schemas.ProjectUpdate,
    out_schema=schemas.ProjectOut,
    path="/projects",
    tag="projects",
)


@project_router.post(
    "/import",
    status_code=status.HTTP_201_CREATED,
    name="import_projects",
)
def import_projects_endpoint(
    file: UploadFile = File(...),
    session_id: int = Form(...),
    dry_run: bool = Form(default=False),
    db: Session = Depends(get_db),
):
    try:
        report = import_projects(
            db=db,
            file_name=file.filename or "projects_upload",
            content=file.file.read(),
            session_id=session_id,
            dry_run=dry_run,
        )
        return report
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

room_router = build_crud_router(
    model=models.Room,
    create_schema=schemas.RoomCreate,
    update_schema=schemas.RoomUpdate,
    out_schema=schemas.RoomOut,
    path="/rooms",
    tag="rooms",
)

slot_router = build_crud_router(
    model=models.Slot,
    create_schema=schemas.SlotCreate,
    update_schema=schemas.SlotUpdate,
    out_schema=schemas.SlotOut,
    path="/slots",
    tag="slots",
)

unavailability_router = build_crud_router(
    model=models.Unavailability,
    create_schema=schemas.UnavailabilityCreate,
    update_schema=schemas.UnavailabilityUpdate,
    out_schema=schemas.UnavailabilityOut,
    path="/unavailabilities",
    tag="unavailabilities",
)

conflict_router = APIRouter(prefix="/conflicts", tags=["conflicts"])


# ── specific routes FIRST (must precede /{item_id}) ───────────────────────────

@conflict_router.get(
    "/resolved",
    response_model=list[ConflictRead],
    name="list_conflicts_resolved",
)
def list_conflicts_resolved(db: Session = Depends(get_db)):
    ProfA = aliased(models.Professor)
    ProfB = aliased(models.Professor)
    rows = (
        db.query(models.Conflict, ProfA.name, ProfB.name)
        .join(ProfA, models.Conflict.professor_a == ProfA.id)
        .join(ProfB, models.Conflict.professor_b == ProfB.id)
        .all()
    )
    return [
        ConflictRead(
            id=conflict.id,
            professor_a=conflict.professor_a,
            professor_b=conflict.professor_b,
            professor_a_name=name_a,
            professor_b_name=name_b,
        )
        for conflict, name_a, name_b in rows
    ]


@conflict_router.post(
    "/safe-create",
    response_model=schemas.ConflictOut,
    status_code=status.HTTP_201_CREATED,
    name="safe_create_conflict",
)
def safe_create_conflict(payload: schemas.ConflictCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Conflict).filter(
        (
            (models.Conflict.professor_a == payload.professor_a) &
            (models.Conflict.professor_b == payload.professor_b)
        ) | (
            (models.Conflict.professor_a == payload.professor_b) &
            (models.Conflict.professor_b == payload.professor_a)
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ce conflit existe déjà")
    obj = models.Conflict(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── generic CRUD routes AFTER the specific ones ───────────────────────────────

@conflict_router.post("", response_model=schemas.ConflictOut, status_code=status.HTTP_201_CREATED, name="create_conflicts")
def create_conflict(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    data = schemas.ConflictCreate.model_validate(payload).model_dump()
    obj = models.Conflict(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@conflict_router.get("", response_model=list[schemas.ConflictOut], name="list_conflicts")
def list_conflicts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return db.query(models.Conflict).offset(skip).limit(limit).all()


@conflict_router.get("/{item_id}", response_model=schemas.ConflictOut, name="get_conflicts")
def get_conflict(item_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.Conflict).filter(models.Conflict.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="conflicts not found")
    return obj


@conflict_router.put("/{item_id}", response_model=schemas.ConflictOut, name="update_conflicts")
def update_conflict(item_id: int, payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    obj = db.query(models.Conflict).filter(models.Conflict.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="conflicts not found")
    update_data = schemas.ConflictUpdate.model_validate(payload).model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@conflict_router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, name="delete_conflicts")
def delete_conflict(item_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.Conflict).filter(models.Conflict.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="conflicts not found")
    try:
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Impossible de supprimer : ce professeur est lié à des projets ou des affectations existantes.",
        )
    return None


assignment_router = build_crud_router(
    model=models.Assignment,
    create_schema=schemas.AssignmentCreate,
    update_schema=schemas.AssignmentUpdate,
    out_schema=schemas.AssignmentOut,
    path="/assignments",
    tag="assignments",
)

constraint_rule_router = build_crud_router(
    model=models.ConstraintRule,
    create_schema=schemas.ConstraintRuleCreate,
    update_schema=schemas.ConstraintRuleUpdate,
    out_schema=schemas.ConstraintRuleOut,
    path="/constraint-rules",
    tag="constraint_rules",
)
