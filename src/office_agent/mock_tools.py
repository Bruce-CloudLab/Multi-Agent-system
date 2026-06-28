from __future__ import annotations

from typing import Any


def _project_suffix(project_id: str) -> str:
    if project_id.startswith("PROJ-"):
        return project_id.removeprefix("PROJ-")
    return project_id


def _inquiry_suffix(inquiry_id: str) -> str:
    if inquiry_id == "INQ-PROJ-CUST-A-0001":
        return ""
    if inquiry_id.startswith("INQ-PROJ-") and inquiry_id.endswith("-0001"):
        return inquiry_id.removeprefix("INQ-PROJ-").removesuffix("-0001")
    return inquiry_id


def check_permission(employee_id: str, request_type: str) -> dict[str, Any]:
    evidence_by_type = {
        "salary_query": "PERMISSION-CHECK-SALARY-0001",
        "reception_schedule": "PERMISSION-CHECK-RECEPTION-0001",
        "reception_plan_upload": "PERMISSION-CHECK-RECEPTION-UPLOAD-0001",
        "project_inquiry": "PERMISSION-CHECK-PROJECT-INQUIRY-0001",
    }
    scope_by_type = {
        "salary_query": "self_salary_preview",
        "reception_schedule": "important_reception_read",
        "reception_plan_upload": "important_reception_write",
        "project_inquiry": "project_inquiry_create",
    }
    return {
        "status": "success",
        "data": {
            "employee_id": employee_id,
            "request_type": request_type,
            "permission_status": "allowed",
            "permission_scope": scope_by_type[request_type],
        },
        "evidence_ref": evidence_by_type[request_type],
    }


def create_audit_log(
    employee_id: str,
    request_type: str,
    risk_level: str,
) -> dict[str, Any]:
    evidence_by_type = {
        "salary_query": "AUDIT-LOG-SALARY-0001",
        "reception_schedule": "AUDIT-LOG-RECEPTION-0001",
        "reception_plan_upload": "AUDIT-LOG-RECEPTION-UPLOAD-0001",
        "project_inquiry": "AUDIT-LOG-PROJECT-INQUIRY-0001",
    }
    return {
        "status": "success",
        "data": {
            "audit_id": f"AUDIT-{request_type.upper()}-0001",
            "employee_id": employee_id,
            "request_type": request_type,
            "risk_level": risk_level,
            "audit_status": "created",
        },
        "evidence_ref": evidence_by_type[request_type],
    }


def create_repair_ticket(location: str, issue: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "ticket_id": "ADMIN-REPAIR-0001",
            "location": location,
            "issue": issue,
            "status": "created",
        },
        "evidence_ref": "ADMIN-REPAIR-RESULT-0001",
    }


def search_policy_docs(query: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "query": query,
            "answer": "根据差旅制度，员工应在出差前提交申请，并在返程后按规定上传票据和行程材料。",
            "source_doc": "POLICY-TRAVEL-2026",
        },
        "evidence_ref": "RAG-POLICY-RESULT-0001",
    }


def evaluate_rag_triad(
    query: str,
    retrieved_context: dict[str, Any],
    answer: str,
    source_evidence_ref: str,
) -> dict[str, Any]:
    policy_terms = ("差旅", "报销", "制度", "出差", "票据", "行程")
    has_source = bool(retrieved_context.get("source_doc"))
    query_matches = any(term in query for term in policy_terms)
    answer_matches = any(term in answer for term in policy_terms)

    context_relevance_score = 0.95 if has_source and query_matches else 0.45
    groundedness_score = 0.94 if has_source and answer.strip() else 0.35
    answer_relevance_score = 0.92 if query_matches and answer_matches else 0.4
    minimum_required_score = 0.75
    scores = (
        context_relevance_score,
        groundedness_score,
        answer_relevance_score,
    )
    gate_status = (
        "passed" if min(scores) >= minimum_required_score else "blocked"
    )

    return {
        "status": "success",
        "data": {
            "evaluation_ref": "RAG-EVAL-POLICY-0001",
            "evaluation_framework": "trulens_rag_triad_compatible_mock_v1",
            "context_relevance_score": context_relevance_score,
            "groundedness_score": groundedness_score,
            "answer_relevance_score": answer_relevance_score,
            "minimum_required_score": minimum_required_score,
            "gate_status": gate_status,
            "source_evidence_ref": source_evidence_ref,
        },
    }


def get_salary_preview(employee_id: str, target_month: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "employee_id": employee_id,
            "target_month": target_month,
            "gross_salary": 18000,
            "estimated_net_salary": 14250,
            "currency": "CNY",
            "status": "preview",
            "disclaimer": "最终发放金额以财务和薪酬系统结算为准。",
        },
        "evidence_ref": "HR-SALARY-PREVIEW-0001",
    }


def get_reception_schedule(reception_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "reception_id": reception_id,
            "title": "客户 A 重要接待",
            "date": "2026-06-27",
            "time_window": "09:30-11:30",
            "location": "总部 18F 第一会议室",
            "owner": "行政接待组",
            "key_arrangements": [
                "09:30 前台接待并完成访客登记",
                "10:00 会议室汇报",
                "11:10 参观展厅",
            ],
        },
        "evidence_ref": "ADMIN-RECEPTION-SCHEDULE-0001",
    }


def get_leave_record(employee_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "employee_id": employee_id,
            "leave_id": "LEAVE-20260620-0001",
            "leave_start": "2026-06-20",
            "leave_end": "2026-06-24",
            "return_date": "2026-06-25",
            "status": "approved",
            "supports_cancellation": True,
        },
        "evidence_ref": "HR-LEAVE-RECORD-0001",
    }


def list_employee_tasks(employee_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "employee_id": employee_id,
            "tasks": [
                {
                    "task_id": "TASK-NORMAL-0001",
                    "title": "整理周报材料",
                    "risk_level": "low",
                    "deadline": "2026-06-27",
                    "created_during_leave": False,
                }
            ],
        },
        "evidence_ref": "TASK-LIST-RESULT-0001",
    }


def submit_leave_cancellation(employee_id: str, leave_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "employee_id": employee_id,
            "leave_id": leave_id,
            "cancellation_id": "LEAVE-CANCEL-0001",
            "workflow_status": "submitted",
            "reviewer_role": "attendance_staff",
        },
        "evidence_ref": "HR-LEAVE-CANCEL-SUBMIT-0001",
    }


def create_upload_session(file_name: str, reception_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "upload_session_id": "UPLOAD-SESSION-RECEPTION-0001",
            "file_id": "FILE-RECEPTION-PLAN-0001",
            "file_name": file_name,
            "reception_id": reception_id,
            "upload_status": "created",
        },
        "evidence_ref": "FILE-UPLOAD-SESSION-0001",
    }


def scan_file_safety(file_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "file_id": file_id,
            "file_safety_status": "passed",
            "scan_engine": "mock_file_safety_v1",
        },
        "evidence_ref": "FILE-SCAN-RESULT-0001",
    }


def classify_file_sensitivity(file_id: str, reception_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "file_id": file_id,
            "reception_id": reception_id,
            "business_domain": "important_reception",
            "sensitivity_level": "high",
            "business_object_match": True,
            "rag_ingestion_allowed": False,
        },
        "evidence_ref": "FILE-CLASSIFY-RECEPTION-0001",
    }


def extract_action_items(file_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "file_id": file_id,
            "action_items": [
                {
                    "action_item_id": "ACTION-RECEPTION-0001",
                    "title": "Confirm visitor registration and route cards",
                    "owner_id": "EMP-3101",
                    "owner_name": "Reception Coordinator",
                    "deadline": "2026-06-27T09:00:00+08:00",
                    "risk_level": "high",
                },
                {
                    "action_item_id": "ACTION-RECEPTION-0002",
                    "title": "Prepare meeting room materials and briefing deck",
                    "owner_id": "EMP-3102",
                    "owner_name": "Meeting Coordinator",
                    "deadline": "2026-06-27T09:20:00+08:00",
                    "risk_level": "high",
                },
            ],
        },
        "evidence_ref": "FILE-ACTION-ITEMS-0001",
    }


def update_reception_plan(
    reception_id: str,
    file_id: str,
    action_items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "reception_id": reception_id,
            "file_id": file_id,
            "update_id": "RECEPTION-UPDATE-0001",
            "updated_sections": ["itinerary", "action_items"],
            "action_item_count": len(action_items),
            "update_status": "updated",
        },
        "evidence_ref": "ADMIN-RECEPTION-UPDATE-0001",
    }


def create_tasks_from_action_items(
    action_items: list[dict[str, Any]],
    reception_id: str,
) -> dict[str, Any]:
    created_tasks = [
        {
            "task_id": f"TASK-RECEPTION-{index:04d}",
            "source_action_item_id": item["action_item_id"],
            "title": item["title"],
            "owner_id": item["owner_id"],
            "deadline": item["deadline"],
            "status": "created",
        }
        for index, item in enumerate(action_items, start=1)
    ]
    return {
        "status": "success",
        "data": {
            "batch_id": "TASK-BATCH-RECEPTION-0001",
            "reception_id": reception_id,
            "created_count": len(created_tasks),
            "created_tasks": created_tasks,
        },
        "evidence_ref": "TASK-RESULT-CREATE-BATCH-0001",
    }


def send_notification(task_batch_id: str, recipients: list[str]) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "notification_id": "NOTIFY-RECEPTION-TASKS-0001",
            "task_batch_id": task_batch_id,
            "recipients": recipients,
            "recipient_count": len(recipients),
            "status": "sent",
        },
        "evidence_ref": "NOTIFY-RESULT-RECEPTION-TASKS-0001",
    }


def decide_rag_ingestion(file_classification: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "business_domain": file_classification["business_domain"],
            "sensitivity_level": file_classification["sensitivity_level"],
            "rag_ingestion_allowed": False,
            "rag_ingestion_status": "skipped_by_policy",
            "reason": "important reception material requires controlled knowledge store review",
        },
        "evidence_ref": "RAG-INGESTION-DECISION-0001",
    }


def get_project_access_scope(employee_id: str, project_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "employee_id": employee_id,
            "project_id": project_id,
            "access_status": "allowed",
            "membership_status": "project_member",
            "project_sensitivity": "confidential",
        },
        "evidence_ref": "PROJECT-ACCESS-SCOPE-0001",
    }


def get_project_owner(project_id: str) -> dict[str, Any]:
    suffix = _project_suffix(project_id)
    return {
        "status": "success",
        "data": {
            "project_id": project_id,
            "owner_id": "EMP-6001" if suffix == "CUST-A" else f"EMP-OWNER-{suffix}",
            "owner_name": f"Project Owner {suffix}",
            "owner_role": "project_owner",
        },
        "evidence_ref": "PROJECT-OWNER-0001",
    }


def create_project_inquiry(
    project_id: str,
    questioner_id: str,
    owner_id: str,
    question: str,
    risk_level: str,
) -> dict[str, Any]:
    suffix = _project_suffix(project_id)
    return {
        "status": "success",
        "data": {
            "inquiry_id": f"INQ-PROJ-{suffix}-0001",
            "project_id": project_id,
            "questioner_id": questioner_id,
            "owner_id": owner_id,
            "question": question,
            "risk_level": risk_level,
            "inquiry_status": "waiting_for_owner_reply",
        },
        "evidence_ref": "PROJECT-INQUIRY-RESULT-0001",
    }


def create_project_inquiry_task(
    inquiry_id: str,
    owner_id: str,
) -> dict[str, Any]:
    suffix = _inquiry_suffix(inquiry_id)
    task_id = "TASK-INQUIRY-0001" if not suffix else f"TASK-INQUIRY-{suffix}-0001"
    return {
        "status": "success",
        "data": {
            "task_id": task_id,
            "inquiry_id": inquiry_id,
            "owner_id": owner_id,
            "task_type": "project_inquiry_response",
            "task_status": "created",
        },
        "evidence_ref": "TASK-RESULT-CREATE-INQUIRY-0001",
    }


def send_project_inquiry_notification(
    task_id: str,
    owner_id: str,
    force_failure: bool = False,
) -> dict[str, Any]:
    if force_failure:
        return {
            "status": "failed",
            "data": {
                "notification_id": None,
                "task_id": task_id,
                "recipients": [owner_id],
                "recipient_count": 1,
                "status": "failed",
                "error_code": "mock_notification_unavailable",
            },
            "evidence_ref": "NOTIFY-RESULT-PROJECT-INQUIRY-FAILED-0001",
        }

    if task_id == "TASK-INQUIRY-0001":
        notification_id = "NOTIFY-PROJECT-INQUIRY-0001"
    else:
        notification_id = f"NOTIFY-PROJECT-INQUIRY-{task_id.removeprefix('TASK-INQUIRY-')}"
    return {
        "status": "success",
        "data": {
            "notification_id": notification_id,
            "task_id": task_id,
            "recipients": [owner_id],
            "recipient_count": 1,
            "status": "sent",
        },
        "evidence_ref": "NOTIFY-RESULT-PROJECT-INQUIRY-0001",
    }


def add_project_inquiry_reply(
    inquiry_id: str,
    responder_id: str,
    reply_summary: str,
    reply_sensitivity_level: str,
) -> dict[str, Any]:
    suffix = _inquiry_suffix(inquiry_id)
    reply_ref = "INQUIRY-REPLY-0001" if not suffix else f"INQUIRY-REPLY-{suffix}-0001"
    return {
        "status": "success",
        "data": {
            "inquiry_id": inquiry_id,
            "owner_id": responder_id,
            "reply_status": "replied",
            "reply_ref": reply_ref,
            "reply_summary": reply_summary,
            "reply_sensitivity_level": reply_sensitivity_level,
            "rag_ingestion_allowed": False,
        },
        "evidence_ref": "PROJECT-INQUIRY-REPLY-0001",
    }


def complete_project_inquiry_task(
    task_id: str,
    completion_evidence_ref: str,
    completed_by: str,
    force_failure: bool = False,
) -> dict[str, Any]:
    if force_failure:
        return {
            "status": "failed",
            "data": {
                "task_id": task_id,
                "task_status": "completion_failed",
                "completion_evidence_ref": completion_evidence_ref,
                "completed_by": completed_by,
                "error_code": "mock_task_completion_failed",
            },
            "evidence_ref": "TASK-RESULT-COMPLETE-INQUIRY-FAILED-0001",
        }

    return {
        "status": "success",
        "data": {
            "task_id": task_id,
            "task_status": "completed",
            "completion_evidence_ref": completion_evidence_ref,
            "completed_by": completed_by,
        },
        "evidence_ref": "TASK-RESULT-COMPLETE-INQUIRY-0001",
    }


def decide_project_reply_rag_ingestion(
    reply_result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "reply_ref": reply_result["reply_ref"],
            "reply_sensitivity_level": reply_result["reply_sensitivity_level"],
            "rag_ingestion_allowed": False,
            "rag_ingestion_status": "skipped_by_policy",
            "reason": "confidential customer delivery reply stays in controlled project record",
        },
        "evidence_ref": "PROJECT-RAG-INGESTION-DECISION-0001",
    }
