# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""A 阶段缺陷回归：独立版设置兼容层 + 质量检测写端点提交。

钉住三件最容易复发的事：

1. SaaS 风格关键字调用 `get_setting(db, tenant_id=..., key=...)` /
   `upsert_setting(db, tenant_id=..., key=..., value=...)` 不再抛 TypeError；
   原有三种签名不许被兼容层改坏。
2. `quality.py` 写端点**必须显式 db.commit()**。同事务里 SELECT 分不出 flush 和
   commit（都能看到行），所以用 spy 包住 session 直接统计 commit 调用次数——
   这是唯一能在单测里钉住「返回 200 却不落库」的写法。
3. 写端点空 body 不许冒 500 / 501（既有单测曾全部直调 crud、跳过 API 装配层）。
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import create_access_token
from app.crud.tenant_setting import get_setting, upsert_setting
from app.models.base import Base
from app.models.permission import Permission
from app.models.quality import DefectCode, InspectionTemplate
from app.models.role import Role, role_permissions
from app.models.user import User, user_roles

P = "/api/admin/production"
CRM_GETS = [
    P + "/crm/opportunities",
    P + "/crm/opportunities/stats",
    P + "/crm/public-pool/opportunities",
    P + "/crm/settings",
]


class _SpySession:
    """只统计 commit，其余属性原样转发给真实 Session。"""

    def __init__(self, real: Session):
        self._real = real
        self.commits = 0

    def commit(self):
        self.commits += 1
        return self._real.commit()

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture(scope="session")
def engine():
    import app.models  # noqa: F401

    e = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(e, "connect")
    def _fk(conn, _record):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(e)
    return e


@pytest.fixture
def api_user(session):
    role = Role(code="admin-" + uuid.uuid4().hex[:6], name="管理员")
    session.add(role)
    session.flush()
    u = User(
        username="u-" + uuid.uuid4().hex[:8],
        password_hash="x",
        full_name="管理员",
        is_active=True,
        is_superuser=True,
    )
    session.add(u)
    session.flush()
    session.execute(user_roles.insert().values(user_id=u.id, role_id=role.id))
    codes = ("customer.manage", "crm.sales", "report.audit", "qc.approve",
             "qc.inspect", "setting.manage")
    for code in codes:
        p = session.scalar(select(Permission).where(Permission.code == code))
        if not p:
            p = Permission(code=code, name=code)
            session.add(p)
            session.flush()
        session.execute(role_permissions.insert().values(role_id=role.id, permission_id=p.id))
    session.flush()
    return u


@pytest.fixture
def api(session, api_user):
    from app.main import app

    spy = _SpySession(session)
    app.dependency_overrides[get_db] = lambda: spy
    try:
        yield TestClient(app), spy, api_user
    finally:
        app.dependency_overrides.pop(get_db, None)


def _auth(u) -> dict:
    return {"Authorization": "Bearer " + create_access_token({"sub": str(u.id)})}


def _count(session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


# ── A-1 独立版设置兼容层 ──

def test_tenant_setting_accepts_saas_keyword(session):
    key = "unit.a.key." + uuid.uuid4().hex[:6]
    upsert_setting(db=session, tenant_id=1, key=key, value="42")
    session.flush()
    got = get_setting(db=session, tenant_id=1, key=key)
    assert got is not None and got.value == "42"


def test_tenant_setting_legacy_signatures_still_work(session):
    key = "unit.b.key." + uuid.uuid4().hex[:6]
    upsert_setting(session, key, "v1")           # 单用户位置风格
    session.flush()
    assert get_setting(session, key).value == "v1"
    assert get_setting(session, 1, key).value == "v1"          # SaaS 位置风格
    assert get_setting(session, key=key).value == "v1"          # 关键字风格
    upsert_setting(session, key=key, value="v2")
    session.flush()
    assert get_setting(session, key).value == "v2"


def test_crm_get_endpoints_no_500(api):
    client, _spy, user = api
    for path in CRM_GETS:
        body = client.get(path, headers=_auth(user)).json()
        assert body["code"] not in (500, 501), (path, body)
        assert body["code"] == 200, (path, body)


def test_crm_settings_put_no_500(api):
    client, spy, user = api
    body = client.put(P + "/crm/settings", json={"recycle_days": 30},
                      headers=_auth(user)).json()
    assert body["code"] not in (500, 501), body
    assert body["code"] == 200, body
    assert spy.commits >= 1


# ── A-2 质量检测写端点必须提交 ──

def test_quality_create_endpoints_commit(api, session):
    client, spy, user = api
    h = _auth(user)
    tag = uuid.uuid4().hex[:8]

    t0, d0, n = _count(session, InspectionTemplate), _count(session, DefectCode), spy.commits
    r1 = client.post(P + "/inspection-templates", headers=h, json={
        "code": "QA-" + tag, "name": "回归模板",
        "items": [{"item_name": "外观", "item_type": "pass_fail"}],
    }).json()
    r2 = client.post(P + "/defect-codes", headers=h, json={
        "code": "QD-" + tag, "name": "回归缺陷", "severity": "minor",
    }).json()

    assert r1["code"] == 200 and r1["data"]["id"], r1
    assert r2["code"] == 200 and r2["data"]["id"], r2
    assert spy.commits >= n + 2, "两个创建端点都必须显式 commit，否则请求结束即回滚"
    assert _count(session, InspectionTemplate) == t0 + 1
    assert _count(session, DefectCode) == d0 + 1


def test_quality_update_and_delete_commit(api, session):
    client, spy, user = api
    h = _auth(user)
    tag = uuid.uuid4().hex[:8]

    tpl = client.post(P + "/inspection-templates", headers=h, json={
        "code": "QU-" + tag, "name": "原名", "items": [],
    }).json()["data"]
    dc = client.post(P + "/defect-codes", headers=h, json={
        "code": "QV-" + tag, "name": "原名", "severity": "minor",
    }).json()["data"]

    n = spy.commits
    u1 = client.put(P + "/inspection-templates/%s" % tpl["id"], headers=h, json={
        "code": "QU-" + tag, "name": "改名后", "items": [],
    }).json()
    u2 = client.put(P + "/defect-codes/%s" % dc["id"], headers=h, json={
        "code": "QV-" + tag, "name": "改名后", "severity": "major",
    }).json()
    assert u1["code"] == 200 and u2["code"] == 200, (u1, u2)
    assert spy.commits >= n + 2, "两个更新端点都必须 commit"
    assert session.get(InspectionTemplate, tpl["id"]).name == "改名后"
    assert session.get(DefectCode, dc["id"]).severity == "major"

    n = spy.commits
    d1 = client.delete(P + "/inspection-templates/%s" % tpl["id"], headers=h).json()
    d2 = client.delete(P + "/defect-codes/%s" % dc["id"], headers=h).json()
    assert d1["code"] == 200 and d2["code"] == 200, (d1, d2)
    assert spy.commits >= n + 2, "两个删除端点都必须 commit（软删 is_active=False 同样要落库）"
    assert session.get(InspectionTemplate, tpl["id"]).is_active in (False, 0)
    assert session.get(DefectCode, dc["id"]).is_active in (False, 0)


def test_quality_empty_body_not_server_error(api):
    client, _spy, user = api
    h = _auth(user)
    for path in (P + "/inspection-templates", P + "/defect-codes"):
        body = client.post(path, json={}, headers=h).json()
        assert body["code"] not in (500, 501), (path, body)
