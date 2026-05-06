from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable


def _load_solve() -> Any:
    if __package__ in (None, ""):
        repo_root = Path(__file__).resolve().parent.parent.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

    from solver import solve

    return solve


def _load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _assert_feasible(result: dict[str, Any]) -> tuple[bool, str]:
    status = str(result.get("status", "")).upper()
    if status == "INFEASIBLE":
        return False, "expected a feasible output but got INFEASIBLE"

    solutions = result.get("solutions") or []
    if not solutions:
        return False, "expected at least one solution"

    assignments = solutions[0].get("assignments") or result.get("assignments") or []
    if not assignments:
        return False, "expected assignments in feasible output"

    return True, ""


def _assert_infeasible(result: dict[str, Any]) -> tuple[bool, str]:
    status = str(result.get("status", "")).upper()
    if status != "INFEASIBLE":
        return False, f"expected INFEASIBLE but got {status or 'EMPTY'}"

    failed_constraints = result.get("failed_constraints")
    if not isinstance(failed_constraints, list) or not failed_constraints:
        return False, "expected non-empty failed_constraints for infeasible output"

    return True, ""


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    solve = _load_solve()

    cases: list[tuple[str, Path, Callable[[dict[str, Any]], tuple[bool, str]]]] = [
        ("feasible", base_dir / "input_feasible_case.json", _assert_feasible),
        ("infeasible", base_dir / "input_infeasible_case.json", _assert_infeasible),
    ]

    all_passed = True
    for label, path, checker in cases:
        payload = _load_payload(path)
        result = solve(payload)

        print(f"CASE={label}")
        print(f"INPUT={path.name}")
        print("OUTPUT=")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        ok, message = checker(result)
        if ok:
            print(f"ASSERTION PASSED ({label})\n")
            continue

        all_passed = False
        print(f"ASSERTION FAILED ({label}): {message}\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())