from office_agent.checkpointing import JsonCheckpointStore
from office_agent.concurrency import (
    run_concurrent_project_inquiry_thread_resumes,
    run_concurrent_project_inquiry_thread_starts,
)
from office_agent.graph import start_project_inquiry_thread


def evidence_refs(state):
    return [item["evidence_ref"] for item in state.get("evidence_refs", [])]


def trace_nodes(state):
    return [event["node"] for event in state.get("trace_events", [])]


def s15_request(project_suffix, employee_id):
    project_id = f"PROJ-CUST-{project_suffix}"
    return {
        "scenario_id": "S15",
        "user_input": f"Ask project owner for {project_id}",
        "operator": {
            "employee_id": employee_id,
            "name": f"Project Member {project_suffix}",
            "roles": ["project_member"],
        },
        "business_object": {
            "project_id": project_id,
            "question": f"Does {project_id} need extra delivery attachments?",
            "question_type": "customer_delivery",
        },
    }


def thread_specs():
    return [
        {
            "thread_id": f"THREAD-S15-CUST-{suffix}",
            "scenario_id": "S15",
            "request_input": s15_request(suffix, f"EMP-10{index:02d}"),
        }
        for index, suffix in enumerate(["A", "B", "C", "D"], start=1)
    ]


def owner_reply_event(state, marker="checkpoint-concurrency-reply"):
    inquiry = state["domain_context"]["project_inquiry"]
    owner = state["domain_context"]["project_owner"]
    return {
        "inquiry_id": inquiry["inquiry_id"],
        "responder_id": owner["owner_id"],
        "reply_summary": f"{marker}-{inquiry['inquiry_id']}",
        "reply_sensitivity_level": "confidential",
    }


def assert_successful_results(results):
    assert [result["status"] for result in results] == ["success"] * len(results)
    assert [result["error"] for result in results] == [None] * len(results)


def assert_no_other_task_ids_in_final_response(states):
    task_ids = {
        state["domain_context"]["project_inquiry_task"]["task_id"]
        for state in states
    }
    for state in states:
        own_task_id = state["domain_context"]["project_inquiry_task"]["task_id"]
        other_task_ids = task_ids - {own_task_id}
        assert own_task_id in state["final_response"]
        for other_task_id in other_task_ids:
            assert other_task_id not in state["final_response"]


def test_concurrent_thread_starts_persist_isolated_checkpoints(tmp_path):
    store = JsonCheckpointStore(tmp_path)
    specs = thread_specs()

    results = run_concurrent_project_inquiry_thread_starts(
        specs,
        checkpoint_store=store,
        max_workers=4,
    )

    assert_successful_results(results)
    states = [result["state"] for result in results]
    assert_no_other_task_ids_in_final_response(states)

    for spec, state in zip(specs, states):
        thread_id = spec["thread_id"]
        expected_project_id = spec["request_input"]["business_object"]["project_id"]
        expected_inquiry_id = f"INQ-{expected_project_id}-0001"
        loaded = store.load(thread_id)

        assert state["thread_id"] == thread_id
        assert loaded["thread_id"] == thread_id
        assert state["waiting_for"] == "project_owner_reply"
        assert loaded["checkpoint_context"]["status"] == "ready_for_resume"
        assert (
            loaded["domain_context"]["project_inquiry"]["project_id"]
            == expected_project_id
        )
        assert (
            loaded["domain_context"]["project_inquiry"]["inquiry_id"]
            == expected_inquiry_id
        )
        assert loaded["checkpoint_context"]["inquiry_id"] == expected_inquiry_id
        assert "checkpoint_waiting_state_node" in trace_nodes(loaded)
        assert "checkpoint_store" in trace_nodes(loaded)
        assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(loaded)


def test_concurrent_thread_resumes_complete_isolated_threads(tmp_path):
    store = JsonCheckpointStore(tmp_path)
    starts = run_concurrent_project_inquiry_thread_starts(
        thread_specs(),
        checkpoint_store=store,
        max_workers=4,
    )
    waiting_states = [result["state"] for result in starts]
    thread_ids = [state["thread_id"] for state in waiting_states]
    reply_events = [owner_reply_event(state) for state in waiting_states]

    results = run_concurrent_project_inquiry_thread_resumes(
        thread_ids,
        reply_events,
        checkpoint_store=store,
        max_workers=4,
    )

    assert_successful_results(results)
    states = [result["state"] for result in results]
    assert_no_other_task_ids_in_final_response(states)

    for thread_id, reply_event, state in zip(thread_ids, reply_events, states):
        loaded = store.load(thread_id)
        refs = evidence_refs(state)

        assert state["waiting_for"] is None
        assert state["checkpoint_context"]["status"] == "resumed"
        assert loaded["checkpoint_context"]["status"] == "resumed"
        assert state["domain_context"]["project_inquiry"]["reply_summary"] == (
            reply_event["reply_summary"]
        )
        assert refs.count("PROJECT-INQUIRY-REPLY-0001") == 1
        assert "TASK-RESULT-COMPLETE-INQUIRY-0001" in refs
        assert "PROJECT-RAG-INGESTION-DECISION-0001" in refs
        assert "checkpoint_store" in trace_nodes(state)
        assert "validate_project_inquiry_resume_node" in trace_nodes(state)


def test_concurrent_same_thread_resume_allows_one_success_and_rejects_replays(
    tmp_path,
):
    store = JsonCheckpointStore(tmp_path)
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=store,
        thread_id="THREAD-S15-CUST-A",
        request_input=s15_request("A", "EMP-1001"),
    )
    reply_events = [
        owner_reply_event(waiting, marker=f"same-thread-reply-{index}")
        for index in range(5)
    ]

    results = run_concurrent_project_inquiry_thread_resumes(
        ["THREAD-S15-CUST-A"] * len(reply_events),
        reply_events,
        checkpoint_store=store,
        max_workers=5,
    )

    assert_successful_results(results)
    states = [result["state"] for result in results]
    successful = [
        state
        for state in states
        if state.get("checkpoint_context", {}).get("status") == "resumed"
        and not state.get("blocked_reason")
    ]
    rejected = [
        state
        for state in states
        if state.get("blocked_reason") == "checkpoint_already_resumed"
    ]
    loaded = store.load("THREAD-S15-CUST-A")

    assert len(successful) == 1
    assert len(rejected) == 4
    assert loaded["checkpoint_context"]["status"] == "resumed"
    assert evidence_refs(loaded).count("PROJECT-INQUIRY-REPLY-0001") == 1
    for state in rejected:
        assert state["next_action"]["type"] == "manual_review"
        assert evidence_refs(state).count("PROJECT-INQUIRY-REPLY-0001") == 1
        assert trace_nodes(state).count("inquiry_add_reply_node") == 1


def test_concurrent_thread_replays_do_not_duplicate_owner_reply_write_back(tmp_path):
    store = JsonCheckpointStore(tmp_path)
    starts = run_concurrent_project_inquiry_thread_starts(
        thread_specs(),
        checkpoint_store=store,
        max_workers=4,
    )
    waiting_states = [result["state"] for result in starts]
    thread_ids = [state["thread_id"] for state in waiting_states]
    reply_events = [owner_reply_event(state) for state in waiting_states]
    first_resume = run_concurrent_project_inquiry_thread_resumes(
        thread_ids,
        reply_events,
        checkpoint_store=store,
        max_workers=4,
    )
    assert_successful_results(first_resume)

    replay = run_concurrent_project_inquiry_thread_resumes(
        thread_ids,
        reply_events,
        checkpoint_store=store,
        max_workers=4,
    )

    assert_successful_results(replay)
    for result in replay:
        state = result["state"]
        assert state["blocked_reason"] == "checkpoint_already_resumed"
        assert state["next_action"]["type"] == "manual_review"
        assert evidence_refs(state).count("PROJECT-INQUIRY-REPLY-0001") == 1
        assert trace_nodes(state).count("inquiry_add_reply_node") == 1


def test_concurrent_thread_resumes_isolate_missing_checkpoint_failure(tmp_path):
    store = JsonCheckpointStore(tmp_path)
    starts = run_concurrent_project_inquiry_thread_starts(
        thread_specs()[:2],
        checkpoint_store=store,
        max_workers=2,
    )
    waiting_states = [result["state"] for result in starts]
    valid_thread_ids = [state["thread_id"] for state in waiting_states]
    valid_replies = [owner_reply_event(state) for state in waiting_states]
    missing_reply = {
        "inquiry_id": "INQ-PROJ-CUST-MISSING-0001",
        "responder_id": "EMP-MISSING",
        "reply_summary": "reply for missing checkpoint",
        "reply_sensitivity_level": "confidential",
    }

    results = run_concurrent_project_inquiry_thread_resumes(
        [valid_thread_ids[0], "THREAD-S15-MISSING", valid_thread_ids[1]],
        [valid_replies[0], missing_reply, valid_replies[1]],
        checkpoint_store=store,
        max_workers=3,
    )

    assert_successful_results(results)
    assert results[1]["state"]["blocked_reason"] == "checkpoint_not_found"
    assert results[1]["state"]["next_action"]["type"] == "manual_review"
    assert "PROJECT-INQUIRY-REPLY-0001" not in evidence_refs(results[1]["state"])
    for result in [results[0], results[2]]:
        state = result["state"]
        assert state["checkpoint_context"]["status"] == "resumed"
        assert state["blocked_reason"] != "checkpoint_not_found"
        assert evidence_refs(state).count("PROJECT-INQUIRY-REPLY-0001") == 1
