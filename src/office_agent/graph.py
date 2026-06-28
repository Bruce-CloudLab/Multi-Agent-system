from __future__ import annotations

from copy import deepcopy
from typing import Literal

from langgraph.graph import END, START, StateGraph

from office_agent.checkpointing import (
    CHECKPOINT_RESUMED_AT,
    CHECKPOINT_SAVED_AT,
    CheckpointNotFoundError,
    JsonCheckpointStore,
    append_checkpoint_trace,
    checkpoint_manual_review_state,
)
from office_agent.langgraph_checkpointing import (
    DEFAULT_PROJECT_INQUIRY_CHECKPOINT_NS,
    LANGGRAPH_ROOT_CHECKPOINT_NS,
    append_native_checkpoint_trace,
    latest_native_checkpoint_tuple,
    load_native_checkpoint_state,
    make_langgraph_thread_config,
    native_checkpoint_manual_review_state,
    native_checkpoint_thread_lock,
    save_native_checkpoint_state,
)
from office_agent.nodes import (
    admin_repair_node,
    ask_clarification_node,
    business_router_node,
    checkpoint_waiting_state_node,
    complete_owner_task_node,
    create_action_item_tasks_node,
    employee_tasks_node,
    entry_node,
    file_processing_node,
    final_response_node,
    inquiry_add_reply_node,
    inquiry_create_node,
    leave_cancellation_decision_node,
    leave_record_node,
    manual_review_node,
    orchestrator_node,
    owner_notification_node,
    owner_task_create_node,
    payroll_query_node,
    permission_audit_node,
    project_access_node,
    project_owner_node,
    project_rag_ingestion_decision_node,
    rag_evaluation_node,
    rag_policy_node,
    rag_ingestion_decision_node,
    reception_schedule_node,
    reception_update_node,
    notification_node,
    resolve_identity_node,
    submit_leave_cancellation_node,
    trace_integrity_node,
    validate_project_inquiry_resume_node,
    wait_for_owner_reply_node,
)
from office_agent.scenarios import get_scenario_input
from office_agent.state import OfficeAgentState


def route_after_orchestrator(
    state: OfficeAgentState,
) -> Literal["ask_clarification_node", "resolve_identity_node", "business_router_node"]:
    if state.get("request_type") == "unknown":
        return "ask_clarification_node"
    if state.get("next_action", {}).get("type") == "ask_clarification":
        return "ask_clarification_node"
    if identity_is_required_and_missing(state):
        return "resolve_identity_node"
    return "business_router_node"


def identity_is_required_and_missing(state: OfficeAgentState) -> bool:
    identity_check = state.get("identity_check", {})
    return identity_check.get("required") and identity_check.get("status") != "resolved"


def permission_has_passed(state: OfficeAgentState) -> bool:
    return (
        state.get("permission_context", {}).get("permission_status") == "allowed"
        and state.get("audit_context", {}).get("audit_status") == "created"
    )


def route_after_identity_resolution(
    state: OfficeAgentState,
) -> Literal["ask_clarification_node", "business_router_node"]:
    if state.get("blocked_reason") == "missing_employee_identity":
        return "ask_clarification_node"
    return "business_router_node"


def route_after_permission_audit(
    state: OfficeAgentState,
) -> Literal["ask_clarification_node", "manual_review_node", "business_router_node"]:
    if state.get("blocked_reason") == "missing_employee_identity":
        return "ask_clarification_node"
    if state.get("permission_context", {}).get("permission_status") != "allowed":
        return "manual_review_node"
    if state.get("audit_context", {}).get("audit_status") != "created":
        return "manual_review_node"
    return "business_router_node"


def route_by_request_type(
    state: OfficeAgentState,
) -> Literal["permission_audit_node", "admin_repair_node", "payroll_query_node", "reception_schedule_node", "file_processing_node", "project_access_node", "rag_policy_node", "leave_record_node", "ask_clarification_node"]:
    if state.get("risk_precheck", {}).get("level") == "high" and not permission_has_passed(state):
        return "permission_audit_node"

    routes = {
        "repair": "admin_repair_node",
        "salary_query": "payroll_query_node",
        "reception_schedule": "reception_schedule_node",
        "reception_plan_upload": "file_processing_node",
        "project_inquiry": "project_access_node",
        "policy_query": "rag_policy_node",
        "leave_cancellation": "leave_record_node",
    }
    return routes.get(state.get("request_type"), "ask_clarification_node")


def route_after_leave_decision(
    state: OfficeAgentState,
) -> Literal["submit_leave_cancellation_node", "trace_integrity_node", "manual_review_node"]:
    next_action = state.get("next_action", {})
    if next_action.get("type") == "manual_review":
        return "manual_review_node"
    if next_action.get("target") == "hr_api.submit_leave_cancellation":
        return "submit_leave_cancellation_node"
    return "trace_integrity_node"


def route_after_owner_notification(
    state: OfficeAgentState,
) -> Literal["wait_for_owner_reply_node", "manual_review_node"]:
    if state.get("next_action", {}).get("type") == "manual_review":
        return "manual_review_node"
    if state.get("blocked_reason") == "owner_notification_failed":
        return "manual_review_node"
    return "wait_for_owner_reply_node"


def route_after_project_inquiry_resume_validation(
    state: OfficeAgentState,
) -> Literal["inquiry_add_reply_node", "manual_review_node"]:
    if state.get("next_action", {}).get("type") == "manual_review":
        return "manual_review_node"
    if state.get("resume_validation", {}).get("status") == "blocked":
        return "manual_review_node"
    return "inquiry_add_reply_node"


def route_after_owner_task_completion(
    state: OfficeAgentState,
) -> Literal["project_rag_ingestion_decision_node", "manual_review_node"]:
    if state.get("next_action", {}).get("type") == "manual_review":
        return "manual_review_node"
    if state.get("blocked_reason") == "owner_task_completion_failed":
        return "manual_review_node"
    return "project_rag_ingestion_decision_node"


def route_after_rag_evaluation(
    state: OfficeAgentState,
) -> Literal["trace_integrity_node", "manual_review_node"]:
    if state.get("next_action", {}).get("type") == "manual_review":
        return "manual_review_node"
    if (
        state.get("domain_context", {})
        .get("rag_evaluation", {})
        .get("gate_status")
        != "passed"
    ):
        return "manual_review_node"
    return "trace_integrity_node"


def route_after_trace_integrity(
    state: OfficeAgentState,
) -> Literal["manual_review_node", "final_response_node"]:
    if state.get("missing_trace_events"):
        return "manual_review_node"
    return "final_response_node"


def build_graph(checkpointer=None):
    graph = StateGraph(OfficeAgentState)

    graph.add_node("entry_node", entry_node)
    graph.add_node("orchestrator_node", orchestrator_node)
    graph.add_node("permission_audit_node", permission_audit_node)
    graph.add_node("resolve_identity_node", resolve_identity_node)
    graph.add_node("business_router_node", business_router_node)
    graph.add_node("admin_repair_node", admin_repair_node)
    graph.add_node("payroll_query_node", payroll_query_node)
    graph.add_node("reception_schedule_node", reception_schedule_node)
    graph.add_node("file_processing_node", file_processing_node)
    graph.add_node("reception_update_node", reception_update_node)
    graph.add_node("create_action_item_tasks_node", create_action_item_tasks_node)
    graph.add_node("notification_node", notification_node)
    graph.add_node("rag_ingestion_decision_node", rag_ingestion_decision_node)
    graph.add_node("project_access_node", project_access_node)
    graph.add_node("project_owner_node", project_owner_node)
    graph.add_node("inquiry_create_node", inquiry_create_node)
    graph.add_node("owner_task_create_node", owner_task_create_node)
    graph.add_node("owner_notification_node", owner_notification_node)
    graph.add_node("wait_for_owner_reply_node", wait_for_owner_reply_node)
    graph.add_node("checkpoint_waiting_state_node", checkpoint_waiting_state_node)
    graph.add_node("rag_policy_node", rag_policy_node)
    graph.add_node("rag_evaluation_node", rag_evaluation_node)
    graph.add_node("leave_record_node", leave_record_node)
    graph.add_node("employee_tasks_node", employee_tasks_node)
    graph.add_node("leave_cancellation_decision_node", leave_cancellation_decision_node)
    graph.add_node("submit_leave_cancellation_node", submit_leave_cancellation_node)
    graph.add_node("trace_integrity_node", trace_integrity_node)
    graph.add_node("final_response_node", final_response_node)
    graph.add_node("ask_clarification_node", ask_clarification_node)
    graph.add_node("manual_review_node", manual_review_node)

    graph.add_edge(START, "entry_node")
    graph.add_edge("entry_node", "orchestrator_node")
    graph.add_conditional_edges("orchestrator_node", route_after_orchestrator)
    graph.add_conditional_edges("permission_audit_node", route_after_permission_audit)
    graph.add_conditional_edges("resolve_identity_node", route_after_identity_resolution)
    graph.add_conditional_edges("business_router_node", route_by_request_type)

    graph.add_edge("admin_repair_node", "trace_integrity_node")
    graph.add_edge("payroll_query_node", "trace_integrity_node")
    graph.add_edge("reception_schedule_node", "trace_integrity_node")
    graph.add_edge("file_processing_node", "reception_update_node")
    graph.add_edge("reception_update_node", "create_action_item_tasks_node")
    graph.add_edge("create_action_item_tasks_node", "notification_node")
    graph.add_edge("notification_node", "rag_ingestion_decision_node")
    graph.add_edge("rag_ingestion_decision_node", "trace_integrity_node")
    graph.add_edge("project_access_node", "project_owner_node")
    graph.add_edge("project_owner_node", "inquiry_create_node")
    graph.add_edge("inquiry_create_node", "owner_task_create_node")
    graph.add_edge("owner_task_create_node", "owner_notification_node")
    graph.add_conditional_edges(
        "owner_notification_node",
        route_after_owner_notification,
    )
    graph.add_edge("wait_for_owner_reply_node", "checkpoint_waiting_state_node")
    graph.add_edge("checkpoint_waiting_state_node", "final_response_node")
    graph.add_edge("rag_policy_node", "rag_evaluation_node")
    graph.add_conditional_edges("rag_evaluation_node", route_after_rag_evaluation)
    graph.add_edge("leave_record_node", "employee_tasks_node")
    graph.add_edge("employee_tasks_node", "leave_cancellation_decision_node")
    graph.add_conditional_edges(
        "leave_cancellation_decision_node",
        route_after_leave_decision,
    )
    graph.add_edge("submit_leave_cancellation_node", "trace_integrity_node")
    graph.add_conditional_edges("trace_integrity_node", route_after_trace_integrity)

    graph.add_edge("ask_clarification_node", END)
    graph.add_edge("manual_review_node", END)
    graph.add_edge("final_response_node", END)

    return graph.compile(checkpointer=checkpointer)


def build_project_inquiry_resume_graph(checkpointer=None):
    graph = StateGraph(OfficeAgentState)

    graph.add_node(
        "validate_project_inquiry_resume_node",
        validate_project_inquiry_resume_node,
    )
    graph.add_node("inquiry_add_reply_node", inquiry_add_reply_node)
    graph.add_node("complete_owner_task_node", complete_owner_task_node)
    graph.add_node(
        "project_rag_ingestion_decision_node",
        project_rag_ingestion_decision_node,
    )
    graph.add_node("trace_integrity_node", trace_integrity_node)
    graph.add_node("final_response_node", final_response_node)
    graph.add_node("manual_review_node", manual_review_node)

    graph.add_edge(START, "validate_project_inquiry_resume_node")
    graph.add_conditional_edges(
        "validate_project_inquiry_resume_node",
        route_after_project_inquiry_resume_validation,
    )
    graph.add_edge("inquiry_add_reply_node", "complete_owner_task_node")
    graph.add_conditional_edges(
        "complete_owner_task_node",
        route_after_owner_task_completion,
    )
    graph.add_edge("project_rag_ingestion_decision_node", "trace_integrity_node")
    graph.add_conditional_edges("trace_integrity_node", route_after_trace_integrity)
    graph.add_edge("manual_review_node", END)
    graph.add_edge("final_response_node", END)

    return graph.compile(checkpointer=checkpointer)


def run_scenario(scenario_id: str) -> OfficeAgentState:
    app = build_graph()
    return app.invoke(get_scenario_input(scenario_id))


def resume_project_inquiry_with_reply(
    saved_state: OfficeAgentState,
    owner_reply_event: dict,
) -> OfficeAgentState:
    app = build_project_inquiry_resume_graph()
    resume_input = dict(saved_state)
    resume_input["owner_reply_event"] = owner_reply_event
    return app.invoke(resume_input)


def start_project_inquiry_thread(
    scenario_id: str,
    checkpoint_store: JsonCheckpointStore,
    thread_id: str,
    request_input: dict | None = None,
    native_checkpointer=None,
    native_checkpoint_ns: str = LANGGRAPH_ROOT_CHECKPOINT_NS,
    project_checkpoint_ns: str = DEFAULT_PROJECT_INQUIRY_CHECKPOINT_NS,
) -> OfficeAgentState:
    app = build_graph(checkpointer=native_checkpointer)
    request = deepcopy(request_input) if request_input is not None else get_scenario_input(
        scenario_id
    )
    request["scenario_id"] = scenario_id
    request["thread_id"] = thread_id
    native_config = None
    if native_checkpointer is not None:
        native_config = make_langgraph_thread_config(
            thread_id,
            checkpoint_ns=native_checkpoint_ns,
            metadata={"scenario_id": scenario_id},
            project_checkpoint_ns=project_checkpoint_ns,
        )
    state = app.invoke(request, native_config) if native_config else app.invoke(request)
    if state.get("waiting_for") != "project_owner_reply":
        raise ValueError("checkpointed project inquiry start requires waiting state")

    checkpoint_context = dict(state.get("checkpoint_context", {}))
    checkpoint_context["saved_at"] = CHECKPOINT_SAVED_AT
    if native_checkpointer is not None:
        latest_native = latest_native_checkpoint_tuple(
            native_checkpointer,
            thread_id,
            checkpoint_ns=native_checkpoint_ns,
        )
        if latest_native is None:
            raise ValueError("LangGraph native checkpoint was not saved")
        native_checkpoint = {
            "provider": "langgraph",
            "thread_id": thread_id,
            "checkpoint_ns": native_checkpoint_ns,
            "project_checkpoint_ns": project_checkpoint_ns,
            "checkpoint_id": latest_native.config["configurable"]["checkpoint_id"],
        }
        checkpoint_context["native_checkpoint"] = native_checkpoint
        state = append_native_checkpoint_trace(
            state,
            "native_checkpoint_saved",
            native_checkpoint,
        )
    state["checkpoint_context"] = checkpoint_context
    state = append_checkpoint_trace(
        state,
        "checkpoint_saved",
        {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_context.get("checkpoint_id"),
        },
    )
    return checkpoint_store.save(state)


def resume_project_inquiry_thread(
    thread_id: str,
    owner_reply_event: dict,
    checkpoint_store: JsonCheckpointStore,
) -> OfficeAgentState:
    with checkpoint_store.locked():
        try:
            saved_state = checkpoint_store.load(thread_id)
        except CheckpointNotFoundError:
            return checkpoint_manual_review_state(
                thread_id,
                "checkpoint_not_found",
                owner_reply_event,
            )

        if saved_state.get("checkpoint_context", {}).get("status") == "resumed":
            return checkpoint_manual_review_state(
                thread_id,
                "checkpoint_already_resumed",
                owner_reply_event,
                base_state=saved_state,
            )

        saved_state = append_checkpoint_trace(
            saved_state,
            "checkpoint_loaded",
            {"thread_id": thread_id},
        )
        resumed = resume_project_inquiry_with_reply(saved_state, owner_reply_event)
        if resumed.get("next_action", {}).get("type") == "manual_review":
            return resumed

        checkpoint_context = dict(resumed.get("checkpoint_context", {}))
        checkpoint_context["status"] = "resumed"
        checkpoint_context["resumed_at"] = CHECKPOINT_RESUMED_AT
        resumed["checkpoint_context"] = checkpoint_context
        resumed = append_checkpoint_trace(
            resumed,
            "checkpoint_resumed",
            {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_context.get("checkpoint_id"),
            },
        )
        return checkpoint_store.save(resumed)


def resume_project_inquiry_thread_from_native_checkpoint(
    thread_id: str,
    owner_reply_event: dict,
    native_checkpointer,
    native_checkpoint_ns: str = LANGGRAPH_ROOT_CHECKPOINT_NS,
    project_checkpoint_ns: str = DEFAULT_PROJECT_INQUIRY_CHECKPOINT_NS,
) -> OfficeAgentState:
    with native_checkpoint_thread_lock(
        native_checkpointer,
        thread_id,
        checkpoint_ns=native_checkpoint_ns,
    ):
        saved_state = load_native_checkpoint_state(
            native_checkpointer,
            thread_id,
            checkpoint_ns=native_checkpoint_ns,
        )
        if saved_state is None:
            return native_checkpoint_manual_review_state(
                thread_id,
                "native_checkpoint_not_found",
                owner_reply_event,
            )

        if saved_state.get("checkpoint_context", {}).get("status") == "resumed":
            return native_checkpoint_manual_review_state(
                thread_id,
                "native_checkpoint_already_resumed",
                owner_reply_event,
                base_state=saved_state,
            )

        if saved_state.get("waiting_for") != "project_owner_reply":
            return native_checkpoint_manual_review_state(
                thread_id,
                "invalid_native_checkpoint_waiting_state",
                owner_reply_event,
                base_state=saved_state,
            )

        saved_state = append_native_checkpoint_trace(
            saved_state,
            "native_checkpoint_loaded",
            {
                "thread_id": thread_id,
                "checkpoint_ns": native_checkpoint_ns,
                "project_checkpoint_ns": project_checkpoint_ns,
            },
        )
        resumed = resume_project_inquiry_with_reply(saved_state, owner_reply_event)
        if resumed.get("next_action", {}).get("type") == "manual_review":
            return resumed

        checkpoint_context = dict(resumed.get("checkpoint_context", {}))
        checkpoint_context["status"] = "resumed"
        checkpoint_context["resumed_at"] = CHECKPOINT_RESUMED_AT
        resumed["checkpoint_context"] = checkpoint_context
        resumed = append_native_checkpoint_trace(
            resumed,
            "native_checkpoint_resumed",
            {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_context.get("checkpoint_id"),
                "checkpoint_ns": native_checkpoint_ns,
                "project_checkpoint_ns": project_checkpoint_ns,
            },
        )
        save_native_checkpoint_state(
            native_checkpointer,
            thread_id,
            resumed,
            checkpoint_ns=native_checkpoint_ns,
        )
        return resumed
