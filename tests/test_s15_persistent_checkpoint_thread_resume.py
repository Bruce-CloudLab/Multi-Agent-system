from office_agent.checkpointing import JsonCheckpointStore
from office_agent.graph import (
    resume_project_inquiry_thread,
    start_project_inquiry_thread,
)


def evidence_refs(state):
    return [item["evidence_ref"] for item in state.get("evidence_refs", [])]


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def owner_reply_event(state):
    inquiry = state["domain_context"]["project_inquiry"]
    owner = state["domain_context"]["project_owner"]
    return {
        "inquiry_id": inquiry["inquiry_id"],
        "responder_id": owner["owner_id"],
        "reply_summary": "checkpoint-thread-resume-reply",
        "reply_sensitivity_level": "confidential",
    }


def test_s15_thread_start_persists_waiting_checkpoint_by_thread_id(tmp_path):
    store = JsonCheckpointStore(tmp_path)
    state = start_project_inquiry_thread(
        "S15",
        checkpoint_store=store,
        thread_id="THREAD-S15-CUST-A",
    )
    loaded = store.load("THREAD-S15-CUST-A")

    assert state["thread_id"] == "THREAD-S15-CUST-A"
    assert state["waiting_for"] == "project_owner_reply"
    assert state["checkpoint_context"]["status"] == "ready_for_resume"
    assert (
        loaded["checkpoint_context"]["checkpoint_id"]
        == state["checkpoint_context"]["checkpoint_id"]
    )
    assert (
        loaded["domain_context"]["project_inquiry"]["inquiry_id"]
        == "INQ-PROJ-CUST-A-0001"
    )
    assert "checkpoint_waiting_state_node" in trace_nodes(loaded)
    assert "checkpoint_store" in trace_nodes(loaded)
    assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(loaded)


def test_s15_thread_resume_loads_checkpoint_and_marks_resumed(tmp_path):
    store = JsonCheckpointStore(tmp_path)
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=store,
        thread_id="THREAD-S15-CUST-A",
    )

    resumed = resume_project_inquiry_thread(
        "THREAD-S15-CUST-A",
        owner_reply_event(waiting),
        checkpoint_store=store,
    )
    loaded_after_resume = store.load("THREAD-S15-CUST-A")

    assert resumed["waiting_for"] is None
    assert resumed["checkpoint_context"]["status"] == "resumed"
    assert loaded_after_resume["checkpoint_context"]["status"] == "resumed"
    assert "checkpoint_store" in trace_nodes(resumed)
    assert "validate_project_inquiry_resume_node" in trace_nodes(resumed)
    assert "PROJECT-INQUIRY-REPLY-0001" in evidence_refs(resumed)
    assert "TASK-RESULT-COMPLETE-INQUIRY-0001" in evidence_refs(resumed)
    assert "PROJECT-RAG-INGESTION-DECISION-0001" in evidence_refs(resumed)


def test_s15_thread_resume_unknown_thread_routes_to_manual_review(tmp_path):
    store = JsonCheckpointStore(tmp_path)
    resumed = resume_project_inquiry_thread(
        "THREAD-MISSING",
        {
            "inquiry_id": "INQ-PROJ-CUST-A-0001",
            "responder_id": "EMP-6001",
            "reply_summary": "late reply",
            "reply_sensitivity_level": "confidential",
        },
        checkpoint_store=store,
    )

    assert resumed["blocked_reason"] == "checkpoint_not_found"
    assert resumed["next_action"]["type"] == "manual_review"
    assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(resumed)
    assert "checkpoint_store" in trace_nodes(resumed)
    assert "manual_review_node" in trace_nodes(resumed)


def test_s15_thread_resume_replay_routes_to_manual_review_without_duplicate_reply(
    tmp_path,
):
    store = JsonCheckpointStore(tmp_path)
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=store,
        thread_id="THREAD-S15-CUST-A",
    )
    reply = owner_reply_event(waiting)

    first = resume_project_inquiry_thread(
        "THREAD-S15-CUST-A",
        reply,
        checkpoint_store=store,
    )
    replay = resume_project_inquiry_thread(
        "THREAD-S15-CUST-A",
        reply,
        checkpoint_store=store,
    )

    assert first["checkpoint_context"]["status"] == "resumed"
    assert replay["blocked_reason"] == "checkpoint_already_resumed"
    assert replay["next_action"]["type"] == "manual_review"
    assert evidence_refs(replay).count("PROJECT-INQUIRY-REPLY-0001") == 1
    assert trace_nodes(replay).count("inquiry_add_reply_node") == 1


def test_s15_thread_resume_mismatched_reply_uses_validation_before_write(tmp_path):
    store = JsonCheckpointStore(tmp_path)
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=store,
        thread_id="THREAD-S15-CUST-A",
    )
    reply = owner_reply_event(waiting)
    reply["inquiry_id"] = "INQ-PROJ-OTHER-0001"

    resumed = resume_project_inquiry_thread(
        "THREAD-S15-CUST-A",
        reply,
        checkpoint_store=store,
    )

    assert resumed["blocked_reason"] == "owner_reply_inquiry_mismatch"
    assert resumed["resume_validation"]["status"] == "blocked"
    assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(resumed)
    assert "validate_project_inquiry_resume_node" in trace_nodes(resumed)
