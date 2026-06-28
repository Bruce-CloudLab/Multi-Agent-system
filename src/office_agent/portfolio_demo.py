from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from office_agent.checkpointing import JsonCheckpointStore
from office_agent.graph import (
    resume_project_inquiry_thread,
    run_scenario,
    start_project_inquiry_thread,
)


PORTFOLIO_CASES = ("S01", "S08", "S05", "S14")
S15_DEMO_THREAD_ID = "THREAD-PORTFOLIO-DEMO-S15"


CASE_CONCEPTS: dict[str, dict[str, str]] = {
    "S01": {
        "title": "S01 Repair",
        "capability": "Low-risk office request with direct tool evidence.",
        "node_focus": "Orchestrator classifies the request, then Admin handles the repair ticket.",
        "edge_focus": "entry -> orchestrator -> business router -> admin repair -> trace integrity -> final response",
        "conditional_edge_focus": "route_by_request_type selects admin_repair_node without permission/audit because risk=low.",
        "checkpoint_focus": "No checkpoint; the request completes synchronously.",
        "interrupt_focus": "No interrupt; no human wait state is needed.",
        "resume_focus": "No resume path.",
    },
    "S08": {
        "title": "S08 Policy Query",
        "capability": "RAG retrieval with a TruLens-style quality gate.",
        "node_focus": "Knowledge/RAG retrieves policy context, then rag_evaluation_node checks quality.",
        "edge_focus": "entry -> orchestrator -> business router -> rag policy -> rag evaluation -> trace integrity -> final response",
        "conditional_edge_focus": "route_after_rag_evaluation continues only when rag_quality_gate=passed.",
        "checkpoint_focus": "No checkpoint; the RAG answer is synchronous.",
        "interrupt_focus": "No interrupt; low-quality RAG would route to manual review.",
        "resume_focus": "No resume path.",
    },
    "S05": {
        "title": "S05 Reception Schedule",
        "capability": "High-risk read path with permission and audit before disclosure.",
        "node_focus": "Permission/Audit runs before Admin loads the reception schedule.",
        "edge_focus": "entry -> orchestrator -> identity -> business router -> permission/audit -> business router -> reception schedule -> final response",
        "conditional_edge_focus": "high-risk routing enters permission_audit_node before sensitive business execution.",
        "checkpoint_focus": "No checkpoint; the authorized read completes synchronously.",
        "interrupt_focus": "No interrupt unless identity or permission fails.",
        "resume_focus": "No resume path.",
    },
    "S14": {
        "title": "S14 Reception Plan Upload",
        "capability": "File processing, business update, task creation, notification, and RAG decision.",
        "node_focus": "File Processing, Admin, Task/Workflow, Notification, and RAG decision nodes cooperate.",
        "edge_focus": "permission/audit -> file processing -> reception update -> task creation -> notification -> RAG decision",
        "conditional_edge_focus": "high-risk write route requires permission/audit; RAG ingestion is decided by file classification.",
        "checkpoint_focus": "No checkpoint; this write workflow completes in one run.",
        "interrupt_focus": "No interrupt in the happy path.",
        "resume_focus": "No resume path.",
    },
    "S15-start": {
        "title": "S15 Project Inquiry Start",
        "capability": "Human-in-the-loop start path with project owner task and waiting checkpoint.",
        "node_focus": "Project and Task/Workflow nodes create the inquiry, task, notification, and wait state.",
        "edge_focus": "permission/audit -> project access -> owner lookup -> inquiry -> task -> notification -> wait -> checkpoint",
        "conditional_edge_focus": "owner notification must succeed before wait_for_owner_reply_node is reached.",
        "checkpoint_focus": "JsonCheckpointStore saves waiting State by thread_id.",
        "interrupt_focus": "waiting_for=project_owner_reply is the human boundary.",
        "resume_focus": "Resume has not run yet; owner reply evidence is absent.",
    },
    "S15-resume": {
        "title": "S15 Project Inquiry Resume",
        "capability": "Checkpoint resume with owner reply validation, task completion, and RAG decision.",
        "node_focus": "Resume validation runs before reply write-back and owner task completion.",
        "edge_focus": "checkpoint load -> resume validation -> add reply -> complete task -> project RAG decision -> final response",
        "conditional_edge_focus": "route_after_project_inquiry_resume_validation blocks mismatched or stale reply events.",
        "checkpoint_focus": "checkpoint_context.status becomes resumed after successful continuation.",
        "interrupt_focus": "waiting_for is cleared after the owner reply is recorded.",
        "resume_focus": "owner_reply_event resumes the saved project inquiry State.",
    },
}


def evidence_refs(state: dict[str, Any]) -> list[str]:
    return [item["evidence_ref"] for item in state.get("evidence_refs", [])]


def trace_nodes(state: dict[str, Any]) -> list[str]:
    return [event.get("node", "unknown_node") for event in state.get("trace_events", [])]


def gate_checks(state: dict[str, Any]) -> list[str]:
    checks = []
    for gate in state.get("gate_checks", []):
        gate_name = gate.get("gate", "unknown_gate")
        status = gate.get("status", "unknown")
        checks.append(f"{gate_name}={status}")
    return checks


def _evidence_text(state: dict[str, Any]) -> str:
    refs = evidence_refs(state)
    return ", ".join(refs) if refs else "none"


def display_response_for_case(case_id: str, state: dict[str, Any]) -> str:
    context = state.get("domain_context", {})
    evidence = _evidence_text(state)

    if case_id == "S01":
        repair = context.get("repair", {})
        ticket_id = repair.get("ticket_id", "unknown_ticket")
        return (
            f"Repair ticket {ticket_id} was created. "
            f"Business evidence: {evidence}."
        )

    if case_id == "S08":
        policy = context.get("policy_query", {})
        source_doc = policy.get("source_doc", "unknown_policy_doc")
        return (
            "The travel reimbursement policy answer is supported by "
            f"RAG-POLICY-RESULT-0001 from {source_doc}. "
            "The RAG quality gate passed; RAG-EVAL-POLICY-0001 is quality "
            "metadata, not business evidence."
        )

    if case_id == "S05":
        schedule = context.get("reception_schedule", {})
        reception_id = schedule.get("reception_id", "unknown_reception")
        time_window = schedule.get("time_window", "unknown_time")
        location = schedule.get("location", "controlled_location")
        return (
            "Permission and audit passed before the reception schedule was "
            f"disclosed. Reception {reception_id} is scheduled for "
            f"{time_window} at {location}. Business evidence: {evidence}."
        )

    if case_id == "S14":
        update = context.get("reception_update", {})
        tasks = context.get("action_item_tasks", {})
        notification = context.get("notification", {})
        rag = context.get("rag_ingestion", {})
        return (
            "The reception plan upload completed through file processing, "
            f"business update {update.get('update_id', 'unknown_update')}, "
            f"{tasks.get('created_count', 0)} task creations, notification "
            f"{notification.get('notification_id', 'unknown_notification')}, "
            "and a RAG ingestion decision of "
            f"{rag.get('rag_ingestion_status', 'unknown')}. "
            f"Business evidence: {evidence}."
        )

    if case_id == "S15-start":
        inquiry = context.get("project_inquiry", {})
        task = context.get("project_inquiry_task", {})
        notification = context.get("project_inquiry_notification", {})
        waiting_for = state.get("waiting_for", "unknown_wait")
        return (
            f"Project inquiry {inquiry.get('inquiry_id', 'unknown_inquiry')} "
            f"created owner task {task.get('task_id', 'unknown_task')} and "
            f"sent notification {notification.get('notification_id', 'unknown_notification')}. "
            f"The graph is interrupted at waiting_for={waiting_for}. "
            f"Business evidence: {evidence}."
        )

    if case_id == "S15-resume":
        inquiry = context.get("project_inquiry", {})
        task = context.get("project_inquiry_task", {})
        rag = context.get("project_rag_ingestion", {})
        return (
            "The owner reply was recorded for inquiry "
            f"{inquiry.get('inquiry_id', 'unknown_inquiry')}; owner task "
            f"{task.get('task_id', 'unknown_task')} was completed; project "
            "reply RAG ingestion status is "
            f"{rag.get('rag_ingestion_status', 'unknown')}. "
            f"Business evidence: {evidence}."
        )

    raw_response = state.get("final_response", "")
    return raw_response or "No display response is available for this case."


def display_response_zh_for_case(case_id: str, state: dict[str, Any]) -> str:
    context = state.get("domain_context", {})
    evidence = _evidence_text(state)

    if case_id == "S01":
        repair = context.get("repair", {})
        ticket_id = repair.get("ticket_id", "unknown_ticket")
        return f"已创建报修工单 {ticket_id}。业务证据：{evidence}。"

    if case_id == "S08":
        policy = context.get("policy_query", {})
        source_doc = policy.get("source_doc", "unknown_policy_doc")
        return (
            "差旅报销政策回答由 "
            f"{source_doc} 中的 RAG-POLICY-RESULT-0001 支撑。"
            "RAG 质量门禁已通过；RAG-EVAL-POLICY-0001 是质量评估元数据，"
            "不是业务证据。"
        )

    if case_id == "S05":
        schedule = context.get("reception_schedule", {})
        reception_id = schedule.get("reception_id", "unknown_reception")
        time_window = schedule.get("time_window", "unknown_time")
        location = schedule.get("location", "controlled_location")
        return (
            "系统先通过权限校验和审计，再披露重要接待安排。"
            f"接待 {reception_id} 的时间为 {time_window}，地点为 {location}。"
            f"业务证据：{evidence}。"
        )

    if case_id == "S14":
        update = context.get("reception_update", {})
        tasks = context.get("action_item_tasks", {})
        notification = context.get("notification", {})
        rag = context.get("rag_ingestion", {})
        return (
            "接待方案上传已完成文件处理、业务更新、待办创建、通知和 RAG 入库判断。"
            f"更新记录为 {update.get('update_id', 'unknown_update')}，"
            f"创建待办 {tasks.get('created_count', 0)} 个，"
            f"通知编号 {notification.get('notification_id', 'unknown_notification')}，"
            f"RAG 入库状态为 {rag.get('rag_ingestion_status', 'unknown')}。"
            f"业务证据：{evidence}。"
        )

    if case_id == "S15-start":
        inquiry = context.get("project_inquiry", {})
        task = context.get("project_inquiry_task", {})
        notification = context.get("project_inquiry_notification", {})
        waiting_for = state.get("waiting_for", "unknown_wait")
        return (
            f"已创建项目问询 {inquiry.get('inquiry_id', 'unknown_inquiry')}，"
            f"并为负责人创建待办 {task.get('task_id', 'unknown_task')}，"
            f"发送通知 {notification.get('notification_id', 'unknown_notification')}。"
            f"图执行在 waiting_for={waiting_for} 处中断，等待负责人回复。"
            f"业务证据：{evidence}。"
        )

    if case_id == "S15-resume":
        inquiry = context.get("project_inquiry", {})
        task = context.get("project_inquiry_task", {})
        rag = context.get("project_rag_ingestion", {})
        return (
            "负责人回复已写回问询 "
            f"{inquiry.get('inquiry_id', 'unknown_inquiry')}；"
            f"负责人待办 {task.get('task_id', 'unknown_task')} 已完成；"
            "项目回复的 RAG 入库状态为 "
            f"{rag.get('rag_ingestion_status', 'unknown')}。"
            f"业务证据：{evidence}。"
        )

    raw_response = state.get("final_response", "")
    return raw_response or "没有可展示的中文回复。"


def summarize_state(case_id: str, state: dict[str, Any]) -> dict[str, Any]:
    concepts = CASE_CONCEPTS[case_id]
    checkpoint_context = state.get("checkpoint_context", {})
    risk = state.get("risk_precheck", {}).get("level", "unknown")
    waiting_for = state.get("waiting_for")
    raw_final_response = state.get("final_response", "")
    display_response = display_response_for_case(case_id, state)
    display_response_zh = display_response_zh_for_case(case_id, state)
    return {
        "case_id": case_id,
        "title": concepts["title"],
        "capability": concepts["capability"],
        "request_type": state.get("request_type", "unknown"),
        "risk_level": risk,
        "waiting_for": waiting_for,
        "checkpoint_status": checkpoint_context.get("status", "none"),
        "trace_nodes": trace_nodes(state),
        "trace_event_count": len(state.get("trace_events", [])),
        "evidence_refs": evidence_refs(state),
        "gate_checks": gate_checks(state),
        "state_focus": (
            f"request_type={state.get('request_type', 'unknown')}; "
            f"risk={risk}; waiting_for={waiting_for or 'none'}; "
            f"checkpoint_status={checkpoint_context.get('status', 'none')}"
        ),
        "node_focus": concepts["node_focus"],
        "edge_focus": concepts["edge_focus"],
        "conditional_edge_focus": concepts["conditional_edge_focus"],
        "checkpoint_focus": concepts["checkpoint_focus"],
        "interrupt_focus": concepts["interrupt_focus"],
        "resume_focus": concepts["resume_focus"],
        "display_response": display_response,
        "display_response_zh": display_response_zh,
        "display_locale": "zh-CN",
        "raw_final_response": raw_final_response,
        "final_response": display_response,
    }


def owner_reply_event_from_waiting_state(state: dict[str, Any]) -> dict[str, Any]:
    inquiry = state["domain_context"]["project_inquiry"]
    owner = state["domain_context"]["project_owner"]
    return {
        "inquiry_id": inquiry["inquiry_id"],
        "responder_id": owner["owner_id"],
        "reply_summary": "portfolio-demo-owner-reply",
        "reply_sensitivity_level": "confidential",
    }


def _run_portfolio_demo_with_checkpoint_root(checkpoint_root: Path) -> list[dict[str, Any]]:
    summaries = [
        summarize_state(scenario_id, run_scenario(scenario_id))
        for scenario_id in PORTFOLIO_CASES
    ]

    checkpoint_store = JsonCheckpointStore(checkpoint_root / "s15")
    waiting = start_project_inquiry_thread(
        "S15",
        checkpoint_store=checkpoint_store,
        thread_id=S15_DEMO_THREAD_ID,
    )
    resumed = resume_project_inquiry_thread(
        S15_DEMO_THREAD_ID,
        owner_reply_event_from_waiting_state(waiting),
        checkpoint_store=checkpoint_store,
    )

    summaries.append(summarize_state("S15-start", waiting))
    summaries.append(summarize_state("S15-resume", resumed))
    return summaries


def run_portfolio_demo(checkpoint_dir: str | Path | None = None) -> list[dict[str, Any]]:
    if checkpoint_dir is not None:
        checkpoint_root = Path(checkpoint_dir)
        checkpoint_root.mkdir(parents=True, exist_ok=True)
        return _run_portfolio_demo_with_checkpoint_root(checkpoint_root)

    with TemporaryDirectory(prefix="office-agent-portfolio-demo-") as temp_dir:
        return _run_portfolio_demo_with_checkpoint_root(Path(temp_dir))


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _format_node_path(nodes: list[str]) -> str:
    return " -> ".join(nodes) if nodes else "none"


def render_demo_report(summaries: list[dict[str, Any]]) -> str:
    lines = [
        "Enterprise Office Agent Demo Harness",
        "Runtime: LangGraph + mock Tool/API/RAG evidence + checkpoint resume",
        "",
    ]
    for summary in summaries:
        lines.extend(
            [
                f"=== {summary['title']} ===",
                f"Capability: {summary['capability']}",
                f"状态 State: {summary['state_focus']}",
                f"节点路径 Node Path: {_format_node_path(summary['trace_nodes'])}",
                f"边 Edge: {summary['edge_focus']}",
                f"条件边 Conditional Edge: {summary['conditional_edge_focus']}",
                f"检查点 Checkpoint: {summary['checkpoint_focus']}",
                f"中断 Interrupt: {summary['interrupt_focus']}",
                f"恢复 Resume: {summary['resume_focus']}",
                f"轨迹 Trace: {summary['trace_event_count']} events",
                f"证据 Evidence: {_format_list(summary['evidence_refs'])}",
                f"Gates: {_format_list(summary['gate_checks'])}",
                f"中文展示: {summary['display_response_zh']}",
                f"Display Response: {summary['display_response']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Enterprise Office Agent demo harness."
    )
    parser.add_argument(
        "--checkpoint-dir",
        help="Optional directory for S15 checkpoint files. Uses a temp dir by default.",
    )
    args = parser.parse_args(argv)

    summaries = run_portfolio_demo(checkpoint_dir=args.checkpoint_dir)
    print(render_demo_report(summaries), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
