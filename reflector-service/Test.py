import requests
import json

# Test Case 1: OPTIMAL feasible case
solver_output_optimal = {
    "status": "OPTIMAL",
    "quality_status": "SOFT_OPTIMAL",
    "assignments": [
        {
            "project_id": 200,
            "session_id": 5000,
            "date": "2026-09-01",
            "period": "morning",
            "roles": {
                "supervisor": 1,
                "president": 2,
                "examiner": 3
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
                    "session_id": 5000,
                    "date": "2026-09-01",
                    "period": "morning",
                    "roles": {
                        "supervisor": 1,
                        "president": 2,
                        "examiner": 3
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

# Test Case 2: INFEASIBLE case
solver_output_infeasible = {
    "status": "INFEASIBLE",
    "failed_constraints": [
        {
            "constraint": "project_scheduled_once",
            "reason": "Project must be scheduled in exactly one session",
            "details": {"project_id": 201}
        },
        {
            "constraint": "role_unique_per_project",
            "reason": "Each project must have exactly one professor for the role",
            "details": {"project_id": 201, "role": "SUPERVISOR"}
        },
        {
            "constraint": "role_session_link",
            "reason": "Role assignments must match the session where the project is scheduled",
            "details": {"project_id": 201, "role": "SUPERVISOR", "session_id": 5001}
        }
    ]
}

def test_reflector(request_id, solver_result):
    response = requests.post(
        "http://localhost:8000/reflect",
        json={
            "request_id": request_id,
            "solver_result": solver_result,
            "solver_payload": {},
            "db_snapshot": {}
        }
    )
    print(f"\n{'='*60}")
    print(f"Test: {request_id}")
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    print(f"{'='*60}")

# Run both tests
test_reflector("test-optimal", solver_output_optimal)
test_reflector("test-infeasible", solver_output_infeasible)

# Test Case 3: Multi-solution scoring demonstration
solver_output_multi = {
    "status": "OPTIMAL",
    "quality_status": "SOFT_OPTIMAL",
    "assignments": [
        {
            "project_id": 100,
            "session_id": 4000,
            "date": "2026-07-01",
            "period": "morning",
            "roles": {"supervisor": 1, "president": 3, "examiner": 2},
        },
        {
            "project_id": 101,
            "session_id": 4001,
            "date": "2026-07-02",
            "period": "morning",
            "roles": {"supervisor": 2, "president": 4, "examiner": 1},
        },
    ],
    "solutions": [
        {
            "solution_index": 1,
            "status": "SOFT_OPTIMAL",
            "raw_status": "OPTIMAL",
            "objective_value": 9800,
            "assignments": [],
            "unsatisfied_soft_constraints": [],
        },
        {
            "solution_index": 2,
            "status": "SOFT_OPTIMAL",
            "raw_status": "OPTIMAL",
            "objective_value": 9800,
            "assignments": [],
            "unsatisfied_soft_constraints": [],
        },
        {
            "solution_index": 3,
            "status": "SOFT_COMPROMISED",
            "raw_status": "OPTIMAL",
            "objective_value": 10300,
            "assignments": [],
            "unsatisfied_soft_constraints": [
                {
                    "rule_index": 5,
                    "rule": "avoid_professor_session",
                    "payload": {"professor_id": 3, "session_id": 4001},
                    "weight_scaled": 100,
                    "weight": 1.0,
                    "violation": 1,
                    "penalty": 100,
                    "penalty_weighted": 1.0,
                }
            ],
        },
        {
            "solution_index": 4,
            "status": "SOFT_COMPROMISED",
            "raw_status": "OPTIMAL",
            "objective_value": 10300,
            "assignments": [],
            "unsatisfied_soft_constraints": [
                {
                    "rule_index": 5,
                    "rule": "avoid_professor_session",
                    "payload": {"professor_id": 3, "session_id": 4001},
                    "weight_scaled": 100,
                    "weight": 1.0,
                    "violation": 1,
                    "penalty": 100,
                    "penalty_weighted": 1.0,
                }
            ],
        },
        {
            "solution_index": 5,
            "status": "SOFT_COMPROMISED",
            "raw_status": "OPTIMAL",
            "objective_value": 10800,
            "assignments": [],
            "unsatisfied_soft_constraints": [
                {
                    "rule_index": 4,
                    "rule": "prefer_professor_role",
                    "payload": {"professor_id": 4, "project_id": 101, "role": "PRESIDENT"},
                    "weight_scaled": 200,
                    "weight": 2.0,
                    "violation": 1,
                    "penalty": 200,
                    "penalty_weighted": 2.0,
                }
            ],
        },
    ],
    "solution_count": 5,
    "solutions_limit_reached": True,
}

test_reflector("test-score-calculation", solver_output_multi)