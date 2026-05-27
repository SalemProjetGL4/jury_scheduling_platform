"""
solver/test/run_update_case.py
──────────────────────────────
Runs the solver once to get a baseline solution, then applies several
override scenarios through the updater and prints a side-by-side diff.

Usage
-----
  python solver/test/run_update_case.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solver.solver_runner import solve
from solver.updater import update


# ── helpers ────────────────────────────────────────────────────────────────

def _load_case(name: str = "input_case.json") -> dict:
    return json.loads((Path(__file__).parent / name).read_text(encoding="utf-8-sig"))


def _print_assignments(assignments: list[dict]) -> None:
    for a in sorted(assignments, key=lambda x: x["project_id"]):
        roles = a.get("roles", {})
        print(
            f"  project={a['project_id']:>4}  session={a['session_id']}  "
            f"({a.get('date', '?')} {a.get('period', '?'):>9})  "
            f"supervisor={roles.get('supervisor', '-'):>3}  "
            f"president={roles.get('president', '-'):>3}  "
            f"examiner={roles.get('examiner', '-'):>3}"
        )


def _separator(title: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


# ── main ───────────────────────────────────────────────────────────────────

def main() -> None:
    data = _load_case()

    # ── Step 1: baseline solve ──────────────────────────────────────────────
    _separator("STEP 1 — Baseline solve")
    baseline = solve(data)
    if baseline["status"] not in ("OPTIMAL", "FEASIBLE"):
        print(f"Baseline failed: {baseline['status']}")
        print(json.dumps(baseline, indent=2))
        sys.exit(1)

    print(f"Status : {baseline['status']}")
    print(f"Quality: {baseline.get('quality_status')}")
    existing = baseline["assignments"]
    _print_assignments(existing)

    # ── Scenario A: move_professor ──────────────────────────────────────────
    _separator("SCENARIO A — move_professor: put professor 4 as PRESIDENT on project 100")
    result_a = update(
        data,
        existing,
        [{"type": "move_professor", "professor_id": 4, "project_id": 100, "role": "PRESIDENT"}],
    )
    print(f"Status : {result_a['status']}")
    summary = result_a.get("update_summary", {})
    print(f"Pinned : {summary.get('pinned_assignments')} assignments")
    print(f"Free   : {summary.get('free_pairs')}")
    print("Overrides:", json.dumps(summary.get("overrides_applied"), indent=4))
    if result_a["status"] not in ("OPTIMAL", "FEASIBLE", "UPDATE_INVALID"):
        print("(infeasible — constraints prevent this move)")
    else:
        _print_assignments(result_a.get("assignments", []))

    # ── Scenario B: move_professor + pin session ────────────────────────────
    # Look up an assignment to find a reachable session for the professor
    project_100_asgn = next(a for a in existing if a["project_id"] == 100)
    first_session = data["sessions"][0]["id"]
    _separator(
        f"SCENARIO B — move_professor + session: put professor 6 as EXAMINER "
        f"on project 100, in session {first_session}"
    )
    result_b = update(
        data,
        existing,
        [{
            "type": "move_professor",
            "professor_id": 6,
            "project_id": 100,
            "role": "EXAMINER",
            "session_id": first_session,
        }],
    )
    print(f"Status : {result_b['status']}")
    if result_b["status"] not in ("INFEASIBLE", "UPDATE_INVALID"):
        _print_assignments(result_b.get("assignments", []))
    else:
        print(f"  → {result_b.get('failed_constraints') or result_b.get('errors')}")

    # ── Scenario C: move_project ─────────────────────────────────────────────
    # Reschedule project 102 to the first available session that isn't pinned.
    target_session = data["sessions"][2]["id"]  # session index 2
    _separator(f"SCENARIO C — move_project: reschedule project 102 → session {target_session}")
    result_c = update(
        data,
        existing,
        [{"type": "move_project", "project_id": 102, "session_id": target_session}],
    )
    print(f"Status : {result_c['status']}")
    if result_c["status"] not in ("INFEASIBLE", "UPDATE_INVALID"):
        _print_assignments(result_c.get("assignments", []))
    else:
        print(f"  → {result_c.get('failed_constraints') or result_c.get('errors')}")

    # ── Scenario D: swap_professors ─────────────────────────────────────────
    _separator("SCENARIO D — swap_professors: swap professor 3 and professor 7 everywhere")
    result_d = update(
        data,
        existing,
        [{"type": "swap_professors", "professor_a": 3, "professor_b": 7}],
    )
    print(f"Status : {result_d['status']}")
    if result_d["status"] not in ("INFEASIBLE", "UPDATE_INVALID"):
        _print_assignments(result_d.get("assignments", []))
    else:
        print(f"  → {result_d.get('failed_constraints') or result_d.get('errors')}")

    # ── Scenario E: unpin_project ────────────────────────────────────────────
    _separator("SCENARIO E — unpin_project: let solver freely reschedule project 103")
    result_e = update(
        data,
        existing,
        [{"type": "unpin_project", "project_id": 103}],
    )
    print(f"Status : {result_e['status']}")
    if result_e["status"] not in ("INFEASIBLE", "UPDATE_INVALID"):
        _print_assignments(result_e.get("assignments", []))
    else:
        print(f"  → {result_e.get('failed_constraints') or result_e.get('errors')}")

    # ── Scenario F: validation error ─────────────────────────────────────────
    _separator("SCENARIO F — validation: bad professor_id and missing role")
    result_f = update(
        data,
        existing,
        [{"type": "move_professor", "professor_id": 9999, "project_id": 100, "role": "INVALID"}],
    )
    print(f"Status : {result_f['status']}")
    print("Errors :", json.dumps(result_f.get("errors"), indent=4))


if __name__ == "__main__":
    main()
