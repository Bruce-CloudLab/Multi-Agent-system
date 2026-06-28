from __future__ import annotations

from typing import Any

from office_agent.scenarios import SCENARIOS


RUNNABLE_HINT = "可在本地运行台执行"
NOT_CONNECTED_HINT = "已设计，当前本地运行台未接入执行"


DESIGNED_SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "scenario_id": "S01",
        "title": "工位报修",
        "request_type": "repair",
        "risk_level": "low",
        "agent": "Admin Agent",
        "description": "低风险办公维修请求，直接调用 mock API 创建报修工单。",
    },
    {
        "scenario_id": "S02",
        "title": "薪资查询",
        "request_type": "salary_query",
        "risk_level": "high",
        "agent": "Permission/Audit Agent + HR Agent",
        "description": "高风险薪资信息读取，必须先经过身份、权限和审计。",
    },
    {
        "scenario_id": "S03",
        "title": "项目负责人联络",
        "request_type": "project_contact",
        "risk_level": "medium",
        "agent": "Project Agent + Task/Workflow Agent",
        "description": "中风险项目协作请求，设计上需要确认委托、负责人和通知结果。",
    },
    {
        "scenario_id": "S04",
        "title": "销假流程",
        "request_type": "leave_cancellation",
        "risk_level": "medium",
        "agent": "HR Agent + Task/Workflow Agent",
        "description": "中风险 HR 流程，查询请假记录和任务风险后提交销假。",
    },
    {
        "scenario_id": "S05",
        "title": "重要接待安排查询",
        "request_type": "reception_schedule",
        "risk_level": "high",
        "agent": "Permission/Audit Agent + Admin Agent",
        "description": "高风险接待信息读取，授权和审计通过后才披露安排。",
    },
    {
        "scenario_id": "S06",
        "title": "入职准备检查",
        "request_type": "onboarding_check",
        "risk_level": "medium",
        "agent": "HR Agent + IT Agent + Admin Agent",
        "description": "中风险多 Agent 协作场景，设计上检查账号、设备、工位和流程状态。",
    },
    {
        "scenario_id": "S07",
        "title": "VPN 登录支持",
        "request_type": "it_support",
        "risk_level": "low",
        "agent": "IT Agent",
        "description": "低风险 IT 支持请求，设计上检查账号状态并创建支持工单。",
    },
    {
        "scenario_id": "S08",
        "title": "差旅报销政策查询",
        "request_type": "policy_query",
        "risk_level": "low",
        "agent": "Knowledge/RAG Agent",
        "description": "低风险政策问答，使用 RAG 检索并通过质量门禁。",
    },
    {
        "scenario_id": "S09",
        "title": "会议纪要待办进展",
        "request_type": "meeting_task_query",
        "risk_level": "high",
        "agent": "Project Agent + Knowledge/RAG Agent + Task/Workflow Agent",
        "description": "高风险项目会议资料读取，设计上需要权限、RAG citation 和任务状态证据。",
    },
    {
        "scenario_id": "S10",
        "title": "项目共享文档访问",
        "request_type": "document_access",
        "risk_level": "high",
        "agent": "Project Agent + Knowledge/RAG Agent",
        "description": "高风险文档访问，设计上需要项目权限和文档敏感级别判断。",
    },
    {
        "scenario_id": "S11",
        "title": "会议室重排",
        "request_type": "meeting_reschedule",
        "risk_level": "medium",
        "agent": "Admin Agent + Task/Workflow Agent",
        "description": "中风险会议资源调整，设计上需要会议权限、可用房间和通知证据。",
    },
    {
        "scenario_id": "S12",
        "title": "财务付款交接",
        "request_type": "payment_handover",
        "risk_level": "high",
        "agent": "Permission/Audit Agent + Task/Workflow Agent + HR Agent",
        "description": "高风险付款流程查询，设计上只确认交接状态，不自动改派负责人。",
    },
    {
        "scenario_id": "S13",
        "title": "普通文件上传",
        "request_type": "file_upload",
        "risk_level": "medium",
        "agent": "File Processing Agent + Knowledge/RAG Agent",
        "description": "中风险写操作，设计上必须先完成上传会话、安全扫描和文件分类。",
    },
    {
        "scenario_id": "S14",
        "title": "重要接待方案上传",
        "request_type": "reception_plan_upload",
        "risk_level": "high",
        "agent": "File Processing Agent + Admin Agent + Task/Workflow Agent",
        "description": "高风险文件处理闭环，覆盖文件处理、接待更新、待办、通知和 RAG 决策。",
    },
    {
        "scenario_id": "S15",
        "title": "项目正式问询",
        "request_type": "project_inquiry",
        "risk_level": "medium/high",
        "agent": "Project Agent + Task/Workflow Agent + Knowledge/RAG Agent",
        "description": "人机协同项目问询，创建负责人待办并在 checkpoint 等待正式回复。",
    },
)


def scenario_catalog() -> list[dict[str, str]]:
    catalog = []
    for item in DESIGNED_SCENARIOS:
        scenario = dict(item)
        if scenario["scenario_id"] in SCENARIOS:
            scenario["status"] = "runnable"
            scenario["run_hint"] = RUNNABLE_HINT
        else:
            scenario["status"] = "not_connected"
            scenario["run_hint"] = NOT_CONNECTED_HINT
        catalog.append(scenario)
    return catalog


def scenario_catalog_payload(runtime: str, service: str) -> dict[str, Any]:
    scenarios = scenario_catalog()
    return {
        "runtime": runtime,
        "service": service,
        "total_count": len(scenarios),
        "runnable_count": sum(1 for item in scenarios if item["status"] == "runnable"),
        "scenarios": scenarios,
    }
