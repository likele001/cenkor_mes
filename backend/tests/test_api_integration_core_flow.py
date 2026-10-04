# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""HTTP 层核心闭环集成测试（QA-1 测试脚手架 + QA-2 核心闭环回归）

与 `test_core_flow.py`（直接调用 crud/service 函数）互补：本文件通过 FastAPI
`TestClient` 真实驱动「路由挂载 → JWT 鉴权 → RBAC 权限查询 → service/crud → 全局
异常/响应信封」全链路，覆盖此前**零覆盖**的 API 装配层。

它专门守住这类回归：
- 路由未挂载 / 前缀改动（历史上线时靠 {code:401} 人工验证，这里自动化）
- 鉴权失效（未登录必须返回业务码 401，而非 500/放行）
- RBAC 配置错误（`require_permissions` 权限点缺失必须 403 拦截）
- 报工审核闭环在 HTTP 层是否真正生成工资 + 追溯码

约定：本项目全局异常处理器恒返回 HTTP 200，业务码放在 body 的 `code` 字段，
故所有断言针对 `resp.json()["code"]` 而非 `resp.status_code`。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
from app.crud.report import create_report
from app.models.permission import Permission
from app.models.role import role_permissions

BASE = "/api/admin/production/reports"


# ── HTTP 测试脚手架 ──

@pytest.fixture(scope="session")
def engine():
    """覆盖 conftest 默认引擎：`:memory:` + StaticPool + check_same_thread=False。

    TestClient 在 worker 线程中运行 ASGI app，默认 SQLite 连接禁止跨线程复用会报
    ProgrammingError（`user.roles` 懒加载处触发）。此处仅对本文件的用例生效，
    不改动全局 fixtures。表结构与 conftest 一致（依赖其 import 期已注册全部模型）。
    """
    from app.models.base import Base

    e = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(e, "connect")
    def _fk(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(e)
    return e


@pytest.fixture
def api(session):
    """把全局 get_db 指向当前测试事务 session。

    不使用 `with TestClient(...)`，从而**不触发 app 生命周期 startup 事件**
    （避免对真实 MySQL 建表 / seed）。仅覆盖 get_db；鉴权与权限走真实实现。
    """
    from app.main import app

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _auth(user) -> dict:
    """为真实用户签发合法 JWT，走完整解码链路。"""
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def _grant_report_audit(session, role):
    """给角色真实写入 report.audit 权限点（验证 RBAC 查询链路而非空覆盖）。"""
    p = Permission(code="report.audit", name="报工审核")
    session.add(p)
    session.flush()
    session.execute(
        role_permissions.insert().values(role_id=role.id, permission_id=p.id)
    )
    session.flush()


# ── 鉴权闸门 ──

def test_api_unauthenticated_returns_business_code_401(api):
    """未带 token：应被 get_current_user 拦截，业务码 401（非 500/放行）。"""
    resp = api.get(BASE)
    assert resp.status_code == 200  # 全局处理器统一 200
    assert resp.json()["code"] == 401


def test_api_invalid_token_returns_business_code_401(api, test_user):
    """伪造 / 失效 token：decode_token 抛错 → 业务码 401。"""
    resp = api.get(BASE, headers={"Authorization": "Bearer not-a-real-jwt"})
    assert resp.json()["code"] == 401


# ── RBAC 权限闸门 ──

def test_api_permission_denied_without_report_audit(api, test_user):
    """已登录但角色无 report.audit：路由级依赖必须 403 拦截。"""
    resp = api.get(BASE, headers=_auth(test_user))
    assert resp.json()["code"] == 403


def test_api_allowed_with_report_audit_seeded(api, session, admin_role, test_user):
    """真实种入 report.audit 权限点后，同一请求应通过鉴权+权限，返回 200 业务码。"""
    _grant_report_audit(session, admin_role)
    resp = api.get(BASE, headers=_auth(test_user))
    assert resp.json()["code"] == 200


# ── 报工审核闭环（真实走 HTTP：初审→终审→算薪） ──

def test_api_report_audit_flow_generates_salary(
    api, session, admin_role, test_user, task, assignment, process_price, sku, process
):
    _grant_report_audit(session, admin_role)
    headers = _auth(test_user)

    # 员工报工由 H5 侧提交，这里用 crud 造一条 submitted 记录，再走管理端 HTTP 审核
    report = create_report(
        session,
        task_id=task.id,
        report_user_id=test_user.id,
        good_qty=50, bad_qty=2, remark="ok", attachment_ids="",
    )
    session.flush()
    assert report.status == "submitted"

    # 班组长初审
    r1 = api.post(f"{BASE}/{report.id}/leader-approve", headers=headers)
    body1 = r1.json()
    assert body1["code"] == 200, body1
    assert body1["data"]["status"] == "leader_approved"

    # QC 终审 → 自动算薪 + 追溯码
    r2 = api.post(f"{BASE}/{report.id}/qc-approve", headers=headers)
    body2 = r2.json()
    assert body2["code"] == 200, body2
    data = body2["data"]
    assert data["status"] == "qc_approved"
    assert data["salary_generated"] is True
    # 计件 = 良品 50 × 单价 1.50 = 75.00
    assert float(data["salary_amount"]) == 75.00

    # 详情应带两级审核记录
    r3 = api.get(f"{BASE}/{report.id}", headers=headers)
    detail = r3.json()["data"]
    assert detail["status"] == "qc_approved"
    assert len(detail["audits"]) == 2

    # 工资明细通过 HTTP 可查
    r4 = api.get(f"{BASE}/salary/items?user_id={test_user.id}", headers=headers)
    items = r4.json()["data"]["items"]
    assert len(items) == 1
    assert float(items[0]["amount"]) == 75.00


# ── 非法状态流转在 HTTP 层被拦截 ──

def test_api_leader_approve_wrong_status_returns_400(
    api, session, admin_role, test_user, task, assignment, process_price
):
    _grant_report_audit(session, admin_role)
    headers = _auth(test_user)

    report = create_report(
        session,
        task_id=task.id,
        report_user_id=test_user.id,
        good_qty=10, bad_qty=0, remark="", attachment_ids="",
    )
    session.flush()

    # 先初审使其进入 leader_approved，再重复初审 → 状态不允许 → 业务码 400
    assert api.post(f"{BASE}/{report.id}/leader-approve", headers=headers).json()["code"] == 200
    resp = api.post(f"{BASE}/{report.id}/leader-approve", headers=headers)
    assert resp.json()["code"] == 400


def test_api_qc_approve_requires_leader_first(
    api, session, admin_role, test_user, task, assignment, process_price
):
    """跳过初审直接终审必须被拦截（submitted 状态不可 qc_approved）。"""
    _grant_report_audit(session, admin_role)
    headers = _auth(test_user)

    report = create_report(
        session,
        task_id=task.id,
        report_user_id=test_user.id,
        good_qty=8, bad_qty=0, remark="", attachment_ids="",
    )
    session.flush()

    resp = api.post(f"{BASE}/{report.id}/qc-approve", headers=headers)
    assert resp.json()["code"] == 400
    # 未生成工资
    items = api.get(f"{BASE}/salary/items?user_id={test_user.id}", headers=headers).json()["data"]["items"]
    assert items == []
