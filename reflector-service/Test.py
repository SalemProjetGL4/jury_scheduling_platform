import requests
import json

BASE_URL = "http://localhost:8000/reflect"

base_context = {
    "strategic_intent": {
        "penalty_threshold": 5.0,
        "protected_constraints": [
            "conflict_of_interest",
            "role_uniqueness"
        ],
        "flexible_constraints": [
            "half_day_exclusivity",
            "supervisor_binding",
            "professor_unavailable"
        ]
    },
    "iteration_state": {
        "retry_count": 0,
        "previously_relaxed": [],
        "max_retries": 3
    }
}

# ─────────────────────────────────────────────
# TEST 1 — OPTIMAL (zero violations, zero penalty)
# Expected: status=OPTIMAL, recommended_solution_index=1, empty compromised_solutions
# ─────────────────────────────────────────────
solver_output_optimal = {
    "status": "OPTIMAL",
    "quality_status": "SOFT_OPTIMAL",
    "assignments": [
        {
            "project_id": 200,
            "project_title": "Autonomous Vehicle Path Planning",
            "session_id": 5000,
            "date": "2026-09-01",
            "period": "morning",
            "roles": {
                "supervisor": {"id": 1, "name": "Prof. Dubois"},
                "president": {"id": 2, "name": "Prof. Mansouri"},
                "examiner": {"id": 3, "name": "Prof. Chen"}
            }
        }
    ],
    "solutions": [
        {
            "solution_index": 1,
            "status": "SOFT_OPTIMAL",
            "raw_status": "OPTIMAL",
            "objective_value": 0,
            "assignments": [
                {
                    "project_id": 200,
                    "project_title": "Autonomous Vehicle Path Planning",
                    "session_id": 5000,
                    "date": "2026-09-01",
                    "period": "morning",
                    "roles": {
                        "supervisor": {"id": 1, "name": "Prof. Dubois"},
                        "president": {"id": 2, "name": "Prof. Mansouri"},
                        "examiner": {"id": 3, "name": "Prof. Chen"}
                    }
                }
            ],
            "unsatisfied_soft_constraints": [],
            "objective_delta_from_best": 0
        }
    ],
    "solution_count": 1,
    "solutions_limit_reached": False,
    "unsatisfied_soft_constraints": []
}

# ─────────────────────────────────────────────
# TEST 2 — INFEASIBLE: Supervisor Binding Impossible
# Prof. Martin is the declared supervisor of project 201
# but is unavailable on the only valid session date.
# Expected: status=INFEASIBLE, 2 relaxation options,
#           Option A = relax professor_unavailable (LOW-MEDIUM loss)
#           Option B = relax supervisor_binding (MEDIUM loss)
# ─────────────────────────────────────────────
solver_output_infeasible_supervisor = {
    "status": "INFEASIBLE",
    "failed_constraints": [
        {
            "constraint": "supervisor_binding",
            "reason": "Declared supervisor is unavailable in the only valid session for this project",
            "details": {
                "project_id": 201,
                "project_title": "Deep Learning for Medical Imaging",
                "supervisor_id": 7,
                "supervisor_name": "Prof. Martin",
                "session_id": 5001,
                "session_date": "2026-09-02",
                "session_period": "morning"
            }
        },
        {
            "constraint": "professor_unavailable",
            "reason": "Professor declared a personal hard unavailability for this slot",
            "details": {
                "professor_id": 7,
                "professor_name": "Prof. Martin",
                "date": "2026-09-02",
                "period": "morning",
                "unavailability_type": "personal_hard_constraint"
            }
        }
    ],
    "trace": (
        "Project 201 ('Deep Learning for Medical Imaging') requires Prof. Martin as supervisor "
        "via supervisor_binding constraint. Prof. Martin has declared personal unavailability "
        "on 2026-09-02 morning. No alternative session exists for project 201. "
        "Both constraints cannot be satisfied simultaneously — system is overconstrained."
    )
}

# ─────────────────────────────────────────────
# TEST 3 — INFEASIBLE: Conflict Chain Deadlock
# Prof. Benali and Prof. Torres declared a conflict of interest.
# Prof. Benali is the only available PRESIDENT for project 202.
# Prof. Torres is the declared SUPERVISOR of project 202.
# No valid third examiner exists who isn't also in conflict with one of them.
# Expected: status=INFEASIBLE, options involve relaxing conflict_of_interest
#           (HIGH loss — must escalate to human, no autonomous relaxation)
# ─────────────────────────────────────────────
solver_output_infeasible_conflict = {
    "status": "INFEASIBLE",
    "failed_constraints": [
        {
            "constraint": "conflict_of_interest",
            "reason": "All valid professor combinations for this jury include a conflicting pair",
            "details": {
                "project_id": 202,
                "project_title": "Quantum Computing Optimization",
                "conflict_pairs": [
                    {
                        "professor_a_id": 8,
                        "professor_a_name": "Prof. Benali",
                        "professor_b_id": 9,
                        "professor_b_name": "Prof. Torres",
                        "conflict_reason": "Co-authored disputed paper — professional conflict declared"
                    }
                ]
            }
        },
        {
            "constraint": "supervisor_binding",
            "reason": "Prof. Torres is the declared supervisor and cannot be replaced without relaxation",
            "details": {
                "project_id": 202,
                "project_title": "Quantum Computing Optimization",
                "supervisor_id": 9,
                "supervisor_name": "Prof. Torres",
                "session_id": 5002,
                "session_date": "2026-09-03",
                "session_period": "afternoon"
            }
        },
        {
            "constraint": "role_unique_per_project",
            "reason": "No valid PRESIDENT can be assigned without including Prof. Benali, who conflicts with Prof. Torres",
            "details": {
                "project_id": 202,
                "role": "PRESIDENT",
                "available_professors": [
                    {"id": 8, "name": "Prof. Benali"}
                ]
            }
        }
    ],
    "trace": (
        "Project 202 ('Quantum Computing Optimization') has Prof. Torres as declared supervisor (supervisor_binding). "
        "Prof. Benali is the only professor available and qualified for the PRESIDENT role in session 5002. "
        "Prof. Benali and Prof. Torres have a declared conflict of interest (professional conflict). "
        "No third examiner is available who is not also in conflict with one of them. "
        "All valid jury combinations are blocked — conflict chain deadlock."
    )
}

# ─────────────────────────────────────────────
# TEST 4 — INFEASIBLE: Single Professor Overloaded
# Prof. Karim is declared supervisor for 3 projects,
# all scheduled in sessions that span both morning and afternoon
# on the same day, violating half_day_exclusivity.
# Expected: status=INFEASIBLE,
#           Option A = relax half_day_exclusivity for Prof. Karim on 2026-09-04 (LOW loss)
#           Option B = relax supervisor_binding for the least critical of the 3 projects (MEDIUM loss)
# ─────────────────────────────────────────────
solver_output_infeasible_overloaded = {
    "status": "INFEASIBLE",
    "failed_constraints": [
        {
            "constraint": "half_day_exclusivity",
            "reason": "Professor is required as supervisor in both morning and afternoon sessions on the same day",
            "details": {
                "professor_id": 5,
                "professor_name": "Prof. Karim",
                "date": "2026-09-04",
                "morning_sessions": [
                    {"session_id": 5003, "project_id": 203, "project_title": "NLP Sentiment Analysis"}
                ],
                "afternoon_sessions": [
                    {"session_id": 5004, "project_id": 204, "project_title": "Federated Learning Privacy"},
                    {"session_id": 5005, "project_id": 205, "project_title": "Graph Neural Networks"}
                ]
            }
        },
        {
            "constraint": "supervisor_binding",
            "reason": "Prof. Karim is declared supervisor for all 3 projects and cannot be substituted without relaxation",
            "details": {
                "professor_id": 5,
                "professor_name": "Prof. Karim",
                "supervised_projects": [
                    {"project_id": 203, "project_title": "NLP Sentiment Analysis", "session_id": 5003},
                    {"project_id": 204, "project_title": "Federated Learning Privacy", "session_id": 5004},
                    {"project_id": 205, "project_title": "Graph Neural Networks", "session_id": 5005}
                ]
            }
        }
    ],
    "trace": (
        "Prof. Karim is the declared supervisor for projects 203, 204, and 205. "
        "Projects 203 is scheduled in the morning (session 5003) and projects 204, 205 in the afternoon "
        "(sessions 5004, 5005) on 2026-09-04. "
        "The half_day_exclusivity constraint prevents Prof. Karim from working both periods on the same day. "
        "supervisor_binding prevents substitution without explicit relaxation. "
        "The three constraints together make the schedule impossible."
    )
}

# ─────────────────────────────────────────────
# TEST 5 — INFEASIBLE: Retry exhausted
# Same supervisor binding case as test 2,
# but retry_count is already at max_retries.
# Expected: retries_exhausted=true, only human-approval options,
#           no autonomous relaxation suggested
# ─────────────────────────────────────────────
solver_output_infeasible_exhausted = {**solver_output_infeasible_supervisor}

context_exhausted = {
    "strategic_intent": {
        "penalty_threshold": 5.0,
        "protected_constraints": ["conflict_of_interest", "role_uniqueness"],
        "flexible_constraints": ["half_day_exclusivity", "supervisor_binding", "professor_unavailable"]
    },
    "iteration_state": {
        "retry_count": 3,
        "previously_relaxed": ["professor_unavailable", "half_day_exclusivity"],
        "max_retries": 3
    }
}

# ─────────────────────────────────────────────
# TEST 6 — COMPROMISED: Multi-solution ranking
# Expected: status=COMPROMISED, solutions ranked by human_cost_hierarchy,
#           solutions 1 & 2 rated highest (no violations),
#           solution 5 rated lowest (prefer_professor_role tier-6 violation)
# ─────────────────────────────────────────────
solver_output_compromised = {
    "status": "OPTIMAL",
    "quality_status": "SOFT_COMPROMISED",
    "solutions": [
        {
            "solution_index": 1,
            "status": "SOFT_OPTIMAL",
            "raw_status": "OPTIMAL",
            "objective_value": 9800,
            "unsatisfied_soft_constraints": []
        },
        {
            "solution_index": 2,
            "status": "SOFT_OPTIMAL",
            "raw_status": "OPTIMAL",
            "objective_value": 9800,
            "unsatisfied_soft_constraints": []
        },
        {
            "solution_index": 3,
            "status": "SOFT_COMPROMISED",
            "raw_status": "OPTIMAL",
            "objective_value": 10300,
            "unsatisfied_soft_constraints": [
                {
                    "rule": "avoid_professor_session",
                    "payload": {"professor_id": 3, "professor_name": "Prof. Chen", "session_id": 4001},
                    "weight": 1.0,
                    "penalty_weighted": 1.0
                }
            ]
        },
        {
            "solution_index": 4,
            "status": "SOFT_COMPROMISED",
            "raw_status": "OPTIMAL",
            "objective_value": 10300,
            "unsatisfied_soft_constraints": [
                {
                    "rule": "avoid_professor_session",
                    "payload": {"professor_id": 3, "professor_name": "Prof. Chen", "session_id": 4001},
                    "weight": 1.0,
                    "penalty_weighted": 1.0
                }
            ]
        },
        {
            "solution_index": 5,
            "status": "SOFT_COMPROMISED",
            "raw_status": "OPTIMAL",
            "objective_value": 10800,
            "unsatisfied_soft_constraints": [
                {
                    "rule": "prefer_professor_role",
                    "payload": {"professor_id": 4, "professor_name": "Prof. Nguyen", "project_id": 101, "project_title": "Computer Vision Tracking", "role": "PRESIDENT"},
                    "weight": 2.0,
                    "penalty_weighted": 2.0
                }
            ]
        }
    ],
    "solution_count": 5,
    "solutions_limit_reached": True
}


def test_reflector(test_name, solver_result, custom_context=None):
    context = custom_context if custom_context else base_context
    payload = {
        "request_id": test_name,
        "solver_result": solver_result,
        "solver_payload": {},
        "db_snapshot": {},
        **context
    }

    response = requests.post(BASE_URL, json=payload)

    print(f"\n{'='*60}")
    print(f"Test: {test_name}")
    print(f"Status Code: {response.status_code}")
    print("Response:")
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)
    print(f"{'='*60}")


if __name__ == "__main__":
    test_reflector("test-optimal", solver_output_optimal)
    test_reflector("test-infeasible-supervisor-binding", solver_output_infeasible_supervisor)
    test_reflector("test-infeasible-conflict-chain", solver_output_infeasible_conflict)
    test_reflector("test-infeasible-overloaded-professor", solver_output_infeasible_overloaded)
    test_reflector("test-infeasible-retries-exhausted", solver_output_infeasible_exhausted, custom_context=context_exhausted)
    test_reflector("test-compromised-multi-solution", solver_output_compromised)