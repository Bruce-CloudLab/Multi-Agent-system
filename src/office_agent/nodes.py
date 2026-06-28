from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from office_agent.mock_tools import (
    add_project_inquiry_reply,
    check_permission,
    complete_project_inquiry_task,
    create_audit_log,
    create_project_inquiry,
    create_project_inquiry_task,
    classify_file_sensitivity,
    create_tasks_from_action_items,
    create_repair_ticket,
    create_upload_session,
    decide_project_reply_rag_ingestion,
    decide_rag_ingestion,
    evaluate_rag_triad,
    extract_action_items,
    get_project_access_scope,
    get_project_owner,
    get_reception_schedule,
    get_leave_record,
    get_salary_preview,
    list_employee_tasks,
    search_policy_docs,
    scan_file_safety,
    send_notification,
    send_project_inquiry_notification,
    submit_leave_cancellation,
    update_reception_plan,
)
from office_agent.state import OfficeAgentState


def _trace(node: str, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "event_id": f"TRACE-{uuid4().hex[:8].upper()}",
        "node": node,
        "action": action,
        "data": data or {},
    }


def _evidence(tool_name: str, evidence_ref: str) -> dict[str, Any]:
    return {"tool_name": tool_name, "evidence_ref": evidence_ref}


PROJECT_OWNER_REPLY_INTERRUPT_CREATED_AT = "2026-06-27T10:00:00+08:00"
PROJECT_OWNER_REPLY_INTERRUPT_EXPIRES_AT = "2026-06-30T10:00:00+08:00"
REQUIRED_OWNER_REPLY_FIELDS = (
    "inquiry_id",
    "responder_id",
    "reply_summary",
    "reply_sensitivity_level",
)


def _manual_review_update(
    node: str,
    code: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details = data or {}
    return {
        "blocked_reason": code,
        "next_action": {"type": "manual_review", "target": code},
        "errors": [
            {
                "node": node,
                "code": code,
                "message": message,
                "data": details,
            }
        ],
        "gate_checks": [
            {
                "gate": node,
                "status": "blocked",
                "reason": message,
            }
        ],
        "trace_events": [
            _trace(
                node,
                "manual_review_required",
                {"code": code, **details},
            )
        ],
    }


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def entry_node(state: OfficeAgentState) -> dict[str, Any]:
    request_id = state.get("request_id", f"REQ-{uuid4().hex[:8].upper()}")
    trace_id = state.get("trace_id", f"TRACE-{uuid4().hex[:8].upper()}")
    return {
        "request_id": request_id,
        "trace_id": trace_id,
        "trace_events": [
            _trace("entry_node", "request_initialized", {"request_id": request_id})
        ],
    }


def orchestrator_node(state: OfficeAgentState) -> dict[str, Any]:
    user_input = state["user_input"]
    scenario_id = state.get("scenario_id")

    if scenario_id == "S01" or "报修" in user_input or "灯坏" in user_input:
        request_type = "repair"
        risk = {"level": "low", "reason": "普通行政报修，不涉及敏感数据披露"}
        identity_check = {"required": False}
        tools = [{"tool_call": "admin_api.create_repair_ticket"}]
    elif scenario_id == "S02" or "薪资" in user_input or "工资" in user_input:
        request_type = "salary_query"
        risk = {"level": "high", "reason": "薪资属于个人敏感信息，必须先做身份、权限和审计"}
        identity_check = {"required": True}
        tools = [
            {"tool_call": "permission_api.check_permission"},
            {"tool_call": "audit_api.create_audit_log"},
            {"tool_call": "hr_api.get_salary_preview"},
        ]
    elif scenario_id == "S14":
        request_type = "reception_plan_upload"
        risk = {
            "level": "high",
            "reason": "important reception upload changes sensitive internal arrangements and tasks",
        }
        identity_check = {"required": True}
        tools = [
            {"tool_call": "permission_api.check_permission"},
            {"tool_call": "audit_api.create_audit_log"},
            {"tool_call": "file_api.create_upload_session"},
            {"tool_call": "file_api.scan_file_safety"},
            {"tool_call": "file_api.classify_file_sensitivity"},
            {"tool_call": "file_api.extract_action_items"},
            {"tool_call": "reception_api.update_reception_plan"},
            {"tool_call": "task_api.create_tasks_from_action_items"},
            {"tool_call": "notification_api.send_message"},
            {"tool_call": "rag.decide_ingestion"},
        ]
    elif scenario_id == "S15":
        request_type = "project_inquiry"
        risk = {
            "level": "high",
            "reason": "客户交付项目问询涉及可能影响对外承诺的事项",
        }
        identity_check = {"required": True}
        tools = [
            {"tool_call": "permission_api.check_permission"},
            {"tool_call": "audit_api.create_audit_log"},
            {"tool_call": "project_api.get_project_access_scope"},
            {"tool_call": "project_api.get_project_owner"},
            {"tool_call": "project_inquiry_api.create_inquiry"},
            {"tool_call": "task_api.create_task"},
            {"tool_call": "notification_api.send_message"},
            {"tool_call": "project_inquiry_api.add_reply"},
            {"tool_call": "task_api.complete_task"},
            {"tool_call": "rag.decide_project_reply_ingestion"},
        ]
    elif scenario_id == "S05" or "重要接待" in user_input or "接待" in user_input:
        request_type = "reception_schedule"
        risk = {"level": "high", "reason": "重要接待安排属于高风险内部信息，必须先做权限和审计"}
        identity_check = {"required": True}
        tools = [
            {"tool_call": "permission_api.check_permission"},
            {"tool_call": "audit_api.create_audit_log"},
            {"tool_call": "admin_api.get_reception_schedule"},
        ]
    elif scenario_id == "S08" or "差旅" in user_input or "制度" in user_input:
        request_type = "policy_query"
        risk = {"level": "low", "reason": "制度查询，只能基于 RAG 证据回答"}
        identity_check = {"required": False}
        tools = [{"tool_call": "rag.search_policy_docs"}]
    elif scenario_id == "S04" or "销假" in user_input:
        request_type = "leave_cancellation"
        risk = {"level": "medium", "reason": "销假会影响考勤记录，需要确认员工身份和请假记录"}
        identity_check = {"required": True}
        tools = [
            {"tool_call": "hr_api.get_leave_record"},
            {"tool_call": "task_api.list_employee_tasks"},
            {"tool_call": "hr_api.submit_leave_cancellation"},
        ]
    else:
        request_type = "unknown"
        risk = {"level": "unknown", "reason": "无法识别请求类型"}
        identity_check = {"required": False}
        tools = []

    return {
        "request_type": request_type,
        "risk_precheck": risk,
        "identity_check": identity_check,
        "routing_plan": {"target_request_type": request_type},
        "tool_execution_plan": tools,
        "next_action": {"type": "route", "target": request_type},
        "trace_events": [
            _trace(
                "orchestrator_node",
                "request_classified",
                {"request_type": request_type, "risk_level": risk["level"]},
            )
        ],
    }


def resolve_identity_node(state: OfficeAgentState) -> dict[str, Any]:
    operator = state.get("operator", {})
    employee_id = operator.get("employee_id")
    if not employee_id:
        return {
            "blocked_reason": "missing_employee_identity",
            "next_action": {"type": "ask_clarification", "question": "请提供员工身份信息。"},
            "trace_events": [
                _trace("resolve_identity_node", "identity_missing")
            ],
        }

    return {
        "identity_check": {
            "required": True,
            "status": "resolved",
            "employee_id": employee_id,
        },
        "blocked_reason": "",
        "trace_events": [
            _trace(
                "resolve_identity_node",
                "identity_resolved",
                {"employee_id": employee_id},
            )
        ],
    }


def business_router_node(state: OfficeAgentState) -> dict[str, Any]:
    return {
        "route_decision": state["request_type"],
        "trace_events": [
            _trace(
                "business_router_node",
                "business_route_selected",
                {"request_type": state["request_type"]},
            )
        ],
    }


def permission_audit_node(state: OfficeAgentState) -> dict[str, Any]:
    operator = state.get("operator", {})
    employee_id = operator.get("employee_id")
    request_type = state["request_type"]
    risk_level = state["risk_precheck"]["level"]

    if not employee_id:
        return {
            "blocked_reason": "missing_employee_identity",
            "next_action": {"type": "ask_clarification", "question": "请提供操作人身份信息。"},
            "trace_events": [
                _trace("permission_audit_node", "identity_missing")
            ],
        }

    permission_result = check_permission(
        employee_id=employee_id,
        request_type=request_type,
    )
    audit_result = create_audit_log(
        employee_id=employee_id,
        request_type=request_type,
        risk_level=risk_level,
    )

    return {
        "identity_check": {
            "required": True,
            "status": "resolved",
            "employee_id": employee_id,
        },
        "blocked_reason": "",
        "permission_context": permission_result["data"],
        "audit_context": audit_result["data"],
        "tool_results": {
            "permission_api.check_permission": permission_result,
            "audit_api.create_audit_log": audit_result,
        },
        "evidence_refs": [
            _evidence("permission_api.check_permission", permission_result["evidence_ref"]),
            _evidence("audit_api.create_audit_log", audit_result["evidence_ref"]),
        ],
        "gate_checks": [
            {
                "gate": "permission_audit",
                "status": "passed",
                "reason": "高风险请求已完成权限校验和审计记录。",
            }
        ],
        "trace_events": [
            _trace(
                "permission_audit_node",
                "permission_and_audit_recorded",
                {
                    "permission_evidence": permission_result["evidence_ref"],
                    "audit_evidence": audit_result["evidence_ref"],
                },
            )
        ],
    }


def admin_repair_node(state: OfficeAgentState) -> dict[str, Any]:
    result = create_repair_ticket(location="工位上方", issue="照明灯损坏")
    return {
        "tool_results": {"admin_api.create_repair_ticket": result},
        "evidence_refs": [
            _evidence("admin_api.create_repair_ticket", result["evidence_ref"])
        ],
        "domain_context": {
            "repair": {
                "ticket_id": result["data"]["ticket_id"],
                "status": result["data"]["status"],
            }
        },
        "trace_events": [
            _trace(
                "admin_repair_node",
                "tool_result_recorded",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def payroll_query_node(state: OfficeAgentState) -> dict[str, Any]:
    employee_id = state["identity_check"]["employee_id"]
    result = get_salary_preview(employee_id=employee_id, target_month="2026-07")
    return {
        "tool_results": {"hr_api.get_salary_preview": result},
        "evidence_refs": [_evidence("hr_api.get_salary_preview", result["evidence_ref"])],
        "domain_context": {"salary_query": result["data"]},
        "trace_events": [
            _trace(
                "payroll_query_node",
                "salary_preview_loaded",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def reception_schedule_node(state: OfficeAgentState) -> dict[str, Any]:
    reception_id = state.get("business_object", {}).get(
        "reception_id",
        "RECEPTION-20260627-AM",
    )
    result = get_reception_schedule(reception_id=reception_id)
    return {
        "tool_results": {"admin_api.get_reception_schedule": result},
        "evidence_refs": [
            _evidence("admin_api.get_reception_schedule", result["evidence_ref"])
        ],
        "domain_context": {"reception_schedule": result["data"]},
        "trace_events": [
            _trace(
                "reception_schedule_node",
                "reception_schedule_loaded",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def rag_policy_node(state: OfficeAgentState) -> dict[str, Any]:
    result = search_policy_docs(query=state["user_input"])
    return {
        "tool_results": {"rag.search_policy_docs": result},
        "evidence_refs": [_evidence("rag.search_policy_docs", result["evidence_ref"])],
        "domain_context": {"policy_query": result["data"]},
        "trace_events": [
            _trace(
                "rag_policy_node",
                "rag_result_recorded",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def rag_evaluation_node(state: OfficeAgentState) -> dict[str, Any]:
    policy = state["domain_context"]["policy_query"]
    source_evidence_ref = state["tool_results"]["rag.search_policy_docs"][
        "evidence_ref"
    ]
    result = evaluate_rag_triad(
        query=state["user_input"],
        retrieved_context=policy,
        answer=policy["answer"],
        source_evidence_ref=source_evidence_ref,
    )
    evaluation = result["data"]
    gate_status = evaluation["gate_status"]
    update: dict[str, Any] = {
        "tool_results": {"rag.evaluate_triad": result},
        "domain_context": {"rag_evaluation": evaluation},
        "gate_checks": [
            {
                "gate": "rag_quality_gate",
                "status": gate_status,
                "evaluation_ref": evaluation["evaluation_ref"],
                "minimum_required_score": evaluation["minimum_required_score"],
                "source_evidence_ref": source_evidence_ref,
            }
        ],
        "trace_events": [
            _trace(
                "rag_evaluation_node",
                "rag_quality_evaluated",
                {
                    "evaluation_ref": evaluation["evaluation_ref"],
                    "gate_status": gate_status,
                    "context_relevance_score": evaluation[
                        "context_relevance_score"
                    ],
                    "groundedness_score": evaluation["groundedness_score"],
                    "answer_relevance_score": evaluation[
                        "answer_relevance_score"
                    ],
                },
            )
        ],
    }
    if gate_status != "passed":
        update["blocked_reason"] = "rag_quality_gate_blocked"
        update["next_action"] = {
            "type": "manual_review",
            "target": "rag_quality_gate",
        }
        update["errors"] = [
            {
                "node": "rag_evaluation_node",
                "code": "rag_quality_gate_blocked",
                "message": "RAG evaluation scores did not meet the quality gate.",
                "data": {"evaluation_ref": evaluation["evaluation_ref"]},
            }
        ]
    return update


def file_processing_node(state: OfficeAgentState) -> dict[str, Any]:
    business_object = state.get("business_object", {})
    reception_id = business_object.get("reception_id", "RECEPTION-20260627-AM")
    file_name = business_object.get("file_name", "reception-plan-client-a.pdf")

    upload_result = create_upload_session(
        file_name=file_name,
        reception_id=reception_id,
    )
    file_id = upload_result["data"]["file_id"]
    safety_result = scan_file_safety(file_id=file_id)
    classification_result = classify_file_sensitivity(
        file_id=file_id,
        reception_id=reception_id,
    )
    action_items_result = extract_action_items(file_id=file_id)

    return {
        "tool_results": {
            "file_api.create_upload_session": upload_result,
            "file_api.scan_file_safety": safety_result,
            "file_api.classify_file_sensitivity": classification_result,
            "file_api.extract_action_items": action_items_result,
        },
        "evidence_refs": [
            _evidence("file_api.create_upload_session", upload_result["evidence_ref"]),
            _evidence("file_api.scan_file_safety", safety_result["evidence_ref"]),
            _evidence(
                "file_api.classify_file_sensitivity",
                classification_result["evidence_ref"],
            ),
            _evidence("file_api.extract_action_items", action_items_result["evidence_ref"]),
        ],
        "domain_context": {
            "file_processing": {
                "upload": upload_result["data"],
                "safety": safety_result["data"],
                "classification": classification_result["data"],
                "action_items": action_items_result["data"]["action_items"],
            }
        },
        "trace_events": [
            _trace(
                "file_processing_node",
                "file_processed",
                {
                    "file_id": file_id,
                    "action_item_count": len(action_items_result["data"]["action_items"]),
                },
            )
        ],
    }


def reception_update_node(state: OfficeAgentState) -> dict[str, Any]:
    file_processing = state["domain_context"]["file_processing"]
    upload = file_processing["upload"]
    action_items = file_processing["action_items"]
    result = update_reception_plan(
        reception_id=upload["reception_id"],
        file_id=upload["file_id"],
        action_items=action_items,
    )
    return {
        "tool_results": {"reception_api.update_reception_plan": result},
        "evidence_refs": [
            _evidence("reception_api.update_reception_plan", result["evidence_ref"])
        ],
        "domain_context": {"reception_update": result["data"]},
        "trace_events": [
            _trace(
                "reception_update_node",
                "reception_plan_updated",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def create_action_item_tasks_node(state: OfficeAgentState) -> dict[str, Any]:
    file_processing = state["domain_context"]["file_processing"]
    reception_id = file_processing["upload"]["reception_id"]
    action_items = file_processing["action_items"]
    result = create_tasks_from_action_items(
        action_items=action_items,
        reception_id=reception_id,
    )
    return {
        "tool_results": {"task_api.create_tasks_from_action_items": result},
        "evidence_refs": [
            _evidence("task_api.create_tasks_from_action_items", result["evidence_ref"])
        ],
        "domain_context": {"action_item_tasks": result["data"]},
        "trace_events": [
            _trace(
                "create_action_item_tasks_node",
                "action_item_tasks_created",
                {
                    "batch_id": result["data"]["batch_id"],
                    "created_count": result["data"]["created_count"],
                },
            )
        ],
    }


def notification_node(state: OfficeAgentState) -> dict[str, Any]:
    task_context = state["domain_context"]["action_item_tasks"]
    recipients = [task["owner_id"] for task in task_context["created_tasks"]]
    result = send_notification(
        task_batch_id=task_context["batch_id"],
        recipients=recipients,
    )
    return {
        "tool_results": {"notification_api.send_message": result},
        "evidence_refs": [
            _evidence("notification_api.send_message", result["evidence_ref"])
        ],
        "domain_context": {"notification": result["data"]},
        "trace_events": [
            _trace(
                "notification_node",
                "notification_sent",
                {
                    "notification_id": result["data"]["notification_id"],
                    "recipient_count": result["data"]["recipient_count"],
                },
            )
        ],
    }


def rag_ingestion_decision_node(state: OfficeAgentState) -> dict[str, Any]:
    classification = state["domain_context"]["file_processing"]["classification"]
    result = decide_rag_ingestion(file_classification=classification)
    return {
        "tool_results": {"rag.decide_ingestion": result},
        "evidence_refs": [_evidence("rag.decide_ingestion", result["evidence_ref"])],
        "domain_context": {"rag_ingestion": result["data"]},
        "gate_checks": [
            {
                "gate": "rag_ingestion",
                "status": result["data"]["rag_ingestion_status"],
                "reason": result["data"]["reason"],
            }
        ],
        "trace_events": [
            _trace(
                "rag_ingestion_decision_node",
                "rag_ingestion_decided",
                {
                    "evidence_ref": result["evidence_ref"],
                    "status": result["data"]["rag_ingestion_status"],
                },
            )
        ],
    }


def project_access_node(state: OfficeAgentState) -> dict[str, Any]:
    employee_id = state["identity_check"]["employee_id"]
    project_id = state.get("business_object", {}).get("project_id", "PROJ-CUST-A")
    result = get_project_access_scope(
        employee_id=employee_id,
        project_id=project_id,
    )
    return {
        "tool_results": {"project_api.get_project_access_scope": result},
        "evidence_refs": [
            _evidence("project_api.get_project_access_scope", result["evidence_ref"])
        ],
        "domain_context": {"project_access": result["data"]},
        "trace_events": [
            _trace(
                "project_access_node",
                "project_access_loaded",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def project_owner_node(state: OfficeAgentState) -> dict[str, Any]:
    project_id = state["domain_context"]["project_access"]["project_id"]
    result = get_project_owner(project_id=project_id)
    return {
        "tool_results": {"project_api.get_project_owner": result},
        "evidence_refs": [
            _evidence("project_api.get_project_owner", result["evidence_ref"])
        ],
        "domain_context": {"project_owner": result["data"]},
        "trace_events": [
            _trace(
                "project_owner_node",
                "project_owner_loaded",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def inquiry_create_node(state: OfficeAgentState) -> dict[str, Any]:
    business_object = state.get("business_object", {})
    question = business_object.get("question", state["user_input"])
    project_access = state["domain_context"]["project_access"]
    project_owner = state["domain_context"]["project_owner"]
    result = create_project_inquiry(
        project_id=project_access["project_id"],
        questioner_id=state["identity_check"]["employee_id"],
        owner_id=project_owner["owner_id"],
        question=question,
        risk_level=state["risk_precheck"]["level"],
    )
    return {
        "tool_results": {"project_inquiry_api.create_inquiry": result},
        "evidence_refs": [
            _evidence("project_inquiry_api.create_inquiry", result["evidence_ref"])
        ],
        "domain_context": {"project_inquiry": result["data"]},
        "trace_events": [
            _trace(
                "inquiry_create_node",
                "project_inquiry_created",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def owner_task_create_node(state: OfficeAgentState) -> dict[str, Any]:
    inquiry = state["domain_context"]["project_inquiry"]
    result = create_project_inquiry_task(
        inquiry_id=inquiry["inquiry_id"],
        owner_id=inquiry["owner_id"],
    )
    return {
        "tool_results": {"task_api.create_task": result},
        "evidence_refs": [_evidence("task_api.create_task", result["evidence_ref"])],
        "domain_context": {"project_inquiry_task": result["data"]},
        "trace_events": [
            _trace(
                "owner_task_create_node",
                "owner_task_created",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def owner_notification_node(state: OfficeAgentState) -> dict[str, Any]:
    task = state["domain_context"]["project_inquiry_task"]
    result = send_project_inquiry_notification(
        task_id=task["task_id"],
        owner_id=task["owner_id"],
        force_failure=state.get("business_object", {}).get(
            "simulate_project_notification_failure",
            False,
        ),
    )
    if result["status"] != "success":
        update = _manual_review_update(
            node="owner_notification_node",
            code="owner_notification_failed",
            message="项目负责人通知发送失败，需要人工确认负责人是否已收到待办。",
            data={
                "task_id": task["task_id"],
                "owner_id": task["owner_id"],
                "evidence_ref": result["evidence_ref"],
            },
        )
        update.update(
            {
                "tool_results": {"notification_api.send_message": result},
                "evidence_refs": [
                    _evidence(
                        "notification_api.send_message",
                        result["evidence_ref"],
                    )
                ],
                "domain_context": {"project_inquiry_notification": result["data"]},
            }
        )
        return update

    return {
        "tool_results": {"notification_api.send_message": result},
        "evidence_refs": [
            _evidence("notification_api.send_message", result["evidence_ref"])
        ],
        "domain_context": {"project_inquiry_notification": result["data"]},
        "trace_events": [
            _trace(
                "owner_notification_node",
                "owner_notification_sent",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def wait_for_owner_reply_node(state: OfficeAgentState) -> dict[str, Any]:
    inquiry = state["domain_context"]["project_inquiry"]
    task = state["domain_context"]["project_inquiry_task"]
    return {
        "waiting_for": "project_owner_reply",
        "interrupt_context": {
            "interrupt_type": "project_owner_reply",
            "resume_required": True,
            "inquiry_id": inquiry["inquiry_id"],
            "owner_task_id": task["task_id"],
            "created_at": PROJECT_OWNER_REPLY_INTERRUPT_CREATED_AT,
            "expires_at": PROJECT_OWNER_REPLY_INTERRUPT_EXPIRES_AT,
            "resume_payload_schema": {
                "inquiry_id": "string",
                "responder_id": "string",
                "reply_summary": "string",
                "reply_sensitivity_level": "string",
            },
        },
        "trace_events": [
            _trace(
                "wait_for_owner_reply_node",
                "owner_reply_interrupt_created",
                {
                    "inquiry_id": inquiry["inquiry_id"],
                    "owner_task_id": task["task_id"],
                },
            )
        ],
    }


def checkpoint_waiting_state_node(state: OfficeAgentState) -> dict[str, Any]:
    thread_id = state.get("thread_id") or state["request_id"]
    inquiry = state["domain_context"]["project_inquiry"]
    task = state["domain_context"]["project_inquiry_task"]
    checkpoint_context = {
        "checkpoint_id": f"CHK-{thread_id}",
        "thread_id": thread_id,
        "checkpoint_type": "project_owner_reply_waiting_state",
        "waiting_for": state.get("waiting_for"),
        "inquiry_id": inquiry["inquiry_id"],
        "owner_task_id": task["task_id"],
        "status": "ready_for_resume",
        "created_at": state["interrupt_context"]["created_at"],
    }
    return {
        "thread_id": thread_id,
        "checkpoint_context": checkpoint_context,
        "trace_events": [
            _trace(
                "checkpoint_waiting_state_node",
                "waiting_state_checkpointed",
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_context["checkpoint_id"],
                    "inquiry_id": inquiry["inquiry_id"],
                },
            )
        ],
    }


def validate_project_inquiry_resume_node(state: OfficeAgentState) -> dict[str, Any]:
    node = "validate_project_inquiry_resume_node"
    interrupt_context = state.get("interrupt_context", {})
    owner_reply = state.get("owner_reply_event") or {}
    inquiry = state.get("domain_context", {}).get("project_inquiry", {})
    expected_inquiry_id = inquiry.get("inquiry_id")

    if state.get("waiting_for") != "project_owner_reply":
        update = _manual_review_update(
            node=node,
            code="invalid_project_inquiry_resume_state",
            message="保存状态不在 project_owner_reply 等待边界，不能自动恢复项目问询。",
            data={"waiting_for": state.get("waiting_for")},
        )
        update["resume_validation"] = {
            "status": "blocked",
            "reason": "invalid_project_inquiry_resume_state",
        }
        return update

    missing_fields = [
        field
        for field in REQUIRED_OWNER_REPLY_FIELDS
        if not owner_reply.get(field)
    ]
    if missing_fields:
        update = _manual_review_update(
            node=node,
            code="owner_reply_missing_required_field",
            message="负责人回复事件缺少必要字段，不能写回项目问询。",
            data={"missing_fields": missing_fields},
        )
        update["resume_validation"] = {
            "status": "blocked",
            "reason": "owner_reply_missing_required_field",
            "missing_fields": missing_fields,
        }
        return update

    if not expected_inquiry_id:
        update = _manual_review_update(
            node=node,
            code="saved_inquiry_missing",
            message="保存状态缺少项目问询 id，不能自动恢复。",
        )
        update["resume_validation"] = {
            "status": "blocked",
            "reason": "saved_inquiry_missing",
        }
        return update

    reply_inquiry_id = owner_reply["inquiry_id"]
    interrupt_inquiry_id = interrupt_context.get("inquiry_id")
    if (
        reply_inquiry_id != expected_inquiry_id
        or interrupt_inquiry_id != expected_inquiry_id
    ):
        update = _manual_review_update(
            node=node,
            code="owner_reply_inquiry_mismatch",
            message="负责人回复事件与保存的项目问询 id 不匹配，不能自动写回。",
            data={
                "expected_inquiry_id": expected_inquiry_id,
                "reply_inquiry_id": reply_inquiry_id,
                "interrupt_inquiry_id": interrupt_inquiry_id,
            },
        )
        update["resume_validation"] = {
            "status": "blocked",
            "reason": "owner_reply_inquiry_mismatch",
            "expected_inquiry_id": expected_inquiry_id,
            "reply_inquiry_id": reply_inquiry_id,
        }
        return update

    received_at = owner_reply.get("received_at")
    expires_at = interrupt_context.get("expires_at")
    if received_at and expires_at and _parse_datetime(received_at) > _parse_datetime(expires_at):
        update = _manual_review_update(
            node=node,
            code="stale_project_owner_reply",
            message="负责人回复事件晚于等待状态过期时间，需要人工确认是否仍可采纳。",
            data={
                "received_at": received_at,
                "expires_at": expires_at,
                "inquiry_id": expected_inquiry_id,
            },
        )
        update["resume_validation"] = {
            "status": "blocked",
            "reason": "stale_project_owner_reply",
            "received_at": received_at,
            "expires_at": expires_at,
        }
        return update

    return {
        "blocked_reason": "",
        "resume_validation": {
            "status": "passed",
            "inquiry_id": expected_inquiry_id,
        },
        "gate_checks": [
            {
                "gate": "project_inquiry_resume_validation",
                "status": "passed",
                "reason": "owner reply event matches saved waiting state",
            }
        ],
        "trace_events": [
            _trace(
                node,
                "resume_validation_passed",
                {"inquiry_id": expected_inquiry_id},
            )
        ],
    }


def inquiry_add_reply_node(state: OfficeAgentState) -> dict[str, Any]:
    owner_reply = state["owner_reply_event"]
    expected_inquiry_id = state["domain_context"]["project_inquiry"]["inquiry_id"]
    if owner_reply["inquiry_id"] != expected_inquiry_id:
        raise ValueError("owner_reply_event inquiry_id does not match saved inquiry")

    result = add_project_inquiry_reply(
        inquiry_id=owner_reply["inquiry_id"],
        responder_id=owner_reply["responder_id"],
        reply_summary=owner_reply["reply_summary"],
        reply_sensitivity_level=owner_reply["reply_sensitivity_level"],
    )
    return {
        "waiting_for": None,
        "interrupt_context": {},
        "tool_results": {"project_inquiry_api.add_reply": result},
        "evidence_refs": [
            _evidence("project_inquiry_api.add_reply", result["evidence_ref"])
        ],
        "domain_context": {"project_inquiry": result["data"]},
        "trace_events": [
            _trace(
                "inquiry_add_reply_node",
                "owner_reply_recorded",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def complete_owner_task_node(state: OfficeAgentState) -> dict[str, Any]:
    task = state["domain_context"]["project_inquiry_task"]
    reply = state["domain_context"]["project_inquiry"]
    result = complete_project_inquiry_task(
        task_id=task["task_id"],
        completion_evidence_ref="PROJECT-INQUIRY-REPLY-0001",
        completed_by=reply["owner_id"],
        force_failure=state.get("owner_reply_event", {}).get(
            "simulate_task_completion_failure",
            False,
        ),
    )
    if result["status"] != "success":
        update = _manual_review_update(
            node="complete_owner_task_node",
            code="owner_task_completion_failed",
            message="负责人回复已写回，但待办完成失败，需要人工复核任务状态。",
            data={
                "task_id": task["task_id"],
                "inquiry_id": reply["inquiry_id"],
                "evidence_ref": result["evidence_ref"],
            },
        )
        update.update(
            {
                "tool_results": {"task_api.complete_task": result},
                "evidence_refs": [
                    _evidence("task_api.complete_task", result["evidence_ref"])
                ],
                "domain_context": {"project_inquiry_task": result["data"]},
            }
        )
        return update

    return {
        "tool_results": {"task_api.complete_task": result},
        "evidence_refs": [
            _evidence("task_api.complete_task", result["evidence_ref"])
        ],
        "domain_context": {"project_inquiry_task": result["data"]},
        "trace_events": [
            _trace(
                "complete_owner_task_node",
                "owner_task_completed",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def project_rag_ingestion_decision_node(state: OfficeAgentState) -> dict[str, Any]:
    reply = state["domain_context"]["project_inquiry"]
    result = decide_project_reply_rag_ingestion(reply_result=reply)
    return {
        "tool_results": {"rag.decide_project_reply_ingestion": result},
        "evidence_refs": [
            _evidence("rag.decide_project_reply_ingestion", result["evidence_ref"])
        ],
        "domain_context": {"project_rag_ingestion": result["data"]},
        "gate_checks": [
            {
                "gate": "project_reply_rag_ingestion",
                "status": result["data"]["rag_ingestion_status"],
                "reason": result["data"]["reason"],
            }
        ],
        "trace_events": [
            _trace(
                "project_rag_ingestion_decision_node",
                "project_reply_rag_ingestion_decided",
                {
                    "evidence_ref": result["evidence_ref"],
                    "status": result["data"]["rag_ingestion_status"],
                },
            )
        ],
    }


def leave_record_node(state: OfficeAgentState) -> dict[str, Any]:
    employee_id = state["identity_check"]["employee_id"]
    result = get_leave_record(employee_id=employee_id)
    return {
        "tool_results": {"hr_api.get_leave_record": result},
        "evidence_refs": [_evidence("hr_api.get_leave_record", result["evidence_ref"])],
        "domain_context": {"leave_record": result["data"]},
        "trace_events": [
            _trace(
                "leave_record_node",
                "leave_record_loaded",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def employee_tasks_node(state: OfficeAgentState) -> dict[str, Any]:
    employee_id = state["identity_check"]["employee_id"]
    result = list_employee_tasks(employee_id=employee_id)
    return {
        "tool_results": {"task_api.list_employee_tasks": result},
        "evidence_refs": [
            _evidence("task_api.list_employee_tasks", result["evidence_ref"])
        ],
        "domain_context": {"employee_tasks": result["data"]["tasks"]},
        "trace_events": [
            _trace(
                "employee_tasks_node",
                "employee_tasks_loaded",
                {
                    "evidence_ref": result["evidence_ref"],
                    "task_count": len(result["data"]["tasks"]),
                },
            )
        ],
    }


def leave_cancellation_decision_node(state: OfficeAgentState) -> dict[str, Any]:
    leave_record = state["domain_context"].get("leave_record")
    tasks = state["domain_context"].get("employee_tasks", [])

    if not leave_record:
        return {
            "next_action": {"type": "final_response", "target": "no_leave_record"},
            "blocked_reason": "leave_record_not_found",
            "trace_events": [
                _trace("leave_cancellation_decision_node", "leave_record_missing")
            ],
        }

    high_risk_blockers = [
        task
        for task in tasks
        if task.get("risk_level") == "high"
        and task.get("created_during_leave")
        and task.get("deadline", "") <= leave_record["return_date"]
    ]

    if high_risk_blockers:
        return {
            "next_action": {"type": "manual_review", "target": "high_risk_task_blocker"},
            "blocked_reason": "high_risk_task_blocker",
            "gate_checks": [
                {
                    "gate": "leave_cancellation_task_risk",
                    "status": "blocked",
                    "reason": "休假期间新增高风险且截止早于返岗日的待办，需要人工复核。",
                }
            ],
            "trace_events": [
                _trace(
                    "leave_cancellation_decision_node",
                    "manual_review_required",
                    {"blocker_count": len(high_risk_blockers)},
                )
            ],
        }

    return {
        "next_action": {"type": "tool_call", "target": "hr_api.submit_leave_cancellation"},
        "gate_checks": [
            {
                "gate": "leave_cancellation_task_risk",
                "status": "passed",
                "reason": "未发现阻断销假的高风险待办；普通待办只做提醒，不阻断销假。",
            }
        ],
        "trace_events": [
            _trace(
                "leave_cancellation_decision_node",
                "leave_cancellation_allowed",
                {"task_count": len(tasks)},
            )
        ],
    }


def submit_leave_cancellation_node(state: OfficeAgentState) -> dict[str, Any]:
    employee_id = state["identity_check"]["employee_id"]
    leave_id = state["domain_context"]["leave_record"]["leave_id"]
    result = submit_leave_cancellation(employee_id=employee_id, leave_id=leave_id)
    return {
        "tool_results": {"hr_api.submit_leave_cancellation": result},
        "evidence_refs": [
            _evidence("hr_api.submit_leave_cancellation", result["evidence_ref"])
        ],
        "domain_context": {"leave_cancellation": result["data"]},
        "trace_events": [
            _trace(
                "submit_leave_cancellation_node",
                "leave_cancellation_submitted",
                {"evidence_ref": result["evidence_ref"]},
            )
        ],
    }


def trace_integrity_node(state: OfficeAgentState) -> dict[str, Any]:
    required_by_type = {
        "repair": ["ADMIN-REPAIR-RESULT-0001"],
        "salary_query": [
            "PERMISSION-CHECK-SALARY-0001",
            "AUDIT-LOG-SALARY-0001",
            "HR-SALARY-PREVIEW-0001",
        ],
        "reception_schedule": [
            "PERMISSION-CHECK-RECEPTION-0001",
            "AUDIT-LOG-RECEPTION-0001",
            "ADMIN-RECEPTION-SCHEDULE-0001",
        ],
        "policy_query": ["RAG-POLICY-RESULT-0001"],
        "leave_cancellation": [
            "HR-LEAVE-RECORD-0001",
            "TASK-LIST-RESULT-0001",
            "HR-LEAVE-CANCEL-SUBMIT-0001",
        ],
        "reception_plan_upload": [
            "PERMISSION-CHECK-RECEPTION-UPLOAD-0001",
            "AUDIT-LOG-RECEPTION-UPLOAD-0001",
            "FILE-UPLOAD-SESSION-0001",
            "FILE-SCAN-RESULT-0001",
            "FILE-CLASSIFY-RECEPTION-0001",
            "FILE-ACTION-ITEMS-0001",
            "ADMIN-RECEPTION-UPDATE-0001",
            "TASK-RESULT-CREATE-BATCH-0001",
            "NOTIFY-RESULT-RECEPTION-TASKS-0001",
            "RAG-INGESTION-DECISION-0001",
        ],
        "project_inquiry": [
            "PERMISSION-CHECK-PROJECT-INQUIRY-0001",
            "AUDIT-LOG-PROJECT-INQUIRY-0001",
            "PROJECT-ACCESS-SCOPE-0001",
            "PROJECT-OWNER-0001",
            "PROJECT-INQUIRY-RESULT-0001",
            "TASK-RESULT-CREATE-INQUIRY-0001",
            "NOTIFY-RESULT-PROJECT-INQUIRY-0001",
            "PROJECT-INQUIRY-REPLY-0001",
            "TASK-RESULT-COMPLETE-INQUIRY-0001",
            "PROJECT-RAG-INGESTION-DECISION-0001",
        ],
    }
    evidence_refs = {item["evidence_ref"] for item in state.get("evidence_refs", [])}
    required = required_by_type.get(state.get("request_type"), [])
    missing = [ref for ref in required if ref not in evidence_refs]
    status = "passed" if not missing else "blocked"
    return {
        "missing_trace_events": missing,
        "gate_checks": [
            {
                "gate": "trace_integrity",
                "status": status,
                "reason": "关键证据完整" if not missing else "缺少关键证据",
            }
        ],
        "trace_events": [
            _trace(
                "trace_integrity_node",
                "trace_integrity_checked",
                {"status": status, "missing": missing},
            )
        ],
    }


def final_response_node(state: OfficeAgentState) -> dict[str, Any]:
    request_type = state.get("request_type")
    if state.get("missing_trace_events"):
        response = "当前流程缺少关键证据，已转人工复核，暂不输出确认性结论。"
    elif request_type == "repair":
        repair = state["domain_context"]["repair"]
        response = f"已创建行政报修工单 {repair['ticket_id']}，当前状态为 {repair['status']}。"
    elif request_type == "salary_query":
        salary = state["domain_context"]["salary_query"]
        response = (
            f"已完成权限校验和审计记录。{salary['target_month']} 薪资预览："
            f"税前 {salary['gross_salary']} {salary['currency']}，"
            f"预计实发 {salary['estimated_net_salary']} {salary['currency']}。"
            f"{salary['disclaimer']}"
        )
    elif request_type == "reception_schedule":
        reception = state["domain_context"]["reception_schedule"]
        arrangements = "；".join(reception["key_arrangements"])
        response = (
            f"已完成权限校验和审计记录。{reception['title']}安排："
            f"{reception['date']} {reception['time_window']}，"
            f"地点 {reception['location']}，负责人 {reception['owner']}。"
            f"关键事项：{arrangements}。"
        )
    elif request_type == "policy_query":
        policy = state["domain_context"]["policy_query"]
        rag_evaluation = state["domain_context"].get("rag_evaluation", {})
        response = (
            f"根据检索到的制度文档 {policy['source_doc']}：{policy['answer']}"
            f" rag_quality_gate={rag_evaluation.get('gate_status', 'unknown')}."
        )
    elif request_type == "reception_plan_upload":
        reception_update = state["domain_context"]["reception_update"]
        task_context = state["domain_context"]["action_item_tasks"]
        notification = state["domain_context"]["notification"]
        rag_decision = state["domain_context"]["rag_ingestion"]
        response = (
            f"reception_plan_updated {reception_update['update_id']}; "
            f"action_item_tasks_created {task_context['batch_id']} "
            f"count={task_context['created_count']}; "
            f"notifications_sent {notification['notification_id']} "
            f"recipient_count={notification['recipient_count']}; "
            f"rag_ingestion_status={rag_decision['rag_ingestion_status']}."
        )
    elif request_type == "project_inquiry":
        if state.get("waiting_for") == "project_owner_reply":
            inquiry = state["domain_context"]["project_inquiry"]
            task = state["domain_context"]["project_inquiry_task"]
            notification = state["domain_context"]["project_inquiry_notification"]
            response = (
                f"project_inquiry_created {inquiry['inquiry_id']}; "
                f"owner_task_created {task['task_id']}; "
                f"owner_notified {notification['notification_id']}; "
                "waiting_for_owner_reply."
            )
        else:
            inquiry = state["domain_context"]["project_inquiry"]
            task = state["domain_context"]["project_inquiry_task"]
            rag_decision = state["domain_context"]["project_rag_ingestion"]
            response = (
                f"owner_reply_recorded {inquiry['inquiry_id']} {inquiry['reply_ref']}; "
                f"owner_task_completed {task['task_id']}; "
                f"rag_ingestion_status={rag_decision['rag_ingestion_status']}."
            )
    elif request_type == "leave_cancellation":
        cancellation = state["domain_context"].get("leave_cancellation")
        if cancellation:
            response = (
                f"已提交销假申请 {cancellation['cancellation_id']}，"
                f"流程状态为 {cancellation['workflow_status']}，后续由考勤人员审核。"
            )
        else:
            response = "当前销假流程需要人工复核，暂未提交销假申请。"
    else:
        response = "我还不能识别这个请求，请补充业务类型和必要信息。"

    return {
        "final_response": response,
        "trace_events": [
            _trace(
                "final_response_node",
                "final_response_generated",
                {"request_type": request_type},
            )
        ],
    }


def ask_clarification_node(state: OfficeAgentState) -> dict[str, Any]:
    question = state.get("next_action", {}).get("question", "请补充必要信息。")
    return {
        "final_response": question,
        "trace_events": [
            _trace("ask_clarification_node", "clarification_requested")
        ],
    }


def manual_review_node(state: OfficeAgentState) -> dict[str, Any]:
    reason = state.get("blocked_reason") or "manual_review_required"
    return {
        "final_response": (
            "该请求触发人工复核条件，系统暂不继续自动执行。"
            f"blocked_reason={reason}."
        ),
        "trace_events": [
            _trace(
                "manual_review_node",
                "manual_review_required",
                {"blocked_reason": reason},
            )
        ],
    }
