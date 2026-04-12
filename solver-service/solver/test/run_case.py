from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_solve() -> Any:
    """Load solve() whether script is run as module or direct file."""
    if __package__ in (None, ""):
        repo_root = Path(__file__).resolve().parent.parent.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))

    from solver import solve

    return solve


def _build_parser() -> argparse.ArgumentParser:
    default_input = Path(__file__).resolve().with_name("input_case.json")
    parser = argparse.ArgumentParser(
        description="Run the jury solver on a JSON input file and print result JSON."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        default=default_input,
        help=(
            "Path to a JSON file containing the solver payload "
            f"(default: {default_input})."
        ),
    )
    parser.add_argument(
        "--show-input",
        action="store_true",
        help="Print input JSON before output JSON.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of pretty format.",
    )
    return parser


def _dump_json(data: Any, *, compact: bool) -> str:
    if compact:
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(data, indent=2, ensure_ascii=False)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    input_path = args.input_file
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 2

    try:
        with input_path.open("r", encoding="utf-8-sig") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {input_path}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(payload, dict):
        print("Input JSON must be an object at the top level.", file=sys.stderr)
        return 2

    solve = _load_solve()
    result = solve(payload)

    if args.show_input:
        print("INPUT=")
        print(_dump_json(payload, compact=args.compact))

    print("OUTPUT=")
    print(_dump_json(result, compact=args.compact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
