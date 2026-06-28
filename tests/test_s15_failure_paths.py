from copy import deepcopy

from office_agent.graph import resume_project_inquiry_with_reply, run_scenario


def evidence_refs(state):
    return {item["evidence_ref"] for item in state.get("evidence_refs", [])}


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def base_reply_event(waiting_state):
    inquiry = waiting_state["domain_context"]["project_inquiry"]
    owner = waiting_state["domain_context"]["project_owner"]
    return {
        "inquiry_id": inquiry["inquiry_id"],
        "responder_id": owner["owner_id"],
        "reply_summary": "需要补充盖章版附件，电子版今天下班前上传即可。",
        "reply_sensitivity_level": "confidential",
    }


def test_s15_resume_inquiry_id_mismatch_routes_to_manual_review_without_reply_write():
    waiting_state = run_scenario("S15")
    reply_event = base_reply_event(waiting_state)
    reply_event["inquiry_id"] = "INQ-PROJ-OTHER-0001"

    resumed = resume_project_inquiry_with_reply(waiting_state, reply_event)
    refs = evidence_refs(resumed)

    assert resumed["blocked_reason"] == "owner_reply_inquiry_mismatch"
    assert resumed["next_action"]["type"] == "manual_review"
    assert resumed["resume_validation"]["status"] == "blocked"
    assert "人工复核" in resumed["final_response"]
    assert "PROJECT-INQUIRY-REPLY-0001" not in refs
    assert "TASK-RESULT-COMPLETE-INQUIRY-0001" not in refs
    assert "PROJECT-RAG-INGESTION-DECISION-0001" not in refs
    assert "inquiry_add_reply_node" not in trace_nodes(resumed)


def test_s15_resume_missing_reply_field_routes_to_manual_review():
    waiting_state = run_scenario("S15")
    reply_event = base_reply_event(waiting_state)
    del reply_event["reply_summary"]

    resumed = resume_project_inquiry_with_reply(waiting_state, reply_event)

    assert resumed["blocked_reason"] == "owner_reply_missing_required_field"
    assert resumed["resume_validation"]["missing_fields"] == ["reply_summary"]
    assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(resumed)
    assert "inquiry_add_reply_node" not in trace_nodes(resumed)


def test_s15_notification_failure_routes_to_manual_review_before_waiting():
    state = run_scenario("S15_NOTIFICATION_FAILURE")
    refs = evidence_refs(state)

    assert state["blocked_reason"] == "owner_notification_failed"
    assert state.get("waiting_for") != "project_owner_reply"
    assert state["next_action"]["type"] == "manual_review"
    assert "NOTIFY-RESULT-PROJECT-INQUIRY-FAILED-0001" in refs
    assert "NOTIFY-RESULT-PROJECT-INQUIRY-0001" not in refs
    assert "wait_for_owner_reply_node" not in trace_nodes(state)
    assert "人工复核" in state["final_response"]


def test_s15_owner_task_completion_failure_routes_to_manual_review_after_reply_write():
    waiting_state = run_scenario("S15")
    reply_event = base_reply_event(waiting_state)
    reply_event["simulate_task_completion_failure"] = True

    resumed = resume_project_inquiry_with_reply(waiting_state, reply_event)
    refs = evidence_refs(resumed)

    assert resumed["blocked_reason"] == "owner_task_completion_failed"
    assert resumed["next_action"]["type"] == "manual_review"
    assert "PROJECT-INQUIRY-REPLY-0001" in refs
    assert "TASK-RESULT-COMPLETE-INQUIRY-FAILED-0001" in refs
    assert "TASK-RESULT-COMPLETE-INQUIRY-0001" not in refs
    assert "PROJECT-RAG-INGESTION-DECISION-0001" not in refs
    assert "project_rag_ingestion_decision_node" not in trace_nodes(resumed)


def test_s15_stale_waiting_state_routes_to_manual_review_without_reply_write():
    waiting_state = deepcopy(run_scenario("S15"))
    waiting_state["interrupt_context"]["expires_at"] = "2026-06-27T10:00:00+08:00"
    reply_event = base_reply_event(waiting_state)
    reply_event["received_at"] = "2026-06-28T10:00:00+08:00"

    resumed = resume_project_inquiry_with_reply(waiting_state, reply_event)

    assert resumed["blocked_reason"] == "stale_project_owner_reply"
    assert resumed["resume_validation"]["status"] == "blocked"
    assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(resumed)
    assert "inquiry_add_reply_node" not in trace_nodes(resumed)
