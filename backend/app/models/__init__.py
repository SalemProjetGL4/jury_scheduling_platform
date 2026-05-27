from app.models.academic import Department, DepartmentDomain, Domain, Filiere
from app.models.people import Professor, ProfessorDomain, Student
from app.models.rules import Conflict, ConstraintRule, Unavailability
from app.models.scheduling import Assignment, Project, Room, Session, Slot

__all__ = [
    "Assignment",
    "Conflict",
    "ConstraintRule",
    "Department",
    "DepartmentDomain",
    "Domain",
    "Filiere",
    "Professor",
    "ProfessorDomain",
    "Project",
    "Room",
    "Session",
    "Slot",
    "Student",
    "Unavailability",
]
