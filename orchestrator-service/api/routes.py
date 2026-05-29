from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import requests

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from config import settings
from contracts.api_models import ScheduleAcceptedResponse, ScheduleRequest, StatusResponse
from graph.graph_builder import graph
from graph.state import SchedulingState, init_state, utc_now_iso
from store.workflow_store import store

try:
    from log_setup import logger
except Exception:
    import logging
    logger = logging.getLogger("orchestrator")

_REPORTS_DIR = Path("/app/logs/reports")


def _iso_to_ms(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp() * 1000


def _write_latency_report(result: dict, triggered_at: str) -> None:
    request_id = result.get("request_id", "unknown")
    node_history = result.get("node_history") or []
    step_history = result.get("step_history") or []
    final_status = result.get("final_status", "unknown")

    # Group sub-steps by agent name for easy lookup.
    sub_steps: dict[str, list[dict]] = {}
    for se in step_history:
        agent = se.get("agentName", "")
        sub_steps.setdefault(agent, []).append(se)

    steps = []
    for idx, event in enumerate(node_history):
        started = event.get("started_at") or ""
        ended = event.get("ended_at") or ""
        duration_ms = round(_iso_to_ms(ended) - _iso_to_ms(started)) if started and ended else None
        raw_status = event.get("status", "unknown")
        step_status = "success" if raw_status == "success" else ("error" if raw_status == "failed" else raw_status)
        agent_name = event.get("node", f"step_{idx}")
        steps.append({
            "agentName": agent_name,
            "stepIndex": idx,
            "startTime": started,
            "endTime": ended,
            "durationMs": duration_ms,
            "status": step_status,
            "summary": event.get("summary"),
            "steps_detail": [
                {
                    "stepName": se.get("stepName", ""),
                    "startedAt": se.get("startedAt", ""),
                    "endedAt": se.get("endedAt") or "",
                    "durationMs": se.get("durationMs"),
                }
                for se in sub_steps.get(agent_name, [])
            ],
        })

    all_starts = [_iso_to_ms(s["startTime"]) for s in steps if s["startTime"]]
    all_ends   = [_iso_to_ms(s["endTime"])   for s in steps if s["endTime"]]
    total_ms   = round(max(all_ends) - min(all_starts)) if all_starts and all_ends else None

    report = {
        "runId": request_id,
        "triggeredAt": triggered_at,
        "totalDurationMs": total_ms,
        "finalStatus": final_status,
        "steps": steps,
    }

    try:
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        (_REPORTS_DIR / f"latency-{request_id}.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

        # CSV — one agent row per node, then indented sub-step rows.
        csv_path = _REPORTS_DIR / f"latency-{request_id}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["runId", "stepIndex", "agentName", "stepName", "durationMs", "status"])
            for s in steps:
                w.writerow([request_id, s["stepIndex"], s["agentName"], "", s["durationMs"], s["status"]])
                for sd in s["steps_detail"]:
                    w.writerow([request_id, "", s["agentName"], sd["stepName"], sd["durationMs"], ""])

        # HTML — agent rows with collapsible nested sub-tables.
        def _sub_table(detail_rows: list[dict]) -> str:
            if not detail_rows:
                return ""
            inner = "".join(
                "<tr style=\"background:#eef4ff\">"
                f"<td style=\"padding-left:24px;color:#555\">↳ {d['stepName']}</td>"
                f"<td>{d['startedAt']}</td>"
                f"<td>{d['endedAt']}</td>"
                f"<td><b>{d['durationMs'] if d['durationMs'] is not None else '—'} ms</b></td>"
                "<td></td><td></td>"
                "</tr>"
                for d in detail_rows
            )
            return inner

        rows_html = "".join(
            "<tr>"
            f"<td>{s['stepIndex']}</td>"
            f"<td><b>{s['agentName']}</b></td>"
            f"<td>{s['startTime']}</td>"
            f"<td>{s['endTime']}</td>"
            f"<td>{s['durationMs'] if s['durationMs'] is not None else '—'}</td>"
            f"<td style=\"color:{'green' if s['status'] == 'success' else 'red'}\">{s['status']}</td>"
            "</tr>"
            + _sub_table(s["steps_detail"])
            for s in steps
        )
        html = (
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            f"<title>Latency — {request_id}</title>"
            "<style>"
            "body{font-family:sans-serif;padding:20px;background:#f8f9fa}"
            "h1{font-size:1.2em;color:#333}"
            ".meta{color:#555;font-size:.9em;margin-bottom:16px}"
            "table{border-collapse:collapse;width:100%}"
            "th,td{border:1px solid #ddd;padding:6px 12px;text-align:left;font-size:.85em}"
            "th{background:#4A90E2;color:#fff}"
            "tr:nth-child(even){background:#f2f2f2}"
            "tr[style*='eef4ff']{background:#eef4ff!important}"
            "</style></head><body>"
            "<h1>Pipeline Latency Report</h1>"
            "<div class=\"meta\">"
            f"<b>Run ID:</b> {request_id}<br>"
            f"<b>Triggered:</b> {triggered_at}<br>"
            f"<b>Total duration:</b> {f'{total_ms} ms' if total_ms is not None else '—'}<br>"
            f"<b>Final status:</b> {final_status}"
            "</div>"
            "<table><thead>"
            "<tr><th>#</th><th>Agent / Step</th><th>Start</th><th>End</th><th>Duration (ms)</th><th>Status</th></tr>"
            f"</thead><tbody>{rows_html}</tbody></table>"
            "</body></html>"
        )
        (_REPORTS_DIR / f"latency-{request_id}.html").write_text(html, encoding="utf-8")

        history_path = _REPORTS_DIR / "latency-history.csv"
        write_header = not history_path.exists()
        with history_path.open("a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if write_header:
                w.writerow(["runId", "triggeredAt", "totalDurationMs", "finalStatus", "stepCount"])
            w.writerow([request_id, triggered_at, total_ms, final_status, len(steps)])

        logger.info(
            "LATENCY REPORT saved — request_id=%s total_ms=%s agents=%d sub_steps=%d",
            request_id, total_ms, len(steps), len(step_history),
        )
    except Exception as exc:
        logger.warning("Failed to write latency report — %s", exc)


router = APIRouter(prefix="/workflows", tags=["workflows"])


def _probe_health(name: str, base_url: str | None) -> dict[str, str]:
    if not base_url:
        return {"status": "unknown", "detail": "missing_url"}

    try:
        response = requests.get(
            f"{base_url.rstrip('/')}/health",
            timeout=settings.gateway_timeout_seconds,
        )
        response.raise_for_status()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "down", "detail": str(exc)}


def _run_workflow(request_id: str) -> None:
    state = store.get(request_id)
    if state is None:
        return

    triggered_at = utc_now_iso()
    logger.info("WORKFLOW START — request_id=%s prompt=%r", request_id, (state.get("user_prompt") or "")[:120])
    result = graph.invoke(state)
    logger.info(
        "WORKFLOW END — request_id=%s final_status=%s errors=%s route=%s",
        request_id,
        result.get("final_status"),
        result.get("errors"),
        result.get("route"),
    )
    solver = result.get("solver_result") or {}
    logger.info(
        "SOLVER RESULT — status=%s solutions=%s assignments=%s failed_constraints=%s",
        solver.get("status"),
        len(solver.get("solutions") or []),
        len(solver.get("assignments") or []),
        solver.get("failed_constraints"),
    )
    store.put(result)
    _write_latency_report(result, triggered_at)


@router.post("/schedule", response_model=ScheduleAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def schedule_workflow(payload: ScheduleRequest, background_tasks: BackgroundTasks):
    request_id = str(uuid4())
    state: SchedulingState = init_state(
        request_id=request_id,
        prompt=payload.prompt,
        user_id=payload.user_id,
        old_solver_result=payload.old_solver_result,
        requested_route=payload.requested_route,
    )
    store.put(state)
    background_tasks.add_task(_run_workflow, request_id)
    return ScheduleAcceptedResponse(request_id=request_id, status="running")


@router.get("/monitor/health")
def monitor_health() -> dict[str, dict[str, str]]:
    return {
        "orchestrator": {"status": "ok"},
        "translator": _probe_health("translator", settings.translator_service_url),
        "solver": _probe_health("solver", settings.solver_service_url),
        "reflector": _probe_health("reflector", settings.reflector_service_url),
        "updater": _probe_health("updater", settings.updater_service_url),
    }


@router.get("/{request_id}/status", response_model=StatusResponse)
def workflow_status(request_id: str):
    state = store.get(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="request_id not found")

    return StatusResponse(
        request_id=request_id,
        final_status=state["final_status"],
        current_node=state["current_node"],
        node_history=state["node_history"],
        errors=state["errors"],
        unrecognized_constraints=state["unrecognized_constraints"],
    )


@router.get("/{request_id}/result")
def workflow_result(request_id: str):
    state = store.get(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="request_id not found")

    if state["final_status"] == "running":
        raise HTTPException(status_code=409, detail="workflow is still running")

    return state
