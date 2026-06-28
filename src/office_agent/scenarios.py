from __future__ import annotations

from typing import Any


SCENARIOS: dict[str, dict[str, Any]] = {
    "S01": {
        "scenario_id": "S01",
        "user_input": "工位上方的灯坏了，需要报修",
        "operator": {"employee_id": "EMP-1001", "name": "张三"},
    },
    "S02": {
        "scenario_id": "S02",
        "user_input": "员工想咨询下月的薪资",
        "operator": {
            "employee_id": "EMP-HR-PAY-0001",
            "name": "Test Payroll Reader",
            "roles": ["employee", "hr_staff", "payroll_reader"],
        },
    },
    "S05": {
        "scenario_id": "S05",
        "user_input": "公司今天有一场重要接待，领导想要查看具体的安排",
        "operator": {
            "employee_id": "EMP-9001",
            "name": "李经理",
            "roles": ["leader", "reception_viewer"],
        },
        "business_object": {"reception_id": "RECEPTION-20260627-AM"},
    },
    "S14": {
        "scenario_id": "S14",
        "user_input": "upload important reception itinerary and action plan",
        "operator": {
            "employee_id": "EMP-9001",
            "name": "Reception Admin",
            "roles": ["leader", "reception_admin"],
        },
        "business_object": {
            "reception_id": "RECEPTION-20260627-AM",
            "file_name": "reception-plan-client-a.pdf",
        },
    },
    "S15": {
        "scenario_id": "S15",
        "user_input": "我想问客户 A 项目的负责人，交付材料确认是否还需要补充附件。",
        "operator": {
            "employee_id": "EMP-1001",
            "name": "张三",
            "roles": ["project_member"],
        },
        "business_object": {
            "project_id": "PROJ-CUST-A",
            "question": "交付材料确认是否还需要补充附件？",
            "question_type": "customer_delivery",
        },
    },
    "S15_NOTIFICATION_FAILURE": {
        "scenario_id": "S15",
        "user_input": "我想问客户 A 项目的负责人，交付材料确认是否还需要补充附件。",
        "operator": {
            "employee_id": "EMP-1001",
            "name": "张三",
            "roles": ["project_member"],
        },
        "business_object": {
            "project_id": "PROJ-CUST-A",
            "question": "交付材料确认是否还需要补充附件？",
            "question_type": "customer_delivery",
            "simulate_project_notification_failure": True,
        },
    },
    "S08": {
        "scenario_id": "S08",
        "user_input": "员工想查询差旅报销制度",
        "operator": {"employee_id": "EMP-1001", "name": "张三"},
    },
    "S04": {
        "scenario_id": "S04",
        "user_input": "员工请假回来走销假流程",
        "operator": {"employee_id": "EMP-1001", "name": "张三"},
    },
}


def get_scenario_input(scenario_id: str) -> dict[str, Any]:
    try:
        return dict(SCENARIOS[scenario_id])
    except KeyError as exc:
        raise ValueError(f"Unsupported scenario_id: {scenario_id}") from exc
