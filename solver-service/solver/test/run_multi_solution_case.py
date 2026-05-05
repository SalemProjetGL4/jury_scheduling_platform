from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _load_solve() -> Any:
    if __package__ in (None, ""):
        repo_root = Path(__file__).resolve().parent.parent.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

    from solver import solve

    return solve


def main() -> int:
    input_path = Path(__file__).resolve().with_name("input_multi_solution_case.json")
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))

    solve = _load_solve()
    result = solve(payload)

    print("OUTPUT=")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("status") == "INFEASIBLE":
        print("\nASSERTION FAILED: scenario is infeasible.")
        return 1

    solutions = result.get("solutions") or []
    if len(solutions) < 2:
        print("\nASSERTION FAILED: expected at least 2 feasible solutions.")
        return 1

    for index, solution in enumerate(solutions, start=1):
        if "unsatisfied_soft_constraints" not in solution:
            print(f"\nASSERTION FAILED: solution {index} is missing unsatisfied_soft_constraints.")
            return 1

    penalties = [
        round(
            sum(float(item.get("penalty_weighted", item.get("penalty", 0))) for item in solution.get("unsatisfied_soft_constraints", [])),
            2,
        )
        for solution in solutions
    ]
    print("\nSUMMARY=")
    print(f"status={result.get('status')}")
    print(f"solution_count={result.get('solution_count')}")
    print(f"penalties={penalties}")
    print("all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
