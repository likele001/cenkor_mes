# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""P3.7：权限码必须真的管事（此前 20 个码只在 seed 里躺着，没人校验）。

守两类回归：
- 空转回归：某个码又被从校验里摘掉 → 对应接口变成「登录即放行」。
- 角色名硬编码回归：员工自助端一旦退回按 `employee`/`leader` 角色名判定，
  `worker` / `workshop_leader` / `production_manager` 这类自建角色就会整片 403。

约定同 `test_api_integration_core_flow.py`：全局异常处理器恒返回 HTTP 200，
业务码在 body 的 `code` 字段，故断言 `resp.json()["code"]`。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
# crm_adapter 的表不在 app/models 包里，需显式导入才会进 Base.metadata
from app.integration.crm_adapter import models as _crm_models  # noqa: F401
from app.models.permission import Permission
from app.models.role import Role, role_permissions
from app.models.user import User, user_roles

ADMIN = "/api/admin"
H5 = "/api/h5"


@pytest.fixture(scope="session")
def engine():
    """:memory: + StaticPool：TestClient 在 worker 线程跑 app，懒加载会跨线程取连接。"""
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
    """不用 `with TestClient(...)`，避免触发 startup 的 create_all（那会碰真实 MySQL）。"""
    from app.main import app

    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def bare_role(session):
    """一个没有任何权限点的角色，用来验证「无码即 403」。"""
    r = Role(code="gate_probe", name="校验探针")
    session.add(r)
    session.flush()
    return r


@pytest.fixture
def probe_user(bare_role, session) -> User:
    u = User(
        username="probe",
        password_hash="$2b$12$fakehashprobe",
        full_name="探针",
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.execute(user_roles.insert().values(user_id=u.id, role_id=bare_role.id))
    session.flush()
    return u


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


def _grant(session, role, code: str) -> None:
    """真实写入权限点并挂到角色，走完整 RBAC 查询链路。"""
    p = session.query(Permission).filter(Permission.code == code).one_or_none()
    if p is None:
        p = Permission(code=code, name=code)
        session.add(p)
        session.flush()
    if p not in role.permissions:
        role.permissions.append(p)
    session.flush()


def test_probe_role_starts_without_permissions(session, bare_role):
    assert [p.code for p in bare_role.permissions] == []


# ── 管理端：.view 码只能读，写仍需 .manage ──

@pytest.mark.parametrize(
    "path,code",
    [
        ("/api/admin/warehouse/stocks", "warehouse.view"),
        ("/api/admin/warehouse/logs", "warehouse.view"),
        ("/api/admin/equipment", "equipment.view"),
        ("/api/admin/production/orders", "order.view"),
        ("/api/admin/production/work-orders", "workorder.view"),
        ("/api/admin/production/tasks", "task.view"),
        ("/api/admin/plans", "production.plan"),
        ("/api/admin/production/report-units", "qc.inspect"),
        ("/api/admin/production/customers", "customer.view"),
        ("/api/crm-adapter/config", "crm.admin"),
    ],
)
def test_view_code_unlocks_read(api, session, probe_user, bare_role, path, code):
    assert api.get(path, headers=_auth(probe_user)).json()["code"] == 403
    _grant(session, bare_role, code)
    assert api.get(path, headers=_auth(probe_user)).json()["code"] == 200


@pytest.mark.parametrize(
    "path,view_code,manage_code",
    [
        ("/warehouse/stocks/adjust", "warehouse.view", "warehouse.manage"),
        ("/equipment", "equipment.view", "equipment.manage"),
        ("/production/customers", "customer.view", "customer.manage"),
    ],
)
def test_view_code_does_not_unlock_write(
    api, session, probe_user, bare_role, path, view_code, manage_code
):
    _grant(session, bare_role, view_code)
    assert api.post(f"{ADMIN}{path}", headers=_auth(probe_user), json={}).json()["code"] == 403
    _grant(session, bare_role, manage_code)
    assert api.post(f"{ADMIN}{path}", headers=_auth(probe_user), json={}).json()["code"] != 403


def test_order_create_code_unlocks_create_only(api, session, probe_user, bare_role):
    assert api.post(f"{ADMIN}/production/orders", headers=_auth(probe_user), json={}).json()["code"] == 403
    _grant(session, bare_role, "order.create")
    assert api.post(f"{ADMIN}/production/orders", headers=_auth(probe_user), json={}).json()["code"] != 403
    # 编辑权独立：order.create 不附带 order.edit
    assert api.put(
        f"{ADMIN}/production/orders/1", headers=_auth(probe_user), json={}
    ).json()["code"] == 403
    _grant(session, bare_role, "order.edit")
    assert api.put(
        f"{ADMIN}/production/orders/1", headers=_auth(probe_user), json={}
    ).json()["code"] != 403


def test_task_assign_code_unlocks_assignment(api, session, probe_user, bare_role):
    url = f"{ADMIN}/production/tasks/1/assign"
    assert api.post(url, headers=_auth(probe_user), json={}).json()["code"] == 403
    _grant(session, bare_role, "task.assign")
    assert api.post(url, headers=_auth(probe_user), json={}).json()["code"] != 403


def test_plan_manage_still_needed_to_create_plan(api, session, probe_user, bare_role):
    """production.plan 管排产，建计划仍要 plan.manage。"""
    _grant(session, bare_role, "production.plan")
    assert api.get(f"{ADMIN}/plans", headers=_auth(probe_user)).json()["code"] == 200
    assert api.post(f"{ADMIN}/plans", headers=_auth(probe_user), json={}).json()["code"] == 403


# ── 审批链：report.approve / qc.approve 各自管事 ──

def test_report_approve_codes_gate_the_two_steps(api, session, probe_user, bare_role, task, assignment):
    from app.crud.report import create_report

    report = create_report(
        session,
        task_id=task.id,
        report_user_id=probe_user.id,
        good_qty=10,
        bad_qty=0,
        remark="",
        attachment_ids="",
    )
    session.flush()

    leader_url = f"{ADMIN}/production/reports/{report.id}/leader-approve"
    qc_url = f"{ADMIN}/production/reports/{report.id}/qc-approve"
    assert api.post(leader_url, headers=_auth(probe_user)).json()["code"] == 403
    assert api.post(qc_url, headers=_auth(probe_user)).json()["code"] == 403

    _grant(session, bare_role, "report.approve")
    assert api.post(leader_url, headers=_auth(probe_user)).json()["code"] == 200
    # 班组长审批码不等于质检终审码
    assert api.post(qc_url, headers=_auth(probe_user)).json()["code"] == 403

    _grant(session, bare_role, "qc.approve")
    assert api.post(qc_url, headers=_auth(probe_user)).json()["code"] == 200


def test_qc_inspect_code_cannot_approve_report_unit(api, session, probe_user, bare_role):
    _grant(session, bare_role, "qc.inspect")
    assert api.get(f"{ADMIN}/production/report-units", headers=_auth(probe_user)).json()["code"] == 200
    assert api.post(
        f"{ADMIN}/production/report-units/1/approve", headers=_auth(probe_user)
    ).json()["code"] == 403


# ── 员工自助端：按权限码放行，不再按角色名 ──

def test_h5_task_list_opened_by_task_view(api, session, probe_user, bare_role):
    """`worker` 这类自建角色以前被 `{"employee","leader"}` 角色名判定整片挡死。"""
    assert api.get(f"{H5}/tasks", headers=_auth(probe_user)).json()["code"] == 403
    _grant(session, bare_role, "task.view")
    assert api.get(f"{H5}/tasks", headers=_auth(probe_user)).json()["code"] == 200


def test_h5_report_submit_needs_report_submit(api, session, probe_user, bare_role):
    _grant(session, bare_role, "task.view")
    url = f"{H5}/reports?task_code=T-NOT-EXIST&good_qty=1"
    assert api.post(url, headers=_auth(probe_user)).json()["code"] == 403
    _grant(session, bare_role, "report.submit")
    # 放行后才会走到业务校验（任务不存在）
    assert "任务不存在" in api.post(url, headers=_auth(probe_user)).json()["msg"]


def test_h5_salary_needs_salary_view(api, session, probe_user, bare_role):
    _grant(session, bare_role, "task.view")
    assert api.get(f"{H5}/salary", headers=_auth(probe_user)).json()["code"] == 403
    _grant(session, bare_role, "salary.view")
    assert api.get(f"{H5}/salary", headers=_auth(probe_user)).json()["code"] == 200
    assert api.get(f"{H5}/salary/slip", headers=_auth(probe_user)).json()["code"] == 200


# ── 防漂移：新增权限点必须挂到某个校验里 ──

def test_every_permission_code_is_enforced():
    """seed 里的每个码都要在代码里被校验引用，否则就是又一个空转码。

    三个码例外：它们对应的功能在本仓没有真实接口
    （AI 只剩返回空数据的占位路由，ERP 前端与路由已整体移除），无校验可挂。
    """
    import pathlib
    import re

    from app.core.seed import DEFAULT_PERMISSIONS

    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    sources = [
        p.read_text(errors="ignore")
        for p in root.rglob("*.py")
        if "__pycache__" not in str(p)
    ]
    blob = "\n".join(sources)
    declared = {code for code, _ in DEFAULT_PERMISSIONS}
    unused_ok = {"ai.use", "ai.alert.view", "erp.manage"}
    idle = sorted(
        code for code in declared
        if code not in unused_ok and f'"{code}"' not in blob
    )
    assert idle == [], f"这些权限点没有任何校验引用：{idle}"
    # 例外清单也要防膨胀：只允许确实无接口的码
    assert len(unused_ok) == 3
    assert re.search(r"ai_compat", blob)
