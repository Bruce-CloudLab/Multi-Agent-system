from office_agent.portfolio_demo import (
    main,
    render_demo_report,
    run_portfolio_demo,
)


def summary_by_case(summaries):
    return {summary["case_id"]: summary for summary in summaries}


def test_portfolio_demo_runs_curated_cases_in_order(tmp_path):
    summaries = run_portfolio_demo(checkpoint_dir=tmp_path)

    assert [summary["case_id"] for summary in summaries] == [
        "S01",
        "S08",
        "S05",
        "S14",
        "S15-start",
        "S15-resume",
    ]


def test_portfolio_demo_preserves_rag_evaluation_boundary(tmp_path):
    summaries = summary_by_case(run_portfolio_demo(checkpoint_dir=tmp_path))
    s08 = summaries["S08"]

    assert "display_response" in s08
    assert "display_response_zh" in s08
    assert s08["display_locale"] == "zh-CN"
    assert "raw_final_response" in s08
    assert "travel reimbursement policy" in s08["display_response"]
    assert "差旅报销政策" in s08["display_response_zh"]
    assert "RAG-POLICY-RESULT-0001" in s08["display_response"]
    assert "RAG-POLICY-RESULT-0001" in s08["display_response_zh"]
    assert "RAG-POLICY-RESULT-0001" in s08["evidence_refs"]
    assert "RAG-EVAL-POLICY-0001" not in s08["evidence_refs"]
    assert "rag_quality_gate=passed" in s08["gate_checks"]
    assert "rag_evaluation_node" in s08["trace_nodes"]


def test_portfolio_demo_shows_s15_checkpoint_interrupt_and_resume(tmp_path):
    summaries = summary_by_case(run_portfolio_demo(checkpoint_dir=tmp_path))
    waiting = summaries["S15-start"]
    resumed = summaries["S15-resume"]

    assert waiting["waiting_for"] == "project_owner_reply"
    assert waiting["checkpoint_status"] == "ready_for_resume"
    assert "PROJECT-INQUIRY-REPLY-0001" not in waiting["evidence_refs"]
    assert "checkpoint_store" in waiting["trace_nodes"]

    assert resumed["waiting_for"] is None
    assert resumed["checkpoint_status"] == "resumed"
    assert "PROJECT-INQUIRY-REPLY-0001" in resumed["evidence_refs"]
    assert "TASK-RESULT-COMPLETE-INQUIRY-0001" in resumed["evidence_refs"]
    assert "PROJECT-RAG-INGESTION-DECISION-0001" in resumed["evidence_refs"]
    assert "validate_project_inquiry_resume_node" in resumed["trace_nodes"]


def test_portfolio_demo_report_contains_langgraph_teaching_sections(tmp_path):
    report = render_demo_report(run_portfolio_demo(checkpoint_dir=tmp_path))

    assert "状态 State:" in report
    assert "节点路径 Node Path:" in report
    assert "边 Edge:" in report
    assert "条件边 Conditional Edge:" in report
    assert "检查点 Checkpoint:" in report
    assert "中断 Interrupt:" in report
    assert "恢复 Resume:" in report
    assert "轨迹 Trace:" in report
    assert "证据 Evidence:" in report
    assert "中文展示:" in report
    assert "Display Response:" in report
    assert "S15 Project Inquiry Resume" in report


def test_portfolio_demo_report_uses_readable_display_responses(tmp_path):
    report = render_demo_report(run_portfolio_demo(checkpoint_dir=tmp_path))

    assert "已创建报修工单 ADMIN-REPAIR-0001" in report
    assert "差旅报销政策" in report
    assert "负责人回复已写回问询 INQ-PROJ-CUST-A-0001" in report
    assert "Repair ticket ADMIN-REPAIR-0001 was created" in report
    assert "travel reimbursement policy" in report
    assert "owner reply was recorded for inquiry INQ-PROJ-CUST-A-0001" in report
    assert "宸" not in report
    assert "鏍" not in report
    assert "绱" not in report


def test_portfolio_demo_cli_prints_report(tmp_path, capsys):
    exit_code = main(["--checkpoint-dir", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Enterprise Office Agent Demo Harness" in captured.out
    assert "S08 Policy Query" in captured.out
    assert "S15 Project Inquiry Resume" in captured.out
