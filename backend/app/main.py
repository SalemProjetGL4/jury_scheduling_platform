from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
