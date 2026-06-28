from concurrent.futures import ThreadPoolExecutor

from langgraph.checkpoint.memory import InMemorySaver

from office_agent.checkpointing import JsonCheckpointStore
from office_agent.graph import (
    resume_project_inquiry_thread_from_native_checkpoint,
    start_project_inquiry_thread,
)
from office_agent.langgraph_checkpointing import (
    DEFAULT_PROJECT_INQUIRY_CHECKPOINT_NS,
    LANGGRAPH_ROOT_CHECKPOINT_NS,
    latest_native_checkpoint_tuple,
    load_native_checkpoint_state,
    make_langgraph_thread_config,
    save_native_checkpoint_state,
)


def evidence_refs(state):
    return [item["evidence_ref"] for item in state.get("evidence_refs", [])]


def trace_actions(state):
    return [event["action"] for event in state.get("trace_events", [])]


def owner_reply_event(state):
    inquiry = state["domain_context"]["project_inquiry"]
    owner = state["domain_context"]["project_owner"]
    return {
        "inquiry_id": inquiry["inquiry_id"],
        "responder_id": owner["owner_id"],
        "reply_summary": "native-checkpoint-resume-reply",
        "reply_sensitivity_level": "confidential",
    }


def test_langgraph_thread_config_maps_thread_namespace_and_metadata():
    config = make_langgraph_thread_config(
        "THREAD-S15-CUST-A",
        metadata={"scenario_id": "S15"},
    )

    assert config["configurable"]["thread_id"] == "THREAD-S15-CUST-A"
    assert (
        config["configurable"]["checkpoint_ns"]
        == LANGGRAPH_ROOT_CHECKPOINT_NS
    )
    assert config["metadata"]["scenario_id"] == "S15"
    assert config["metadata"]["checkpoint_scope"] == "project_inquiry_waiting_state"
    assert (
        config["metadata"]["project_checkpoint_ns"]
        == DEFAULT_PROJECT_INQUIRY_CHECKPOINT_NS
    )


def test_s15_thread_start_records_native_checkpoint_metadata(tmp_path):
    business_store = JsonCheckpointStore(tmp_path)
    native_checkpointer = InMemorySaver()

    state = start_project_inquiry_thread(
        "S15",
        checkpoint_store=business_store,
        thread_id="THREAD-S15-CUST-A",
        native_checkpointer=native_checkpointer,
    )

    latest = latest_native_checkpoint_tuple(
        native_checkpointer,
        "THREAD-S15-CUST-A",
    )

    assert latest is not None
    assert latest.config["configurable"]["thread_id"] == "THREAD-S15-CUST-A"
    assert (
        latest.config["configurable"]["checkpoint_ns"]
        == LANGGRAPH_ROOT_CHECKPOINT_NS
    )
    assert state["checkpoint_context"]["native_checkpoint"] == {
        "provider": "langgraph",
        "thread_id": "THREAD-S15-CUST-A",
        "checkpoint_ns": LANGGRAPH_ROOT_CHECKPOINT_NS,
        "project_checkpoint_ns": DEFAULT_PROJECT_INQUIRY_CHECKPOINT_NS,
        "checkpoint_id": latest.config["configurable"]["checkpoint_id"],
    }
    assert "native_checkpoint_saved" in trace_actions(state)
    assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(state)


def test_native_checkpoints_are_isolated_by_thread_id(tmp_path):
    business_store = JsonCheckpointStore(tmp_path)
    native_checkpointer = InMemorySaver()

    first = start_project_inquiry_thread(
        "S15",
        checkpoint_store=business_store,
        thread_id="THREAD-S15-CUST-A",
        native_checkpointer=native_checkpointer,
    )
    second = start_project_inquiry_thread(
        "S15",
        checkpoint_store=business_store,
        thread_id="THREAD-S15-CUST-B",
        request_input={
            "scenario_id": "S15",
            "user_input": "project inquiry for customer B",
            "operator": {"employee_id": "EMP-S15-4002", "name": "Project Member B"},
            "business_object": {
                "project_id": "PROJ-CUST-B",
                "question": "Does customer B need a milestone update?",
                "question_type": "major_milestone",
            },
        },
        native_checkpointer=native_checkpointer,
    )

    first_latest = latest_native_checkpoint_tuple(
        native_checkpointer,
        "THREAD-S15-CUST-A",
    )
    second_latest = latest_native_checkpoint_tuple(
        native_checkpointer,
        "THREAD-S15-CUST-B",
    )

    assert first_latest is not None
    assert second_latest is not None
    assert (
        first["checkpoint_context"]["native_checkpoint"]["checkpoint_id"]
        == first_latest.config["configurable"]["checkpoint_id"]
    )
    assert (
        second["checkpoint_context"]["native_checkpoint"]["checkpoint_id"]
        == second_latest.config["configurable"]["checkpoint_id"]
    )
    assert first["thread_id"] != second["thread_id"]
    assert first["domain_context"]["project_inquiry"]["project_id"] == "PROJ-CUST-A"
    assert second["domain_context"]["project_inquiry"]["project_id"] == "PROJ-CUST-B"


def test_native_checkpoint_state_can_be_loaded_by_thread_id(tmp_path):
    business_store = JsonCheckpointStore(tmp_path)
    native_checkpointer = InMemorySaver()
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=business_store,
        thread_id="THREAD-S15-CUST-A",
        native_checkpointer=native_checkpointer,
    )

    loaded = load_native_checkpoint_state(native_checkpointer, "THREAD-S15-CUST-A")

    assert loaded["thread_id"] == waiting["thread_id"]
    assert loaded["waiting_for"] == "project_owner_reply"
    assert loaded["checkpoint_context"]["status"] == "ready_for_resume"
    assert (
        loaded["domain_context"]["project_inquiry"]["inquiry_id"]
        == waiting["domain_context"]["project_inquiry"]["inquiry_id"]
    )


def test_native_checkpoint_resume_completes_and_updates_native_state(tmp_path):
    business_store = JsonCheckpointStore(tmp_path)
    native_checkpointer = InMemorySaver()
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=business_store,
        thread_id="THREAD-S15-CUST-A",
        native_checkpointer=native_checkpointer,
    )

    resumed = resume_project_inquiry_thread_from_native_checkpoint(
        "THREAD-S15-CUST-A",
        owner_reply_event(waiting),
        native_checkpointer=native_checkpointer,
    )
    latest = load_native_checkpoint_state(native_checkpointer, "THREAD-S15-CUST-A")

    assert resumed["waiting_for"] is None
    assert resumed["checkpoint_context"]["status"] == "resumed"
    assert latest["checkpoint_context"]["status"] == "resumed"
    assert "PROJECT-INQUIRY-REPLY-0001" in evidence_refs(resumed)
    assert "TASK-RESULT-COMPLETE-INQUIRY-0001" in evidence_refs(resumed)
    assert "PROJECT-RAG-INGESTION-DECISION-0001" in evidence_refs(resumed)
    assert "native_checkpoint_loaded" in trace_actions(resumed)
    assert "native_checkpoint_resumed" in trace_actions(resumed)


def test_native_checkpoint_resume_replay_routes_to_manual_review(tmp_path):
    business_store = JsonCheckpointStore(tmp_path)
    native_checkpointer = InMemorySaver()
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=business_store,
        thread_id="THREAD-S15-CUST-A",
        native_checkpointer=native_checkpointer,
    )
    reply = owner_reply_event(waiting)

    first = resume_project_inquiry_thread_from_native_checkpoint(
        "THREAD-S15-CUST-A",
        reply,
        native_checkpointer=native_checkpointer,
    )
    replay = resume_project_inquiry_thread_from_native_checkpoint(
        "THREAD-S15-CUST-A",
        reply,
        native_checkpointer=native_checkpointer,
    )

    assert first["checkpoint_context"]["status"] == "resumed"
    assert replay["blocked_reason"] == "native_checkpoint_already_resumed"
    assert replay["next_action"]["type"] == "manual_review"
    assert evidence_refs(replay).count("PROJECT-INQUIRY-REPLY-0001") == 1
    assert trace_actions(replay).count("owner_reply_recorded") == 1
    assert "native_checkpoint_resume_rejected" in trace_actions(replay)


def test_native_checkpoint_resume_missing_thread_routes_to_manual_review():
    native_checkpointer = InMemorySaver()

    resumed = resume_project_inquiry_thread_from_native_checkpoint(
        "THREAD-MISSING",
        {
            "inquiry_id": "INQ-PROJ-CUST-A-0001",
            "responder_id": "EMP-6001",
            "reply_summary": "late reply",
            "reply_sensitivity_level": "confidential",
        },
        native_checkpointer=native_checkpointer,
    )

    assert resumed["blocked_reason"] == "native_checkpoint_not_found"
    assert resumed["next_action"]["type"] == "manual_review"
    assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(resumed)
    assert "native_checkpoint_resume_rejected" in trace_actions(resumed)


def test_native_checkpoint_resume_invalid_waiting_state_routes_to_manual_review(
    tmp_path,
):
    business_store = JsonCheckpointStore(tmp_path)
    native_checkpointer = InMemorySaver()
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=business_store,
        thread_id="THREAD-S15-CUST-A",
        native_checkpointer=native_checkpointer,
    )
    bad_state = dict(load_native_checkpoint_state(native_checkpointer, "THREAD-S15-CUST-A"))
    bad_state["waiting_for"] = None
    save_native_checkpoint_state(native_checkpointer, "THREAD-S15-CUST-A", bad_state)

    resumed = resume_project_inquiry_thread_from_native_checkpoint(
        "THREAD-S15-CUST-A",
        owner_reply_event(waiting),
        native_checkpointer=native_checkpointer,
    )

    assert resumed["blocked_reason"] == "invalid_native_checkpoint_waiting_state"
    assert resumed["next_action"]["type"] == "manual_review"
    assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(resumed)
    assert "native_checkpoint_resume_rejected" in trace_actions(resumed)


def test_native_checkpoint_concurrent_same_thread_resume_allows_one_success(
    tmp_path,
):
    business_store = JsonCheckpointStore(tmp_path)
    native_checkpointer = InMemorySaver()
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=business_store,
        thread_id="THREAD-S15-CUST-A",
        native_checkpointer=native_checkpointer,
    )
    replies = []
    for index in range(5):
        reply = owner_reply_event(waiting)
        reply["reply_summary"] = f"native-concurrent-reply-{index}"
        replies.append(reply)

    with ThreadPoolExecutor(max_workers=5) as executor:
        states = list(
            executor.map(
                lambda reply: resume_project_inquiry_thread_from_native_checkpoint(
                    "THREAD-S15-CUST-A",
                    reply,
                    native_checkpointer=native_checkpointer,
                ),
                replies,
            )
        )

    successful = [
        state
        for state in states
        if state.get("checkpoint_context", {}).get("status") == "resumed"
        and not state.get("blocked_reason")
    ]
    rejected = [
        state
        for state in states
        if state.get("blocked_reason") == "native_checkpoint_already_resumed"
    ]
    latest = load_native_checkpoint_state(native_checkpointer, "THREAD-S15-CUST-A")

    assert len(successful) == 1
    assert len(rejected) == 4
    assert latest["checkpoint_context"]["status"] == "resumed"
    assert evidence_refs(latest).count("PROJECT-INQUIRY-REPLY-0001") == 1
    for state in rejected:
        assert state["next_action"]["type"] == "manual_review"
        assert evidence_refs(state).count("PROJECT-INQUIRY-REPLY-0001") == 1
        assert trace_actions(state).count("owner_reply_recorded") == 1
