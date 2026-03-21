from fastapi import FastAPI

from app.routers.crud import (
    assignment_router,
    conflict_router,
    constraint_rule_router,
    domain_router,
    filiere_router,
    professor_router,
    project_router,
    session_router,
    slot_router,
    student_router,
    unavailability_router,
)

app = FastAPI(title="PFA Backend API", version="0.1.0")


@app.get("/health", tags=["health"])
def healthcheck():
    return {"status": "ok"}


app.include_router(filiere_router)
app.include_router(domain_router)
app.include_router(professor_router)
app.include_router(student_router)
app.include_router(session_router)
app.include_router(project_router)
app.include_router(slot_router)
app.include_router(unavailability_router)
app.include_router(conflict_router)
app.include_router(assignment_router)
app.include_router(constraint_rule_router)
