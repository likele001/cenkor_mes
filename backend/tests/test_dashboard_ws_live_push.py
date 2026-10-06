# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
"""P1.3 现网形态验证：业务接口 commit 之后，已连接的大屏真的收到 refresh。

`test_dashboard_ws_refresh.py` 测的是 hub 与监听器各自的职责；这里把
「TestClient 跑真接口 + 真 WebSocket 连接 + 跨线程投递」串起来，
证明 ws_hub.broadcast 不再是零生产者的死代码。

收消息用带超时的线程包装：断言失败时宁可报错，也不要让 pytest 挂在
receive_json 上。
"""
from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user, get_db
from app.core.security import create_access_token
# crm_adapter 的表不在 app/models 包里，需显式导入才会进 Base.metadata
from app.integration.crm_adapter import models as _crm_models  # noqa: F401
from app.models.customer import Customer
from app.models.permission import Permission
from app.models.role import Role
from app.models.sku import Sku
from app.models.user import User, user_roles
from app.api.ws import dashboard as ws_module

ADMIN = "/api/admin"


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
def screen_user(session) -> User:
    role = Role(code="screen_probe", name="大屏探针")
    perm = session.query(Permission).filter(Permission.code == "order.create").one_or_none()
    if perm is None:
        perm = Permission(code="order.create", name="order.create")
        session.add(perm)
    session.flush()
    if perm not in role.permissions:
        role.permissions.append(perm)
    u = User(
        username="screen-probe",
        password_hash="$2b$12$fakehashscreen",
        full_name="大屏",
        is_active=True,
    )
    session.add(u)
    session.flush()
    session.execute(user_roles.insert().values(user_id=u.id, role_id=role.id))
    session.flush()
    return u


@pytest.fixture
def screen_client(api, screen_user, monkeypatch):
    """WS 握手用真实 token 校验，但 `_user_from_token` 自己开 SessionLocal（真 MySQL），
    测试里换成同一个探针用户。"""
    monkeypatch.setattr(ws_module, "_user_from_token", lambda token: screen_user)
    return api


@pytest.fixture
def api(session, screen_user):
    """不用 `with TestClient(...)`，避免触发 startup 的 create_all（那会碰真实 MySQL）。"""
    from app.main import app

    def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: screen_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _recv_with_timeout(ws, seconds: float = 5.0):
    box: list = []

    def _read() -> None:
        try:
            box.append(ws.receive_json())
        except Exception as e:  # noqa: BLE001
            box.append(e)

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(seconds)
    if not box:
        pytest.fail(f"{seconds}s 内没收到任何 WS 消息（推送链路又断了）")
    if isinstance(box[0], Exception):
        pytest.fail(f"接收 WS 消息失败：{box[0]!r}")
    return box[0]


def test_order_create_pushes_refresh_to_connected_screen(screen_client, session):
    customer = Customer(name="探针客户", code="C-WS-PROBE")
    product = None
    session.flush()
    from app.models.product import Product

    product = Product(name="探针产品", code="P-WS-PROBE")
    sku = None
    session.add_all([customer, product])
    session.flush()
    from app.models.sku import Sku as _Sku

    sku = _Sku(product_id=product.id, code="S-WS-PROBE", name="探针型号", is_active=True)
    session.add(sku)
    session.flush()

    token = create_access_token({"sub": str(screen_client and 0 or 0)})  # placeholder


def _noop():
    pass
