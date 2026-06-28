from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from threading import RLock
from typing import Any
from uuid import uuid4


LANGGRAPH_ROOT_CHECKPOINT_NS = ""
DEFAULT_PROJECT_INQUIRY_CHECKPOINT_NS = "office_agent.s15.project_inquiry.v1"
_APPEND_ONLY_STATE_FIELDS = {
    "evidence_refs",
    "gate_checks",
    "trace_events",
    "errors",
}
_NATIVE_CHECKPOINT_LOCK_GUARD = RLock()
_NATIVE_CHECKPOINT_LOCKS: dict[tuple[int, str, str], RLock] = {}


def make_langgraph_thread_config(
    thread_id: str,
    checkpoint_ns: str = LANGGRAPH_ROOT_CHECKPOINT_NS,
    checkpoint_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    project_checkpoint_ns: str = DEFAULT_PROJECT_INQUIRY_CHECKPOINT_NS,
) -> dict[str, Any]:
    if not str(thread_id).strip():
        raise ValueError("LangGraph checkpoint config requires thread_id")

    configurable = {
        "thread_id": str(thread_id),
        "checkpoint_ns": str(checkpoint_ns),
    }
    if checkpoint_id:
        configurable["checkpoint_id"] = str(checkpoint_id)

    merged_metadata = {
        "checkpoint_scope": "project_inquiry_waiting_state",
        "project_checkpoint_ns": project_checkpoint_ns,
    }
    merged_metadata.update(metadata or {})

    return {
        "configurable": configurable,
        "metadata": merged_metadata,
    }


def latest_native_checkpoint_tuple(
    checkpointer: Any,
    thread_id: str,
    checkpoint_ns: str = LANGGRAPH_ROOT_CHECKPOINT_NS,
) -> Any | None:
    return checkpointer.get_tuple(
        make_langgraph_thread_config(thread_id, checkpoint_ns=checkpoint_ns)
    )


def append_native_checkpoint_trace(
    state: dict[str, Any],
    action: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    updated = deepcopy(state)
    updated.setdefault("trace_events", []).append(
        {
            "event_id": f"TRACE-{uuid4().hex[:8].upper()}",
            "node": "langgraph_native_checkpointer",
            "action": action,
            "data": data,
        }
    )
    return updated


@contextmanager
def native_checkpoint_thread_lock(
    checkpointer: Any,
    thread_id: str,
    checkpoint_ns: str = LANGGRAPH_ROOT_CHECKPOINT_NS,
):
    key = (id(checkpointer), str(thread_id), str(checkpoint_ns))
    with _NATIVE_CHECKPOINT_LOCK_GUARD:
        lock = _NATIVE_CHECKPOINT_LOCKS.setdefault(key, RLock())
    with lock:
        yield


def native_checkpoint_state_from_snapshot(snapshot: Any) -> dict[str, Any] | None:
    values = getattr(snapshot, "values", None)
    if not values:
        return None
    return deepcopy(dict(values))


def load_native_checkpoint_state(
    checkpointer: Any,
    thread_id: str,
    checkpoint_ns: str = LANGGRAPH_ROOT_CHECKPOINT_NS,
) -> dict[str, Any] | None:
    from office_agent.graph import build_graph

    app = build_graph(checkpointer=checkpointer)
    snapshot = app.get_state(
        make_langgraph_thread_config(thread_id, checkpoint_ns=checkpoint_ns)
    )
    return native_checkpoint_state_from_snapshot(snapshot)


def save_native_checkpoint_state(
    checkpointer: Any,
    thread_id: str,
    state: dict[str, Any],
    checkpoint_ns: str = LANGGRAPH_ROOT_CHECKPOINT_NS,
) -> dict[str, Any]:
    from office_agent.graph import build_graph

    app = build_graph(checkpointer=checkpointer)
    config = make_langgraph_thread_config(thread_id, checkpoint_ns=checkpoint_ns)
    previous = native_checkpoint_state_from_snapshot(app.get_state(config)) or {}
    app.update_state(
        config,
        _native_checkpoint_update(previous, state),
        as_node="final_response_node",
    )
    latest = native_checkpoint_state_from_snapshot(app.get_state(config))
    return latest or deepcopy(state)


def native_checkpoint_manual_review_state(
    thread_id: str,
    code: str,
    owner_reply_event: dict[str, Any],
    base_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = deepcopy(base_state) if base_state else {}
    state["thread_id"] = thread_id
    state["request_type"] = state.get("request_type", "project_inquiry")
    state["owner_reply_event"] = owner_reply_event
    state["blocked_reason"] = code
    state["next_action"] = {"type": "manual_review", "target": code}
    state.setdefault("errors", []).append(
        {
            "node": "langgraph_native_checkpointer",
            "code": code,
            "message": f"native checkpoint resume blocked: {code}",
            "data": {"thread_id": thread_id},
        }
    )
    state.setdefault("gate_checks", []).append(
        {
            "gate": "langgraph_native_checkpointer",
            "status": "blocked",
            "reason": code,
        }
    )
    state = append_native_checkpoint_trace(
        state,
        "native_checkpoint_resume_rejected",
        {"thread_id": thread_id, "code": code},
    )
    state.setdefault("trace_events", []).append(
        {
            "event_id": f"TRACE-{uuid4().hex[:8].upper()}",
            "node": "manual_review_node",
            "action": "manual_review_required",
            "data": {"blocked_reason": code},
        }
    )
    state["final_response"] = (
        "Native checkpoint resume requires manual review. "
        f"blocked_reason={code}."
    )
    return state


def _native_checkpoint_update(
    previous: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    update: dict[str, Any] = {}
    for key, value in state.items():
        if key in _APPEND_ONLY_STATE_FIELDS:
            update[key] = _list_suffix(previous.get(key, []), value or [])
        else:
            update[key] = deepcopy(value)
    return update


def _list_suffix(previous: list[Any], current: list[Any]) -> list[Any]:
    if len(current) >= len(previous) and current[: len(previous)] == previous:
        return deepcopy(current[len(previous) :])
    return []
