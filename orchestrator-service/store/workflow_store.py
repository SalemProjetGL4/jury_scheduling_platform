from __future__ import annotations

from threading import Lock

from graph.state import SchedulingState, clone_state


class WorkflowStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._states: dict[str, SchedulingState] = {}

    def put(self, state: SchedulingState) -> None:
        with self._lock:
            self._states[state["request_id"]] = clone_state(state)

    def get(self, request_id: str) -> SchedulingState | None:
        with self._lock:
            state = self._states.get(request_id)
            return None if state is None else clone_state(state)


store = WorkflowStore()
