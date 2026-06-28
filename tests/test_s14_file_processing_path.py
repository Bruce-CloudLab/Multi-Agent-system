from office_agent.graph import run_scenario


def evidence_refs(state):
    return {item["evidence_ref"] for item in state.get("evidence_refs", [])}


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def assert_node_before(state, before, after):
    nodes = trace_nodes(state)
    assert before in nodes
    assert after in nodes
    assert nodes.index(before) < nodes.index(after)


def test_s14_reception_plan_upload_creates_tasks_notifies_and_decides_rag():
    state = run_scenario("S14")
    refs = evidence_refs(state)

    assert state["request_type"] == "reception_plan_upload"
    assert state["risk_precheck"]["level"] == "high"
    assert state["permission_context"]["permission_status"] == "allowed"
    assert state["audit_context"]["audit_status"] == "created"

    assert "PERMISSION-CHECK-RECEPTION-UPLOAD-0001" in refs
    assert "AUDIT-LOG-RECEPTION-UPLOAD-0001" in refs
    assert "FILE-UPLOAD-SESSION-0001" in refs
    assert "FILE-SCAN-RESULT-0001" in refs
    assert "FILE-CLASSIFY-RECEPTION-0001" in refs
    assert "FILE-ACTION-ITEMS-0001" in refs
    assert "ADMIN-RECEPTION-UPDATE-0001" in refs
    assert "TASK-RESULT-CREATE-BATCH-0001" in refs
    assert "NOTIFY-RESULT-RECEPTION-TASKS-0001" in refs
    assert "RAG-INGESTION-DECISION-0001" in refs

    assert_node_before(state, "business_router_node", "permission_audit_node")
    assert_node_before(state, "permission_audit_node", "file_processing_node")
    assert_node_before(state, "file_processing_node", "reception_update_node")
    assert_node_before(state, "reception_update_node", "create_action_item_tasks_node")
    assert_node_before(state, "create_action_item_tasks_node", "notification_node")
    assert_node_before(state, "notification_node", "rag_ingestion_decision_node")
    assert_node_before(state, "rag_ingestion_decision_node", "trace_integrity_node")

    file_context = state["domain_context"]["file_processing"]
    assert file_context["classification"]["business_domain"] == "important_reception"
    assert file_context["classification"]["sensitivity_level"] == "high"
    assert len(file_context["action_items"]) == 2

    tasks = state["domain_context"]["action_item_tasks"]
    assert tasks["created_count"] == 2
    assert tasks["batch_id"] == "TASK-BATCH-RECEPTION-0001"

    notification = state["domain_context"]["notification"]
    assert notification["status"] == "sent"
    assert notification["recipient_count"] == 2

    rag_decision = state["domain_context"]["rag_ingestion"]
    assert rag_decision["rag_ingestion_status"] == "skipped_by_policy"

    assert "task_completed" not in state["final_response"]
    assert "generic_rag_ingested" not in state["final_response"]
    assert "TASK-BATCH-RECEPTION-0001" in state["final_response"]
    assert "skipped_by_policy" in state["final_response"]
