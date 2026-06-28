from __future__ import annotations

from typing import Annotated, Any, NotRequired, TypedDict


def append_list(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    """Reducer for append-only State fields."""
    return (left or []) + (right or [])


def merge_dict(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reducer for keyed State fields such as tool results."""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class OfficeAgentState(TypedDict, total=False):
    request_id: str
    trace_id: str
    thread_id: str
    scenario_id: str
    user_input: str
    request_time: str
    business_object: dict[str, Any]

    operator: dict[str, Any]
    request_type: str
    risk_precheck: dict[str, Any]
    identity_check: dict[str, Any]
    permission_context: dict[str, Any]
    audit_context: dict[str, Any]

    routing_plan: dict[str, Any]
    route_decision: str
    tool_execution_plan: list[dict[str, Any]]
    next_action: dict[str, Any]
    blocked_reason: str

    tool_results: Annotated[dict[str, dict[str, Any]], merge_dict]
    evidence_refs: Annotated[list[dict[str, Any]], append_list]
    domain_context: Annotated[dict[str, Any], merge_dict]
    gate_checks: Annotated[list[dict[str, Any]], append_list]
    trace_events: Annotated[list[dict[str, Any]], append_list]
    errors: Annotated[list[dict[str, Any]], append_list]

    missing_trace_events: list[str]
    waiting_for: str | None
    interrupt_context: dict[str, Any]
    checkpoint_context: dict[str, Any]
    owner_reply_event: dict[str, Any]
    resume_validation: dict[str, Any]
    final_response: str
