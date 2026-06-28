from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from threading import RLock
from typing import Any
from urllib.parse import quote
from uuid import uuid4


CHECKPOINT_SAVED_AT = "2026-06-27T10:00:02+08:00"
CHECKPOINT_RESUMED_AT = "2026-06-27T10:10:00+08:00"


class CheckpointNotFoundError(Exception):
    """Raised when no persisted checkpoint exists for a thread id."""


def _trace(node: str, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "event_id": f"TRACE-{uuid4().hex[:8].upper()}",
        "node": node,
        "action": action,
        "data": data or {},
    }


def append_checkpoint_trace(
    state: dict[str, Any],
    action: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(state)
    updated.setdefault("trace_events", []).append(
        _trace("checkpoint_store", action, data)
    )
    return updated


def checkpoint_manual_review_state(
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
            "node": "checkpoint_store",
            "code": code,
            "message": f"checkpoint resume blocked: {code}",
            "data": {"thread_id": thread_id},
        }
    )
    state.setdefault("gate_checks", []).append(
        {
            "gate": "checkpoint_store",
            "status": "blocked",
            "reason": code,
        }
    )
    state = append_checkpoint_trace(
        state,
        "checkpoint_resume_rejected",
        {"thread_id": thread_id, "code": code},
    )
    state.setdefault("trace_events", []).append(
        _trace("manual_review_node", "manual_review_required", {"blocked_reason": code})
    )
    state["final_response"] = (
        "该请求触发人工复核条件，系统暂不继续自动执行。"
        f"blocked_reason={code}."
    )
    return state


class JsonCheckpointStore:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    @contextmanager
    def locked(self):
        with self._lock:
            yield

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(state)
        thread_id = stored.get("thread_id") or stored.get("checkpoint_context", {}).get(
            "thread_id"
        )
        if not thread_id:
            raise ValueError("checkpoint state requires thread_id")
        stored["thread_id"] = thread_id
        path = self._path_for(thread_id)
        with self._lock:
            path.write_text(
                json.dumps(stored, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        return stored

    def load(self, thread_id: str) -> dict[str, Any]:
        path = self._path_for(thread_id)
        with self._lock:
            if not path.exists():
                raise CheckpointNotFoundError(thread_id)
            return json.loads(path.read_text(encoding="utf-8"))

    def _path_for(self, thread_id: str) -> Path:
        safe_thread_id = quote(thread_id, safe="")
        return self.root_dir / f"{safe_thread_id}.json"
