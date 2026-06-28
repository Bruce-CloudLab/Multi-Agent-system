from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from typing import Any

from office_agent.graph import (
    build_graph,
    build_project_inquiry_resume_graph,
    resume_project_inquiry_thread,
    start_project_inquiry_thread,
)


def run_concurrent_requests(
    requests: list[dict[str, Any]],
    max_workers: int = 5,
) -> list[dict[str, Any]]:
    """Invoke one compiled entry graph with multiple requests concurrently."""
    app = build_graph()
    results: list[dict[str, Any] | None] = [None] * len(requests)

    def invoke_one(index: int, request: dict[str, Any]) -> dict[str, Any]:
        started_at = perf_counter()
        try:
            state = app.invoke(dict(request))
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return {
                "index": index,
                "status": "success",
                "input": request,
                "state": state,
                "error": None,
                "elapsed_ms": elapsed_ms,
            }
        except Exception as exc:  # pragma: no cover - exercised only on failure paths
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return {
                "index": index,
                "status": "error",
                "input": request,
                "state": None,
                "error": repr(exc),
                "elapsed_ms": elapsed_ms,
            }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(invoke_one, index, dict(request))
            for index, request in enumerate(requests)
        ]
        for future in as_completed(futures):
            result = future.result()
            results[result["index"]] = result

    return [result for result in results if result is not None]


def run_concurrent_project_inquiry_resumes(
    saved_states: list[dict[str, Any]],
    owner_reply_events: list[dict[str, Any]],
    max_workers: int = 5,
) -> list[dict[str, Any]]:
    """Invoke one compiled project-inquiry resume graph concurrently."""
    app = build_project_inquiry_resume_graph()
    results: list[dict[str, Any] | None] = [None] * len(saved_states)

    def invoke_one(
        index: int,
        saved_state: dict[str, Any],
        owner_reply_event: dict[str, Any],
    ) -> dict[str, Any]:
        started_at = perf_counter()
        try:
            resume_input = dict(saved_state)
            resume_input["owner_reply_event"] = dict(owner_reply_event)
            state = app.invoke(resume_input)
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return {
                "index": index,
                "status": "success",
                "input": saved_state,
                "owner_reply_event": owner_reply_event,
                "state": state,
                "error": None,
                "elapsed_ms": elapsed_ms,
            }
        except Exception as exc:  # pragma: no cover - exercised only on failure paths
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return {
                "index": index,
                "status": "error",
                "input": saved_state,
                "owner_reply_event": owner_reply_event,
                "state": None,
                "error": repr(exc),
                "elapsed_ms": elapsed_ms,
            }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                invoke_one,
                index,
                dict(saved_state),
                dict(owner_reply_event),
            )
            for index, (saved_state, owner_reply_event) in enumerate(
                zip(saved_states, owner_reply_events)
            )
        ]
        for future in as_completed(futures):
            result = future.result()
            results[result["index"]] = result

    return [result for result in results if result is not None]


def run_concurrent_project_inquiry_thread_starts(
    thread_specs: list[dict[str, Any]],
    checkpoint_store: Any,
    max_workers: int = 5,
) -> list[dict[str, Any]]:
    """Start multiple checkpointed project-inquiry threads concurrently."""
    results: list[dict[str, Any] | None] = [None] * len(thread_specs)

    def invoke_one(index: int, spec: dict[str, Any]) -> dict[str, Any]:
        started_at = perf_counter()
        try:
            state = start_project_inquiry_thread(
                spec.get("scenario_id", "S15"),
                checkpoint_store=checkpoint_store,
                thread_id=spec["thread_id"],
                request_input=spec.get("request_input"),
            )
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return {
                "index": index,
                "status": "success",
                "input": spec,
                "state": state,
                "error": None,
                "elapsed_ms": elapsed_ms,
            }
        except Exception as exc:  # pragma: no cover - exercised only on failures
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return {
                "index": index,
                "status": "error",
                "input": spec,
                "state": None,
                "error": repr(exc),
                "elapsed_ms": elapsed_ms,
            }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(invoke_one, index, dict(spec))
            for index, spec in enumerate(thread_specs)
        ]
        for future in as_completed(futures):
            result = future.result()
            results[result["index"]] = result

    return [result for result in results if result is not None]


def run_concurrent_project_inquiry_thread_resumes(
    thread_ids: list[str],
    owner_reply_events: list[dict[str, Any]],
    checkpoint_store: Any,
    max_workers: int = 5,
) -> list[dict[str, Any]]:
    """Resume checkpointed project-inquiry threads concurrently by thread id."""
    results: list[dict[str, Any] | None] = [None] * len(thread_ids)

    def invoke_one(
        index: int,
        thread_id: str,
        owner_reply_event: dict[str, Any],
    ) -> dict[str, Any]:
        started_at = perf_counter()
        try:
            state = resume_project_inquiry_thread(
                thread_id,
                dict(owner_reply_event),
                checkpoint_store=checkpoint_store,
            )
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return {
                "index": index,
                "status": "success",
                "thread_id": thread_id,
                "owner_reply_event": owner_reply_event,
                "state": state,
                "error": None,
                "elapsed_ms": elapsed_ms,
            }
        except Exception as exc:  # pragma: no cover - exercised only on failures
            elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
            return {
                "index": index,
                "status": "error",
                "thread_id": thread_id,
                "owner_reply_event": owner_reply_event,
                "state": None,
                "error": repr(exc),
                "elapsed_ms": elapsed_ms,
            }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(invoke_one, index, thread_id, dict(owner_reply_event))
            for index, (thread_id, owner_reply_event) in enumerate(
                zip(thread_ids, owner_reply_events)
            )
        ]
        for future in as_completed(futures):
            result = future.result()
            results[result["index"]] = result

    return [result for result in results if result is not None]
