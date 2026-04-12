from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from solver.solver_runner import solve


app = FastAPI(title="Juriq Solver Service", version="0.1.0")


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/solve", tags=["solver"])
def solve_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    return solve(payload)
