from office_agent.graph import resume_project_inquiry_with_reply, run_scenario


def evidence_refs(state):
    return {item["evidence_ref"] for item in state.get("evidence_refs", [])}


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def assert_node_before(state, before, after):
    nodes = trace_nodes(state)
    assert before in nodes
    assert after in nodes
    assert nodes.index(before) < nodes.index(after)


def test_s15_project_inquiry_creates_record_task_notification_and_waits():
    state = run_scenario("S15")
    refs = evidence_refs(state)

    assert state["request_type"] == "project_inquiry"
    assert state["risk_precheck"]["level"] == "high"
    assert state["waiting_for"] == "project_owner_reply"
    assert state["interrupt_context"]["interrupt_type"] == "project_owner_reply"
    assert state["interrupt_context"]["resume_required"] is True

    assert "PERMISSION-CHECK-PROJECT-INQUIRY-0001" in refs
    assert "AUDIT-LOG-PROJECT-INQUIRY-0001" in refs
    assert "PROJECT-ACCESS-SCOPE-0001" in refs
    assert "PROJECT-OWNER-0001" in refs
    assert "PROJECT-INQUIRY-RESULT-0001" in refs
    assert "TASK-RESULT-CREATE-INQUIRY-0001" in refs
    assert "NOTIFY-RESULT-PROJECT-INQUIRY-0001" in refs

    assert "PROJECT-INQUIRY-REPLY-0001" not in refs
    assert "TASK-RESULT-COMPLETE-INQUIRY-0001" not in refs
    assert "PROJECT-RAG-INGESTION-DECISION-0001" not in refs

    assert_node_before(state, "business_router_node", "permission_audit_node")
    assert_node_before(state, "permission_audit_node", "project_access_node")
    assert_node_before(state, "project_access_node", "project_owner_node")
    assert_node_before(state, "project_owner_node", "inquiry_create_node")
    assert_node_before(state, "inquiry_create_node", "owner_task_create_node")
    assert_node_before(state, "owner_task_create_node", "owner_notification_node")
    assert_node_before(state, "owner_notification_node", "wait_for_owner_reply_node")

    assert "waiting_for_owner_reply" in state["final_response"]
    assert "owner_replied" not in state["final_response"]
    assert "task_completed" not in state["final_response"]


def test_s15_resume_with_owner_reply_records_reply_completes_task_and_decides_rag():
    waiting_state = run_scenario("S15")
    resumed = resume_project_inquiry_with_reply(
        waiting_state,
        {
            "inquiry_id": "INQ-PROJ-CUST-A-0001",
            "responder_id": "EMP-6001",
            "reply_summary": "需要补充盖章版附件，电子版今天下班前上传即可。",
            "reply_sensitivity_level": "confidential",
        },
    )
    refs = evidence_refs(resumed)

    assert resumed["request_id"] == waiting_state["request_id"]
    assert resumed["trace_id"] == waiting_state["trace_id"]
    assert resumed["waiting_for"] is None

    assert "PROJECT-INQUIRY-REPLY-0001" in refs
    assert "TASK-RESULT-COMPLETE-INQUIRY-0001" in refs
    assert "PROJECT-RAG-INGESTION-DECISION-0001" in refs

    assert resumed["domain_context"]["project_inquiry"]["reply_status"] == "replied"
    assert resumed["domain_context"]["project_inquiry_task"]["task_status"] == "completed"
    assert (
        resumed["domain_context"]["project_rag_ingestion"]["rag_ingestion_status"]
        == "skipped_by_policy"
    )

    assert_node_before(resumed, "wait_for_owner_reply_node", "inquiry_add_reply_node")
    assert_node_before(resumed, "inquiry_add_reply_node", "complete_owner_task_node")
    assert_node_before(
        resumed,
        "complete_owner_task_node",
        "project_rag_ingestion_decision_node",
    )
    assert_node_before(
        resumed,
        "project_rag_ingestion_decision_node",
        "trace_integrity_node",
    )

    assert "owner_reply_recorded" in resumed["final_response"]
    assert "owner_task_completed" in resumed["final_response"]
    assert "skipped_by_policy" in resumed["final_response"]
