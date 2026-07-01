from __future__ import annotations

from dataclasses import dataclass
from http.cookies import SimpleCookie
from secrets import token_urlsafe
from typing import Any


SESSION_COOKIE_NAME = "office_agent_session"


@dataclass(frozen=True)
class DemoUser:
    username: str
    password: str
    employee_id: str
    display_name: str
    department: str
    role_label: str
    default_prompt: str

    def public_profile(self) -> dict[str, str]:
        return {
            "username": self.username,
            "employee_id": self.employee_id,
            "display_name": self.display_name,
            "department": self.department,
            "role_label": self.role_label,
            "default_prompt": self.default_prompt,
        }


DEMO_USERS: dict[str, DemoUser] = {
    "it.demo": DemoUser(
        username="it.demo",
        password="demo123",
        employee_id="EMP-IT-DEV-0001",
        display_name="IT Developer Demo",
        department="IT Department",
        role_label="普通员工 / IT Developer",
        default_prompt="查一下我的工资",
    ),
    "hr.payroll": DemoUser(
        username="hr.payroll",
        password="demo123",
        employee_id="EMP-HR-PAY-0001",
        display_name="Payroll Reader Demo",
        department="HR Department",
        role_label="薪酬权限账号 / Payroll Reader",
        default_prompt="salary query request",
    ),
}

_SESSIONS: dict[str, str] = {}


def authenticate(username: str, password: str) -> DemoUser | None:
    user = DEMO_USERS.get(username)
    if user is None or user.password != password:
        return None
    return user


def create_session(user: DemoUser) -> str:
    token = token_urlsafe(32)
    _SESSIONS[token] = user.username
    return token


def clear_session(token: str | None) -> None:
    if token:
        _SESSIONS.pop(token, None)


def user_for_session(token: str | None) -> DemoUser | None:
    if not token:
        return None
    username = _SESSIONS.get(token)
    if not username:
        return None
    return DEMO_USERS.get(username)


def session_token_from_headers(headers: dict[str, str] | None) -> str | None:
    if not headers:
        return None
    cookie_header = headers.get("Cookie") or headers.get("cookie")
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    morsel = cookie.get(SESSION_COOKIE_NAME)
    return morsel.value if morsel else None


def current_user(headers: dict[str, str] | None) -> DemoUser | None:
    return user_for_session(session_token_from_headers(headers))


def session_cookie(token: str) -> str:
    return (
        f"{SESSION_COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Lax; "
        "Max-Age=28800"
    )


def expired_session_cookie() -> str:
    return (
        f"{SESSION_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; "
        "Max-Age=0"
    )


def public_demo_accounts() -> list[dict[str, Any]]:
    return [
        {
            "username": user.username,
            "password": user.password,
            "display_name": user.display_name,
            "employee_id": user.employee_id,
            "role_label": user.role_label,
        }
        for user in DEMO_USERS.values()
    ]
